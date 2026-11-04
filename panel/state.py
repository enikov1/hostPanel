# -*- coding: utf-8 -*-
"""Хранилище состояния панели: state.json + учётные данные администратора.

Состояние мутируется под state.lock (короткие секции), сохранение атомарное
(запись во временный файл + os.replace).
"""
import json
import os
import secrets
import threading

from . import utils
from .config import SESSION_TTL  # noqa: F401 (реэкспорт для удобства)

try:
    import fcntl  # межпроцессная блокировка state.json (cron-режимы)
except ImportError:  # демо на другой ОС
    fcntl = None


class _Flock:
    """Эксклюзивная межпроцессная блокировка на файл <home>/state.lock:
    панель и cron-процессы (--cron-backup, --ssl-renew) пишут state.json
    из разных процессов — без flock последний писавший затирает чужие
    изменения. Используется как менеджер контекста."""

    def __init__(self, home):
        self.path = os.path.join(home, "state.lock")
        self.fd = None

    def __enter__(self):
        if fcntl is None:
            return self
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except OSError:
            self.fd = None
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        return False


def default_perf():
    """Профиль производительности сайта (nginx-галочки) — по умолчанию
    всё выключено: поведение существующих сайтов не меняется."""
    return {"gzip": False, "static_cache": False, "hsts": False,
            "http2": False}


def default_snippets():
    """Библиотека nginx-сниппетов сайта."""
    return {"www_redirect": False, "admin_ip": "", "upload_size": ""}


def pbkdf2(password, salt):
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               bytes.fromhex(salt), 200_000).hex()


def default_security():
    """Настройки безопасности нового сайта (гео/IP/лимиты/WAF)."""
    return {
        "geo_mode": "off",        # off | allow (только эти страны) | deny
        "geo_countries": [],      # коды ISO-3166 alpha-2
        "ip_allow": [],
        "ip_deny": [],
        "rate_limit": 0,          # запросов/сек, 0 = выключено
        "rate_burst": 20,
        "block_bots": False,      # блокировать плохих ботов (грубая галочка)
        "waf": False,             # базовый WAF (SQLi/XSS/скрытые файлы)
        # --- WAF 2.0: тонкие правила ---
        "geo_allow": [],          # страны, которым доступ разрешён
        "geo_deny": [],           # страны, которым доступ запрещён
        "ua_categories": [],      # id категорий ботов из config.BOT_CATEGORIES
        "ua_rules": [],           # [{"pattern": "...", "note": "..."}]
        "block_empty_ua": False,  # запросы без User-Agent
        "ref_block": [],          # домены-источники, с которых не пускаем
        "ref_allow": [],          # белый список источников (если непуст — только они)
        "block_empty_ref": False, # запросы без Referer
    }


