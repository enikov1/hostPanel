# -*- coding: utf-8 -*-
"""Аутентификация: сессии, PBKDF2, TOTP (2FA), ограничение попыток входа."""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import threading
import time

from ..config import SESSION_TTL, LOGIN_MAX_FAILS, LOGIN_FAIL_WINDOW
from ..context import CTX

SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
LOGIN_FAILS = {}
CLI_FAILS = {}

# плоский журнал неудачных входов — источник для fail2ban (jail hostpanel)
AUTH_LOG = "/var/log/hostpanel/auth.log"


def _auth_log(text):
    if CTX.demo:
        return
    try:
        d = os.path.dirname(AUTH_LOG)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(AUTH_LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
    except OSError:
        pass

TOTP_STEP = 30          # шаг TOTP, сек (стандарт RFC 6238)

# CLI-токен принимается только с локальной машины
CLI_LOOPBACK = ("127.0.0.1", "::1")


def new_session(user, ip="", ua=""):
    token = secrets.token_hex(24)
    now = time.time()
    with SESSIONS_LOCK:
        SESSIONS[token] = {"user": user, "ts": now, "created": now,
                           "ip": ip or "", "ua": (ua or "")[:200],
                           "sid": secrets.token_hex(4)}
        # подчистка просроченных
        deadline = now - SESSION_TTL
        for t in list(SESSIONS):
            if SESSIONS[t]["ts"] < deadline:
                del SESSIONS[t]
    return token


def list_sessions():
    """Активные сессии для показа администратору (без токенов)."""
    with SESSIONS_LOCK:
        return [{"sid": s["sid"], "user": s["user"], "ip": s["ip"],
                 "ua": s["ua"], "created": s.get("created", s["ts"]),
                 "seen": s["ts"]}
                for s in SESSIONS.values()]


def session_sid(token):
    with SESSIONS_LOCK:
        s = SESSIONS.get(token)
        return s["sid"] if s else ""


def drop_session(token):
    with SESSIONS_LOCK:
        SESSIONS.pop(token, None)


def drop_session_sid(sid):
    """Завершение чужой сессии по короткому идентификатору."""
    with SESSIONS_LOCK:
        for t in list(SESSIONS):
            if SESSIONS[t]["sid"] == sid:
                del SESSIONS[t]
                return True
    return False


def check_session(handler):
    """Токен из заголовка X-Panel-Token или cookie hp_token."""
    token = handler.headers.get("X-Panel-Token", "")
    if token and _valid(token):
        return token
    cookie = handler.headers.get("Cookie", "")
    for part in cookie.split(";"):
        if part.strip().startswith("hp_token="):
            token = part.strip()[9:]
            if _valid(token):
                return token
    return None


def _valid(token):
    with SESSIONS_LOCK:
        s = SESSIONS.get(token)
        if s is None:
            return False
        s["ts"] = time.time()
        return True


def login_allowed(ip):
    """Ограничение частоты попыток входа."""
    fails = LOGIN_FAILS.setdefault(ip, [])
    fails[:] = [t for t in fails if time.time() - t < LOGIN_FAIL_WINDOW]
    return len(fails) < LOGIN_MAX_FAILS


def login_failed(ip):
    LOGIN_FAILS.setdefault(ip, []).append(time.time())
    _auth_log("login-failed ip=%s" % ip)


def login_ok(ip):
    LOGIN_FAILS.pop(ip, None)


def verify(password, creds):
    from ..state import pbkdf2
    h = pbkdf2(password, creds["salt"])
    return hmac.compare_digest(h, creds["hash"])


# ---------------------------------------------------------------- TOTP ---
def totp_secret_new():
    """Новый секрет TOTP (base32, 20 байт = 160 бит)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp_at(secret, counter):
    key = base64.b32decode(
        secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset:offset + 4])[0]
            & 0x7FFFFFFF) % 1_000_000
    return "%06d" % code


def totp_valid(secret, code):
    """Код верен, если совпадает с текущим/соседним окном (±30 сек)."""
    code = (code or "").strip()
    if not secret or not code.isdigit() or len(code) != 6:
        return False
    now = int(time.time() // TOTP_STEP)
    try:
        return any(hmac.compare_digest(_totp_at(secret, now + d), code)
                  for d in (-1, 0, 1))
    except Exception:  # noqa: BLE001 — битый секрет приравниваем к неверному
        return False


def totp_uri(secret, login="admin"):
    """otpauth://-ссылка для добавления в приложение-аутентификатор."""
    return ("otpauth://totp/HostPanel:%s?secret=%s&issuer=HostPanel"
            "&algorithm=SHA1&digits=6&period=30" % (login, secret))


# ------------------------------------------------------------- CLI -------
def cli_issue(creds):
    """Выдать CLI-токен: в панели остаётся только SHA-256, само значение
    возвращается один раз и хранится в /opt/hostpanel/cli-token (0600)."""
    token = secrets.token_hex(32)
    creds["cli_token"] = hashlib.sha256(token.encode()).hexdigest()
    creds["cli_created"] = int(time.time())
    return token


def cli_revoke(creds):
    creds.pop("cli_token", None)
    creds.pop("cli_created", None)


def cli_valid(token, handler, creds):
    """Токен действителен только с 127.0.0.1 — даже украденный токен
    бесполезен из интернета (панель проверяет адрес подключения)."""
    if handler.client_address[0] not in CLI_LOOPBACK:
        return False
    stored = creds.get("cli_token") or ""
    if not stored or not token:
        return False
    got = hashlib.sha256(token.encode()).hexdigest()
    return hmac.compare_digest(got, stored)


def cli_login_allowed(ip):
    """Ограничение попыток hcp-login — отдельный счётчик, чтобы блокировка
    консольного входа не запирала вход в веб-интерфейс."""
    fails = CLI_FAILS.setdefault("cli:" + ip, [])
    fails[:] = [t for t in fails if time.time() - t < LOGIN_FAIL_WINDOW]
    return len(fails) < LOGIN_MAX_FAILS


def cli_login_failed(ip):
    CLI_FAILS.setdefault("cli:" + ip, []).append(time.time())
    _auth_log("cli-login-failed ip=%s" % ip)


def cli_login_ok(ip):
    CLI_FAILS.pop("cli:" + ip, None)
