# -*- coding: utf-8 -*-
"""HTTP-сервер панели: статика из web/, JSON API, загрузка, скачивание."""
import json
import mimetypes
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, utils
from .context import CTX, STATE_LOCK
from .api import auth
from .api import router  # noqa: F401 (импорт регистрирует маршруты)
from .api import general, sites, system, manage, mail, cli, swset, panelupd  # noqa: F401

PANEL_HOME_ = ""


class Handler(BaseHTTPRequestHandler):
    server_version = "HostPanel/" + config.VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # тише в консоли
        pass

    # -- низкий уровень -----------------------------------------------------
    def _send_bytes(self, body, ctype, code=200, headers=None, head=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # CSP: чужие скрипты/стили запрещены; 'unsafe-inline' оставлен, т.к.
        # фронтенд широко использует инлайн-обработчики onclick
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; "
                         "script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data:; "
                         "font-src 'self'; connect-src 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'; "
                         "form-action 'self'")
        self.send_header("Permissions-Policy",
                         "camera=(), microphone=(), geolocation=()")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def send_json(self, obj, code=200, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8",
                         code, headers)

    def send_html(self, html):
        body = html.encode("utf-8")
        self._send_bytes(body, "text/html; charset=utf-8")

    def send_file(self, path, name):
        try:
            size = os.path.getsize(path)
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        except OSError as e:
            return self.send_json({"ok": False, "error": str(e)}, 404)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition",
                         'attachment; filename="%s"' % name)
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(262144)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return

    def read_body(self):
        # тело читаем один раз и кешируем: повторное чтение rfile блокируется
        if getattr(self, "_body", None) is not None:
            return self._body
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        limit = config.MAX_UPLOAD_BODY \
            if (self.path.startswith("/api/files/upload") or
                self.path.startswith("/api/db/import") or
                self.path.startswith("/api/sites/import")) \
            else config.MAX_JSON_BODY
        if length > limit:
            self._body = b""
            self._oversized = True
            # тело не прочитано — keep-alive соединение надо закрыть,
            # иначе недочитанный мусор будет разобран как следующий запрос
            self.close_connection = True
            return b""
        self._body = self.rfile.read(length) if length > 0 else b""
        return self._body

    def read_json(self):
        body = self.read_body()
        if getattr(self, "_oversized", False):
            return None
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    # -- статика ------------------------------------------------------------
    def serve_static(self, route):
        """Отдаёт файлы сборки фронтенда (Vue SPA) из web/:
        index.html, favicon.svg, /assets/* (хешированные файлы Vite).
        Все остальные «страничные» пути отдаёт index.html —
        реальный URL-роутинг без перезагрузок (history mode)."""
        web = config.WEB_DIR
        if route.startswith("/assets/"):
            rel = route[8:]
            if ".." in rel or "/" in rel:
                return False
            path = os.path.join(web, "assets", rel)
            if not os.path.isfile(path):
                return False
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            if path.endswith(".js"):
                mime = "application/javascript; charset=utf-8"
            if path.endswith(".css"):
                mime = "text/css; charset=utf-8"
            with open(path, "rb") as f:
                # хеш в имени файла — можно кешировать надолго
                self._send_bytes(f.read(), mime,
                                 headers={"Cache-Control":
                                          "public, max-age=31536000, immutable"})
            return True
        if route in ("/favicon.svg",):
            path = os.path.join(web, "favicon.svg")
            if not os.path.isfile(path):
                return False
            with open(path, "rb") as f:
                self._send_bytes(f.read(), "image/svg+xml",
                                 headers={"Cache-Control": "no-store"})
            return True
        if route.startswith("/api/") or route == "/status":
            return False
        index = os.path.join(web, "index.html")
        if not os.path.isfile(index):
            return False
        with open(index, "rb") as f:
            self._send_bytes(f.read(), "text/html; charset=utf-8",
                             headers={"Cache-Control": "no-store"})
        return True

    # -- аутентификация ------------------------------------------------------
    def _auth(self):
        """(токен сессии | None, is_cli) — CLI-токен принимается вторым,
        аварийный одноразовый код сброса пароля — третьим (только POST
        /api/cli/reset-password, код кладёт root для hcp reset-password)."""
        token = auth.check_session(self)
        if token:
            return token, False
        cli_token = self.headers.get("X-CLI-Token", "")
        if cli_token and auth.cli_valid(cli_token, self, CTX.store.creds):
            return None, True
        if self.command == "POST" and \
                urllib.parse.urlparse(self.path).path == "/api/cli/reset-password":
            from .api.cli import reset_nonce_ok
            if reset_nonce_ok(self):
                # код здесь проверен и погашен (файл удалён) — повторно
                # его в cli._require_cli_token проверять нельзя
                self._reset_nonce = True
                return None, True
        return None, False

    # -- маршруты -----------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if route == "/status":
            return self._public_status()
        if self.serve_static(route):
            return
        if not route.startswith("/api/"):
            return self.send_json({"ok": False, "error": "не найдено"}, 404)
        if route == "/api/login-state":
            return self.send_json({
                "auth": bool(auth.check_session(self)),
                "default_password": bool(
                    CTX.store.creds.get("is_default")),
                "version": config.VERSION})
        token, is_cli = self._auth()
        if not token and not is_cli:
            return self.send_json({"ok": False, "error": "требуется вход"},
                                  401)
        if route == "/api/backup/download":
            return self._backup_download(qs)
        if route == "/api/files/download":
            return self._files_download(qs)
        if route == "/api/db/export":
            return self._db_export(qs)
        try:
            with STATE_LOCK:
                data = router.dispatch_get(route, qs, self)
            if isinstance(data, tuple):
                return self.send_json(data[0], data[1])
            return self.send_json(data)
        except Exception as e:  # noqa: BLE001
            utils.log("GET %s: %s" % (route, e))
            return self.send_json({"ok": False, "error": str(e)}, 500)

    def do_POST(self):
        self._body = None
        self._oversized = False
        route = urllib.parse.urlparse(self.path).path
        if route == "/api/login":
            return self.handle_login()
        if route == "/api/cli/login":
            return self.handle_cli_login()
        token, is_cli = self._auth()
        if not token and not is_cli:
            return self.send_json({"ok": False, "error": "требуется вход"},
                                  401)
        # CSRF: мутации из браузера — двойной submit (X-Panel-Token) ИЛИ
        # совпадающий Origin. Cookie SameSite=Strict кросс-сайтово не
        # отправляется, Origin — второй рубеж: fetch шлёт его всегда,
        # curl/hcp — никогда. Позволяет не хранить токен в localStorage.
        if not is_cli and route not in ("/api/logout",):
            if not self._csrf_ok(token):
                return self.send_json({"ok": False, "error": "CSRF"}, 403)
        # upload шлёт multipart — JSON не парсим
        if route in ("/api/files/upload", "/api/db/import",
                     "/api/sites/import"):
            body = {}
        else:
            body = self.read_json()
            if body is None:
                return self.send_json({"ok": False, "error": "некорректное "
                                                             "тело запроса"},
                                      400)
        try:
            with STATE_LOCK:
                data = router.dispatch_post(route, body, self)
            if isinstance(data, tuple):
                return self.send_json(data[0], data[1])
            return self.send_json(data)
        except Exception as e:  # noqa: BLE001
            utils.log("POST %s: %s" % (route, e))
            return self.send_json({"ok": False, "error": str(e)}, 500)

    def _public_status(self):
        """Опциональный публичный JSON для внешних мониторингов
        (UptimeRobot и т.п.). Включается в Настройках; без авторизации
        отдаёт только агрегаты — никаких доменов и секретов."""
        if not CTX.store.data["settings"].get("public_status"):
            return self.send_json({"ok": False, "error": "не найдено"}, 404)
        from .core import services
        svcs = services.detect_services()
        active = len([s for s in svcs if s.get("state") == "active"])
        sites = CTX.store.data.get("sites", [])
        import time as _t
        uptime = 0
        try:
            with open("/proc/uptime") as f:
                uptime = float(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            pass
        return self.send_json({
            "ok": True, "panel": config.PANEL_NAME,
            "version": config.VERSION,
            "uptime_sec": int(uptime),
            "services_active": active, "services_total": len(svcs),
            "sites_enabled": len([s for s in sites if s.get("enabled")]),
            "ts": utils.now_str()})

    # -- CSRF -------------------------------------------------------------------
    def _csrf_ok(self, token):
        if token and self.headers.get("X-Panel-Token", "") == token:
            return True
        origin = self.headers.get("Origin", "").strip()
        if not origin:
            return True  # не браузер (curl, hcp, проверки живучести)
        try:
            from urllib.parse import urlsplit
            ohost = urlsplit(origin).netloc
        except ValueError:
            return False
        if not ohost:
            return False
        host = self.headers.get("Host", "").strip()
        if ohost == host:
            return True
        # за прокси на нестандартном порту Host может приходить без порта
        # (nginx $host) при Origin с портом — сравниваем имена хостов
        return ohost.split(":")[0] == host.split(":")[0]

    # -- скачивание -----------------------------------------------------------
    def _backup_download(self, qs):
        bid = qs.get("id", [""])[0]
        meta = next((b for b in CTX.store.data.get("backups", [])
                     if b["id"] == bid), None)
        if not meta or not os.path.exists(meta["file"]):
            return self.send_json({"ok": False, "error": "архив не найден"},
                                  404)
        self.send_file(meta["file"], os.path.basename(meta["file"]))

    def _files_download(self, qs):
        from .context import fm_allowed
        from .core import files as files_mod
        path = qs.get("path", [""])[0]
        if not fm_allowed(path):
            return self.send_json({"ok": False, "error": "путь недоступен"},
                                  403)
        info = files_mod.download_info(path)
        if not info:
            return self.send_json({"ok": False, "error": "файл не найден"},
                                  404)
        self.send_file(info["path"], info["name"])

    def _db_export(self, qs):
        """Дамп базы: создаётся во временный файл, отдаётся и удаляется."""
        from .api.manage import db_export_file
        path, fname, error, code = db_export_file(qs)
        if error:
            return self.send_json({"ok": False, "error": error}, code)
        try:
            self.send_file(path, fname)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    # -- вход -----------------------------------------------------------------
    def _client_ip(self):
        """Реальный IP клиента. За nginx-прокси (TLS-фронт) соединение
        приходит с 127.0.0.1 — берём X-Real-IP, который прокси ставит из
        фактического адреса. Заголовок доверяем ТОЛЬКО от loopback: прямое
        подключение снаружи (закрыто ufw) не сможет подделать IP и обойти
        лимит попыток входа."""
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "::1"):
            fwd = (self.headers.get("X-Real-IP") or "").strip()
            if fwd:
                return fwd.split(",")[0].strip()
        return ip

    def handle_login(self):
        ip = self._client_ip()
        if not auth.login_allowed(ip):
            return self.send_json(
                {"ok": False, "error": "слишком много попыток, подождите "
                                      "5 минут"}, 429)
        p = self.read_json() or {}
        ok = auth.verify(p.get("password", ""), CTX.store.creds) and \
            p.get("login", "") == CTX.store.creds["login"]
        if not ok:
            auth.login_failed(ip)
            utils.log("Неудачный вход с %s" % ip)
            left = max(0, config.LOGIN_MAX_FAILS -
                       len(auth.LOGIN_FAILS.get(ip, [])))
            return self.send_json(
                {"ok": False, "error": "неверный логин или пароль",
                 "attempts_left": left}, 401)
        # включена двухфакторная аутентификация — нужен код приложения
        if CTX.store.creds.get("totp_enabled"):
            if not auth.totp_valid(CTX.store.creds.get("totp_secret"),
                                   p.get("code", "")):
                auth.login_failed(ip)
                utils.log("Неудачный код 2FA с %s" % ip)
                left = max(0, config.LOGIN_MAX_FAILS -
                           len(auth.LOGIN_FAILS.get(ip, [])))
                return self.send_json(
                    {"ok": False, "need_code": True, "attempts_left": left,
                     "error": "введите код из приложения-аутентификатора"},
                    401)
        auth.login_ok(ip)
        # security-уведомление (если включено) — в фоне, чтобы не тормозить вход
        if CTX.store.data["settings"].get("notify", {}).get(
                "security", {}).get("enabled"):
            import threading as _th
            _ua = self.headers.get("User-Agent", "")
            _ip = ip

            def _sec_note():
                try:
                    from .core import notify
                    body = ("Вход администратора\nIP: %s\nУстройство: %s\n"
                            "Время: %s"
                            % (_ip, (_ua or "?")[:200], utils.now_str()))
                    notify.send("HostPanel: вход в панель", body)
                except Exception as e:  # noqa: BLE001
                    utils.log("security notify: %s" % e)
            _th.Thread(target=_sec_note, daemon=True).start()
        token = auth.new_session(CTX.store.creds["login"], ip,
                                 self.headers.get("User-Agent", ""))
        cookie = ("hp_token=%s; Path=/; HttpOnly; SameSite=Strict; "
                  "Max-Age=%d" % (token, config.SESSION_TTL))
        utils.log("Вход администратора с %s" % ip)
        CTX.store.log_action("Вход администратора с %s" % ip)
        # вход со стандартным паролем admin — потребовать смену
        must_change = bool(CTX.store.creds.get("must_change_password")) or \
            auth.verify("admin", CTX.store.creds)
        if must_change:
            CTX.store.creds["must_change_password"] = True
            CTX.store.save()
        return self.send_json({"ok": True, "token": token,
                               "must_change_password": must_change},
                              headers={"Set-Cookie": cookie})


    # -- вход из консоли (hcp-login) ------------------------------------------
    def handle_cli_login(self):
        """Выдача CLI-токена: только с 127.0.0.1, логин+пароль (+2FA),
        отдельный лимит попыток, в панели хранится только хеш токена."""
        from .api.cli import _save_creds
        ip = self.client_address[0]
        if ip not in auth.CLI_LOOPBACK:
            utils.log("CLI-вход отклонён: не локальный адрес (%s)" % ip)
            return self.send_json(
                {"ok": False, "error": "CLI-вход доступен только с самого "
                                       "сервера (127.0.0.1)"}, 403)
        if not auth.cli_login_allowed(ip):
            return self.send_json(
                {"ok": False, "error": "слишком много попыток, подождите "
                                       "5 минут"}, 429)
        p = self.read_json() or {}
        okc = auth.verify(p.get("password", ""), CTX.store.creds) and \
            p.get("login", "") == CTX.store.creds["login"]
        if not okc:
            auth.cli_login_failed(ip)
            utils.log("CLI: неудачный hcp-login с %s" % ip)
            return self.send_json(
                {"ok": False, "error": "неверный логин или пароль"}, 401)
        if CTX.store.creds.get("totp_enabled"):
            if not auth.totp_valid(CTX.store.creds.get("totp_secret"),
                                   p.get("code", "")):
                auth.cli_login_failed(ip)
                return self.send_json(
                    {"ok": False, "need_code": True,
                     "error": "введите код из приложения-аутентификатора"},
                    401)
        auth.cli_login_ok(ip)
        token = auth.cli_issue(CTX.store.creds)
        _save_creds()
        CTX.store.log_action("CLI: выдан токен (hcp-login) с %s" % ip)
        utils.log("CLI: выдан токен (hcp-login) с %s" % ip)
        return self.send_json({"ok": True, "token": token,
                               "home": CTX.home})


def run_server(port):
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    server.serve_forever()
    return server
