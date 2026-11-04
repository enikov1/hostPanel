# -*- coding: utf-8 -*-
"""Почта: виртуальные домены и ящики (Postfix + Dovecot + Mailutils).

Схема (как в небольших VPS-панелях):
  * Postfix — приём/отправка SMTP (25, 587 submission), виртуальные
    домены (/etc/postfix/vmailbox_domains) и ящики-Maildir
    (/etc/postfix/vmailbox → /var/vmail/домен/ящик/);
  * Dovecot — IMAP/POP3 и SMTP-авторизация (SASL-сокет private/auth),
    пароли (SHA512-CRYPT) в /etc/dovecot/users;
  * Mailutils — команда mail для отправки и теста доставки.

Все операции идемпотентны и выполняются от root (рабочий режим панели).
"""
import os
import re
import shutil
import time

from ..context import CTX, run, have
from .. import utils

VMAIL_USER = "vmail"
VMAIL_HOME = "/var/vmail"
DOVECOT_USERS = "/etc/dovecot/users"
POSTFIX_DOMAINS = "/etc/postfix/vmailbox_domains"
POSTFIX_VMAILBOX = "/etc/postfix/vmailbox"
DOVECOT_CONF = "/etc/dovecot/conf.d/99-hostpanel.conf"

_DOMAIN_RE = (r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?"
              r"(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$")
_EMAIL_RE = r"^[a-z0-9_\-.]{1,64}@[a-z0-9.\-]{3,255}$"


def _email_safe(email):
    """Полная проверка адреса ящика. Локальная часть строит путь
    Maildir (/var/vmail/<домен>/<локал>) — '.' и '..' должны быть
    исключены, иначе '.'/'..' проходят символьный класс и удаление
    «ящика» способно стереть /var/vmail целиком (path traversal)."""
    if not re.match(_EMAIL_RE, email or ""):
        return False
    local = email.partition("@")[0]
    if local in ("", ".", "..") or ".." in local or \
            local.startswith(".") or local.endswith("."):
        return False
    return True


# ------------------------------------------------------------- состояние ---
def _state():
    data = CTX.store.data.setdefault(
        "mail", {"domains": [], "mailboxes": []})
    data.setdefault("domains", [])
    data.setdefault("mailboxes", [])
    return data


def _unit_active(unit):
    code, out, _ = run(["systemctl", "is-active", unit], timeout=10)
    return code == 0 and out.strip() == "active"


def status():
    """Состояние почтового стека для страницы «Почта»."""
    data = _state()
    if CTX.demo:
        return {"installed": False, "postfix_installed": False,
                "dovecot_installed": False, "mailutils_installed": False,
                "postfix_active": False, "dovecot_active": False,
                "domains": 0, "mailboxes": 0, "server_ips": []}
    ips = []
    code, out, _ = run(["hostname", "-I"], timeout=10)
    if code == 0:
        ips = (out or "").split()
    return {"installed": have("postconf") and have("dovecot"),
            "postfix_installed": have("postconf"),
            "dovecot_installed": have("dovecot"),
            "mailutils_installed": have("mail"),
            "postfix_active": _unit_active("postfix"),
            "dovecot_active": _unit_active("dovecot"),
            "domains": len(data["domains"]),
            "mailboxes": len(data["mailboxes"]),
            "server_ips": ips}


def list_all():
    data = _state()
    return {"domains": data["domains"], "mailboxes": data["mailboxes"]}


# ------------------------------------------------------------ инфраструктура
def _write_domains_map(domains):
    """Карта виртуальных доменов: postmap требует «ключ значение»,
    поэтому каждому домену присваиваем произвольное значение."""
    _write(POSTFIX_DOMAINS,
           "".join("%s ok\n" % d for d in domains))


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _vmail_uid():
    code, out, _ = run(["id", "-u", VMAIL_USER], timeout=10)
    return (out or "").strip() or "5000"


