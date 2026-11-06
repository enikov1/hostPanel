# -*- coding: utf-8 -*-
"""API консольного клиента hcp: отзыв CLI-токена и аварийный сброс пароля.

Сам вход (/api/cli/login) живёт в server.py — он до сессии. Здесь два
маршрута, доступных ТОЛЬКО с CLI-токеном и только с локальной машины:
сессия браузера их вызвать не может. Это сознательно: сброс пароля —
аварийный инструмент для консоли, когда в панель не пускает.
"""
import hmac
import json
import os
import secrets
import time

from .. import utils
from ..context import CTX
from ..state import pbkdf2
from . import auth
from .router import post, ok, err

# аварийный сброс пароля без логина: root заранее кладёт одноразовый код
# в этот файл (0600, владелец root), hcp передаёт его в X-Reset-Auth
RESET_NONCE_FILE = os.path.join(CTX.home, "reset-nonce")
RESET_NONCE_TTL = 120  # сек — код живёт 2 минуты и сгорает после попытки


def _save_creds():
    with open(CTX.store.cred_path, "w", encoding="utf-8") as f:
        json.dump(CTX.store.creds, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(CTX.store.cred_path, 0o600)
    except OSError:
        pass


def reset_nonce_ok(handler):
    """Проверка одноразового кода аварийного сброса (маршрут /api/cli/
    reset-password, только 127.0.0.1). Файл уничтожается при любой
    попытке — код работает один раз; просроченный (2 мин) не принимается.
    Создать файл может только root (/opt/hostpanel принадлежит root),
    поэтому это не лазейка, а штатный аварийный вход из консоли."""
    if handler.client_address[0] not in auth.CLI_LOOPBACK:
        return False
    got = handler.headers.get("X-Reset-Auth", "")
    want = ""
    try:
        st = os.stat(RESET_NONCE_FILE)
        if st.st_uid != 0 or (st.st_mode & 0o022):
            return False  # владелец не root или права слишком широкие
        if time.time() - st.st_mtime > RESET_NONCE_TTL:
            return False
        with open(RESET_NONCE_FILE, encoding="utf-8") as f:
            want = f.read().strip()
    except OSError:
        return False
    finally:
        try:
            os.remove(RESET_NONCE_FILE)
        except OSError:
            pass
    if not want or not got:
        return False
    return hmac.compare_digest(got, want)


def _require_cli_token(handler):
    """CLI-маршруты не работают из браузерной сессии — только по токену
    (или по одноразовому коду root для аварийного сброса пароля: код
    проверен и погашен в server._auth, сюда доходит флаг на handler)."""
    token = handler.headers.get("X-CLI-Token", "")
    if auth.cli_valid(token, handler, CTX.store.creds):
        return True
    return bool(getattr(handler, "_reset_nonce", False))


@post("/api/cli/logout")
def cli_logout(handler, body):
    if not _require_cli_token(handler):
        return err("нужен CLI-токен с локальной машины (hcp-login)", 403)
    auth.cli_revoke(CTX.store.creds)
    _save_creds()
    CTX.store.log_action("CLI: токен отозван (hcp-logout)")
    return ok(message="CLI-токен отозван, файл на сервере можно удалить")


@post("/api/cli/reset-password")
def cli_reset_password(handler, body):
    """Аварийный сброс пароля администратора из консоли (root).

    Два способа авторизации запроса: обычный CLI-токен (hcp-login) ИЛИ
    одноразовый код из /opt/hostpanel/reset-nonce — его кладёт hcp, когда
    пароль потерян и войти некому (работает без логина, только root и
    только с самого сервера). Новый пароль генерируется (или передан в
    теле), показывается один раз и дублируется в admin.txt (0600).
    Все активные сессии и счётчики неудачных попыток сбрасываются.
    """
    if not _require_cli_token(handler):
        return err("нужен CLI-токен с локальной машины (hcp-login)", 403)
    new_pw = str(body.get("password") or "").strip()
    if not new_pw:
        new_pw = secrets.token_urlsafe(12)
    if len(new_pw) < 8:
        return err("пароль слишком короткий — минимум 8 символов")
    if new_pw == "admin":
        return err("пароль «admin» запрещён — придумайте надёжный")
    store = CTX.store
    store.creds["salt"] = secrets.token_hex(16)
    store.creds["hash"] = pbkdf2(new_pw, store.creds["salt"])
    store.creds.pop("must_change_password", None)
    store.creds.pop("is_default", None)
    if body.get("drop_totp"):
        store.creds.pop("totp_enabled", None)
        store.creds.pop("totp_secret", None)
    _save_creds()
    # новый пароль — единственный способ входа: завершаем все сессии
    # и снимаем блокировку «слишком много попыток» для веб-интерфейса
    with auth.SESSIONS_LOCK:
        auth.SESSIONS.clear()
    auth.LOGIN_FAILS.clear()
    auth.CLI_FAILS.clear()
    pw_file = os.path.join(store.home, "admin.txt")
    try:
        with open(pw_file, "w", encoding="utf-8") as f:
            f.write("Логин: %s\nПароль: %s\n\nПароль сброшен из консоли "
                    "(hcp-reset-password) %s.\nСмените его в настройках "
                    "панели и удалите этот файл.\n"
                    % (store.creds["login"], new_pw, utils.now_str()))
        os.chmod(pw_file, 0o600)
    except OSError:
        pw_file = ""
    CTX.store.log_action("CLI: пароль администратора сброшен "
                         "(hcp-reset-password, все сессии завершены)")
    return ok(message="пароль администратора изменён", password=new_pw,
              login=store.creds["login"], file=pw_file)