class Store:
    """JSON-состояние панели + учётные данные администратора."""

    def __init__(self, home, demo):
        self.home = home
        self.demo = demo
        self.path = os.path.join(home, "state.json")
        self.cred_path = os.path.join(home, "admin.json")
        self.lock = threading.RLock()
        os.makedirs(home, exist_ok=True)
        for sub in ("backups", "certs", "logs", "tmp"):
            os.makedirs(os.path.join(home, sub), exist_ok=True)
        self.data = self._load_or_seed()
        self._migrate()
        self.creds = self._load_creds()

    # -- загрузка ---------------------------------------------------------
    def _load_or_seed(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:  # noqa: BLE001
                utils.log("Не удалось прочитать state.json (%s), создаю заново"
                          % e)
        data = self._seed_base()
        if self.demo:
            from . import demo
            demo.seed_demo(data, self.home)
        self.data = data
        self.save()
        return data

    def _seed_base(self):
        return {
            "settings": {
                "panel_port": 8080,
                "backup_retention": 7,
                "auto_backup_cron": "0 3 * * *",
                "auto_backup_enabled": False,
                "theme": "dark",
                "health_interval": 60,
                "fm_restricted": True,
            },
            "sites": [],
            "dbs": [],
            "backups": [],
            "cron": [],
            "notifications": [],
            "stats": {},
            "health": {},
            "packages": {"demo_installed": {}, "demo_versions": [],
                         "demo_upgradable": [], "apt_updated": ""},
            "panel_log": [],
        }

    def _migrate(self):
        """Дозаполняем поля, добавленные в новых версиях панели."""
        for site in self.data.get("sites", []):
            site.setdefault("parent", 0)
            site.setdefault("maintenance", False)
            sec = site.setdefault("security", default_security())
            for key, val in default_security().items():
                sec.setdefault(key, val)
            perf = site.setdefault("perf", default_perf())
            for key, val in default_perf().items():
                perf.setdefault(key, val)
            snip = site.setdefault("snippets", default_snippets())
            for key, val in default_snippets().items():
                snip.setdefault(key, val)
        self.data.setdefault("health", {})
        self.data.setdefault("packages", self._seed_base()["packages"])
        self.data.setdefault("mail", {"domains": [], "mailboxes": []})
        self.data["settings"].setdefault("ssl_autorenew_enabled", True)
        self.data["settings"].setdefault("ssl_renew_cron", "30 3,15 * * *")
        self.data["settings"].setdefault("expert_mode", False)
        self.data["settings"].setdefault("public_status", False)
        self.data["settings"].setdefault("weekly_report_enabled", False)
        self.data["settings"].setdefault(
            "notify", {"email": {"enabled": False, "host": "", "port": 587,
                                 "user": "", "pass": "", "from": "",
                                 "to": ""},
                       "tg": {"enabled": False, "token": "", "chat": ""}})
        notify = self.data["settings"]["notify"]
        notify.setdefault("email", {})
        notify.setdefault("tg", {})
        notify.setdefault("security", {"enabled": False})
        for k, v in (("host", ""), ("port", 587), ("user", ""),
                     ("pass", ""), ("from", ""), ("to", ""),
                     ("enabled", False)):
            notify["email"].setdefault(k, v)
        for k, v in (("token", ""), ("chat", ""), ("enabled", False)):
            notify["tg"].setdefault(k, v)

    def _load_creds(self):
        if os.path.exists(self.cred_path):
            try:
                with open(self.cred_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # первый запуск: стандартный вход admin/admin; панель после входа
        # сразу предложит заменить пароль на надёжный (must_change_password)
        password = "admin"
        salt = secrets.token_hex(16)
        creds = {"login": "admin", "salt": salt,
                 "hash": pbkdf2(password, salt), "created": utils.now_str(),
                 "is_default": True}  # подсказка на экране входа
        with open(self.cred_path, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(self.cred_path, 0o600)
        except OSError:
            pass
        pw_file = os.path.join(self.home, "admin.txt")
        with open(pw_file, "w", encoding="utf-8") as f:
            f.write("Логин: admin\nПароль: admin\n\n"
                    "Это стандартный пароль первого запуска.\n"
                    "Панель предложит сменить его сразу после входа — "
                    "обязательно сделайте это.\n")
        try:
            os.chmod(pw_file, 0o600)
        except OSError:
            pass
        utils.log("Первый запуск: логин admin, пароль admin (панель "
                  "потребует сменить его после входа)")
        return creds

    # -- сохранение ---------------------------------------------------------
    def save(self):
        with self.lock, _Flock(self.home):
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    # -- журнал и уведомления ------------------------------------------------
    def notify(self, text, level="info"):
        with self.lock:
            self.data.setdefault("notifications", []).insert(
                0, {"ts": utils.now_str(), "level": level, "text": text})
            self.data["notifications"] = self.data["notifications"][:100]

    def log_action(self, text):
        """Аудит: каждая операция панели попадает в журнал."""
        with self.lock:
            entry = {"ts": utils.now_str(), "text": text}
            pl = self.data.setdefault("panel_log", [])
            pl.insert(0, entry)
            self.data["panel_log"] = pl[:400]

    # -- помощники для обработчиков -------------------------------------------
    def find_site(self, sid):
        for s in self.data.get("sites", []):
            if s["id"] == sid:
                return s
        return None

    def find_site_by_domain(self, domain):
        for s in self.data.get("sites", []):
            if s["domain"] == (domain or "").strip().lower():
                return s
        return None

    def site_domains(self):
        return [s["domain"] for s in self.data.get("sites", [])]
