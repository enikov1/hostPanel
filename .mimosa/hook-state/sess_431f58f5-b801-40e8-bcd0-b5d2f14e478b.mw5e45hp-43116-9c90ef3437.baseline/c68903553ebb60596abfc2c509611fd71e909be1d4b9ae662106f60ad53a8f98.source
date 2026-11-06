# -*- coding: utf-8 -*-
"""Чистые вспомогательные функции: не зависят от состояния выполнения."""
import datetime as dt
import os
import re
import secrets
import string

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,18}$",
    re.IGNORECASE)
SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$",
                          re.IGNORECASE)
IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print("[%s] %s" % (now_str(), msg), flush=True)


def valid_domain(name):
    return bool(name) and bool(DOMAIN_RE.match(name.strip().lower()))


def valid_subdomain(name):
    return bool(name) and bool(SUBDOMAIN_RE.match(name.strip().lower()))


def valid_ip(ip):
    if not IP_RE.match(ip or ""):
        return False
    return all(0 <= int(p) <= 255 for p in ip.split("."))


def valid_country(code):
    return bool(COUNTRY_RE.match(code or ""))


def gen_password(length=16):
    abc = string.ascii_letters + string.digits
    while True:
        pwd_ = "".join(secrets.choice(abc) for _ in range(length))
        if (any(c.islower() for c in pwd_) and any(c.isupper() for c in pwd_)
                and any(c.isdigit() for c in pwd_)):
            return pwd_


def human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if abs(n) < 1024 or unit == "ТБ":
            if unit == "Б":
                return "%d %s" % (int(n), unit)
            return ("%.1f %s" % (n, unit)).replace(".", ",")
        n /= 1024.0
    return "—"


def human_uptime(seconds):
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append("%d дн." % days)
    if hours:
        parts.append("%d ч." % hours)
    parts.append("%d мин." % minutes)
    return " ".join(parts)


def time_ago(iso_str):
    try:
        t = dt.datetime.strptime(str(iso_str)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(iso_str)
    d = dt.datetime.now() - t
    s = int(d.total_seconds())
    if s < 0:
        s = 0
    if s < 60:
        return "только что"
    if s < 3600:
        return "%d мин. назад" % (s // 60)
    if s < 86400:
        return "%d ч. назад" % (s // 3600)
    days = s // 86400
    if days < 30:
        return "%d дн. назад" % days
    return t.strftime("%d.%m.%Y")


def safe_join(root, rel):
    """Склейка пути с проверкой, что результат остаётся внутри root."""
    root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root, rel.lstrip("/")))
    # root="/" даёт root+os.sep="//" — корень обрабатываем отдельно
    prefix = root if root.endswith(os.sep) else root + os.sep
    if full != root and not full.startswith(prefix):
        raise ValueError("путь вне разрешённой папки")
    return full


def read_text_file(path, limit_bytes=1_500_000):
    with open(path, "rb") as f:
        data = f.read(limit_bytes)
    for enc in ("utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def dir_size(path):
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.lstat(os.path.join(root, f)).st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def parse_multipart(body, content_type):
    """Минимальный парсер multipart/form-data -> [{name, filename, data}]."""
    m = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not m:
        return []
    boundary = m.group(1).encode()
    parts = []
    for chunk in body.split(b"--" + boundary):
        if chunk in (b"", b"--", b"--\r\n"):
            continue
        chunk = chunk.lstrip(b"\r\n")
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        headers = head.decode("utf-8", "replace")
        nm = re.search(r'name="([^"]*)"', headers)
        fn = re.search(r'filename="([^"]*)"', headers)
        parts.append({"name": nm.group(1) if nm else "",
                      "filename": fn.group(1) if fn else "",
                      "data": data})
    return parts