def _master_cf_submission():
    """Включает службу submission (SMTP 587 c авторизацией) в master.cf."""
    path = "/etc/postfix/master.cf"
    text = _read(path)
    if not text:
        return
    if "hostpanel-submission" in text or \
            re.search(r"^submission\s+inet", text, re.M):
        return
    block = ("# hostpanel-submission: SMTP 587 с авторизацией (добавлено "
             "панелью)\n"
             "submission inet n       -       y       -       -       smtpd\n"
             "  -o syslog_name=postfix/submission\n"
             "  -o smtpd_sasl_auth_enable=yes\n"
             "  -o smtpd_client_restrictions=permit_sasl_authenticated,"
             "reject\n"
             "  -o smtpd_relay_restrictions=permit_sasl_authenticated,"
             "reject\n"
             "  -o smtpd_recipient_restrictions=permit_sasl_authenticated,"
             "reject\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + block)


def _dovecot_conf():
    # Синтаксис Dovecot 2.4: имя секции = драйвер, параметры — именованные
    # настройки. userdb passwd-file берёт home/uid/gid из /etc/dovecot/users
    # (формат passwd), mail_path = %{home} — оттуда же.
    return """# HostPanel: виртуальные почтовые ящики в /var/vmail
# (перечитывается последним, переопределяет значения из 10-*.conf;
# в Dovecot 2.4 INBOX по умолчанию ищется в /var/mail (mbox) —
# без переопределения mail_inbox_path SELECT INBOX падает с EACCES)
mail_driver = maildir
mail_path = %%{home}
mail_inbox_path = %%{home}
mail_privileged_group = %(vmail)s
first_valid_uid = %(uid)s

passdb passwd-file {
  default_password_scheme = SHA512-CRYPT
  auth_username_format = %%{user}
  passwd_file_path = /etc/dovecot/users
}
userdb passwd-file {
  auth_username_format = %%{user}
  passwd_file_path = /etc/dovecot/users
}

service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0660
    user = postfix
    group = postfix
  }
}
""" % {"vmail": VMAIL_USER, "uid": _vmail_uid()}


def _ensure_infra():
    """vmail-пользователь, настройки postfix/dovecot (идемпотентно)."""
    code, _, _ = run(["id", VMAIL_USER], timeout=10)
    if code != 0:
        run(["useradd", "-r", "-M", "-d", VMAIL_HOME,
             "-s", "/usr/sbin/nologin", VMAIL_USER],
            as_root=True, timeout=30)
    os.makedirs(VMAIL_HOME, exist_ok=True)
    run(["chown", "-R", "%s:%s" % (VMAIL_USER, VMAIL_USER), VMAIL_HOME],
        as_root=True, timeout=60)

    if have("postconf"):
        uid = _vmail_uid()
        run(["postconf", "-e",
             "virtual_mailbox_domains = hash:%s" % POSTFIX_DOMAINS,
             "virtual_mailbox_base = %s" % VMAIL_HOME,
             "virtual_mailbox_maps = hash:%s" % POSTFIX_VMAILBOX,
             "virtual_uid_maps = static:%s" % uid,
             "virtual_gid_maps = static:%s" % uid,
             "virtual_minimum_uid = 100",
             "mydestination = localhost",
             "smtpd_sasl_type = dovecot",
             "smtpd_sasl_path = private/auth",
             "smtpd_sasl_auth_enable = yes",
             "smtpd_tls_auth_only = no",
             "smtpd_recipient_restrictions = permit_sasl_authenticated, "
             "permit_mynetworks, reject_unauth_destination"],
            as_root=True, timeout=60)
        for path in (POSTFIX_DOMAINS, POSTFIX_VMAILBOX):
            if not os.path.exists(path):
                _write(path, "")
        _master_cf_submission()
        run(["postmap", POSTFIX_DOMAINS], as_root=True, timeout=60)
        run(["postmap", POSTFIX_VMAILBOX], as_root=True, timeout=60)
        run(["systemctl", "enable", "--now", "postfix"],
            as_root=True, timeout=60)

    if have("dovecot"):
        _write(DOVECOT_CONF, _dovecot_conf())
        _write(DOVECOT_USERS, _read(DOVECOT_USERS) or "", mode=0o640)
        run(["systemctl", "enable", "--now", "dovecot"],
            as_root=True, timeout=60)


def _reload_services(restart_dovecot=False):
    if have("dovecot"):
        if restart_dovecot:
            run(["systemctl", "restart", "dovecot"], as_root=True,
                timeout=60)
        else:
            run(["systemctl", "reload", "dovecot"], as_root=True,
                timeout=60)
    if have("postconf"):
        run(["postfix", "reload"], as_root=True, timeout=60)


# ------------------------------------------------------------------ домены --
def add_domain(domain):
    domain = (domain or "").strip().lower()
    if not re.match(_DOMAIN_RE, domain):
        return False, "некорректное имя домена (например, example.ru)"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    if not have("postconf"):
        return False, "сначала установите Postfix (Система → Установка ПО)"
    data = _state()
    if any(d["domain"] == domain for d in data["domains"]):
        return False, "домен %s уже добавлен" % domain
    _ensure_infra()
    domains = [d["domain"] for d in data["domains"]] + [domain]
    _write_domains_map(domains)
    run(["postmap", POSTFIX_DOMAINS], as_root=True, timeout=60)
    _reload_services()
    data["domains"].append({"domain": domain, "created": utils.now_str()})
    CTX.store.save()
    CTX.store.log_action("Добавлен почтовый домен %s" % domain)
    return True, "домен %s добавлен — не забудьте MX-запись у регистратора" \
                 % domain


def remove_domain(domain):
    domain = (domain or "").strip().lower()
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    data = _state()
    if not any(d["domain"] == domain for d in data["domains"]):
        return False, "домен не найден"
    boxes = [m for m in data["mailboxes"] if m["domain"] == domain]
    if boxes:
        return False, ("сначала удалите ящики домена: %s"
                       % ", ".join(m["email"] for m in boxes[:10]))
    _write_domains_map([d["domain"] for d in data["domains"]
                        if d["domain"] != domain])
    if have("postconf"):
        run(["postmap", POSTFIX_DOMAINS], as_root=True, timeout=60)
        _reload_services()
    data["domains"] = [d for d in data["domains"] if d["domain"] != domain]
    CTX.store.save()
    CTX.store.log_action("Удалён почтовый домен %s" % domain)
    return True, "домен %s удалён" % domain


# ------------------------------------------------------------------ ящики --
def _maildir(email):
    local, _, domain = email.partition("@")
    return os.path.join(VMAIL_HOME, domain, local)


def _hash_password(password):
    code, out, _ = run(["openssl", "passwd", "-6", "-stdin"],
                       input_text=password, timeout=15)
    if code == 0 and (out or "").strip().startswith("$6$"):
        return out.strip()
    code, out, _ = run(["doveadm", "pw", "-s", "SHA512-CRYPT",
                        "-p", password], timeout=15)
    if code == 0 and (out or "").strip():
        # doveadm возвращает {SHA512-CRYPT}$6$...
        return (out or "").strip().split("}", 1)[-1]
    raise RuntimeError("не удалось создать хэш пароля "
                       "(нет openssl/doveadm)")


def _users_lines():
    if not os.path.exists(DOVECOT_USERS):
        return []
    with open(DOVECOT_USERS, "r", encoding="utf-8") as f:
        return [l.rstrip("\n") for l in f if l.strip()]


def _user_line(email, pwhash):
    """Строка passwd-формата: user:hash:uid:gid::home::"""
    local, _, domain = email.partition("@")
    uid, gid = _vmail_uid(), _vmail_gid()
    home = os.path.join(VMAIL_HOME, domain, local)
    return "%s:%s:%s:%s::%s::" % (email, pwhash, uid, gid, home)


def _line_email(line):
    return line.split(":", 1)[0]


def _vmail_gid():
    code, out, _ = run(["id", "-g", VMAIL_USER], timeout=10)
    return (out or "").strip() or _vmail_uid()


def _save_users(lines):
    # 0640 root:dovecot — файл с хэшами паролей читает процесс dovecot,
    # но не остальные пользователи системы
    _write(DOVECOT_USERS,
           "\n".join(lines) + ("\n" if lines else ""), mode=0o640)
    try:
        import grp
        gid = grp.getgrnam("dovecot").gr_gid
        os.chown(DOVECOT_USERS, 0, gid)
    except (KeyError, OSError):
        pass


def _save_vmailbox(pairs):
    """pairs: [(email, 'домен/ящик/')] → /etc/postfix/vmailbox + postmap."""
    lines = ["%s %s/" % (email, path.rstrip("/")) for email, path in pairs]
    _write(POSTFIX_VMAILBOX, "\n".join(lines) + ("\n" if lines else ""))
    if have("postconf"):
        run(["postmap", POSTFIX_VMAILBOX], as_root=True, timeout=60)


def add_mailbox(email, password):
    """Создаёт ящик. Возвращает (ok, err, пароль)."""
    email = (email or "").strip().lower()
    if not _email_safe(email):
        return False, "некорректный адрес ящика", ""
    if len(password or "") < 6:
        return False, "пароль короче 6 символов", ""
    if CTX.demo:
        return False, "в демо-режиме недоступно", ""
    if not have("dovecot"):
        return False, "сначала установите Dovecot (Система → Установка ПО)", ""
    local, _, domain = email.partition("@")
    data = _state()
    if not any(d["domain"] == domain for d in data["domains"]):
        return False, ("сначала добавьте домен %s на странице «Почта»"
                       % domain), ""
    if any(m["email"] == email for m in data["mailboxes"]):
        return False, "ящик уже существует", ""
    _ensure_infra()
    try:
        pwhash = _hash_password(password)
    except RuntimeError as e:
        return False, str(e), ""
    # пользователи dovecot (passwd-формат): заменяем строку этого ящика,
    # остальные не трогаем
    users = [l for l in _users_lines() if _line_email(l) != email]
    users.append(_user_line(email, pwhash))
    _save_users(users)
    # Maildir
    mdir = _maildir(email)
    for sub in ("", "cur", "new", "tmp"):
        os.makedirs(os.path.join(mdir, sub), exist_ok=True)
    run(["chown", "-R", "%s:%s" % (VMAIL_USER, VMAIL_USER),
         os.path.join(VMAIL_HOME, domain)], as_root=True, timeout=60)
    # карта postfix
    vlines = [l.split(None, 1) for l in
              _read(POSTFIX_VMAILBOX).splitlines() if l.strip()]
    pairs = [(e, p.strip()) for e, p in vlines if e != email]
    pairs.append((email, "%s/%s" % (domain, local)))
    _save_vmailbox(pairs)
    _reload_services(restart_dovecot=True)
    data["mailboxes"].append({"email": email, "domain": domain,
                              "created": utils.now_str()})
    CTX.store.save()
    CTX.store.log_action("Создан почтовый ящик %s" % email)
    return True, "ящик %s создан" % email, password


def set_password(email, password):
    email = (email or "").strip().lower()
    if not _email_safe(email):
        return False, "некорректный адрес ящика"
    if len(password or "") < 6:
        return False, "пароль короче 6 символов"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    data = _state()
    if not any(m["email"] == email for m in data["mailboxes"]):
        return False, "ящик не найден"
    try:
        pwhash = _hash_password(password)
    except RuntimeError as e:
        return False, str(e)
    users = [_user_line(email, pwhash) if _line_email(l) == email
             else l for l in _users_lines()]
    if not any(_line_email(l) == email for l in users):
        return False, "ящик не найден в /etc/dovecot/users"
    _save_users(users)
    _reload_services(restart_dovecot=True)
    CTX.store.log_action("Изменён пароль ящика %s" % email)
    return True, "пароль ящика %s изменён" % email


def remove_mailbox(email):
    email = (email or "").strip().lower()
    if not _email_safe(email):
        return False, "некорректный адрес ящика"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    data = _state()
    if not any(m["email"] == email for m in data["mailboxes"]):
        return False, "ящик не найден"
    _save_users([l for l in _users_lines()
                 if _line_email(l) != email])
    vlines = [l.split(None, 1) for l in
              _read(POSTFIX_VMAILBOX).splitlines() if l.strip()]
    _save_vmailbox([(e, p.strip()) for e, p in vlines if e != email])
    shutil.rmtree(_maildir(email), ignore_errors=True)
    _reload_services(restart_dovecot=True)
    data["mailboxes"] = [m for m in data["mailboxes"]
                         if m["email"] != email]
    CTX.store.save()
    CTX.store.log_action("Удалён почтовый ящик %s" % email)
    return True, "ящик %s и его письма удалены" % email


# ------------------------------------------------------------- тест доставки
def test_delivery(email):
    """Отправляет тестовое письмо командой mail и ищет его в Maildir."""
    email = (email or "").strip().lower()
    if not _email_safe(email):
        return False, "некорректный адрес ящика"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    data = _state()
    if not any(m["email"] == email for m in data["mailboxes"]):
        return False, "ящик не найден"
    if not have("mail"):
        return False, "установите Mailutils (Система → Установка ПО)"
    if have("postconf"):
        _ensure_infra()
    subject = "HostPanel: тест доставки %s" % utils.now_str()[11:19]
    code, out, err = run(["mail", "-s", subject, "--", email],
                         input_text="Тестовое письмо из панели HostPanel.",
                         timeout=60)
    if code != 0:
        return False, "команда mail завершилась с ошибкой: %s" % \
            ((err or out)[:200])
    time.sleep(3)
    new_dir = os.path.join(_maildir(email), "new")
    try:
        found = [n for n in os.listdir(new_dir) if not n.startswith(".")]
    except OSError:
        found = []
    if found:
        CTX.store.log_action("Тест доставки в %s пройден" % email)
        return True, ("тестовое письмо доставлено (в ящике писем: %d)"
                      % len(found))
    return False, ("письмо не появилось в ящике за 3 сек — проверьте "
                   "журнал: journalctl -u postfix -n 20")
