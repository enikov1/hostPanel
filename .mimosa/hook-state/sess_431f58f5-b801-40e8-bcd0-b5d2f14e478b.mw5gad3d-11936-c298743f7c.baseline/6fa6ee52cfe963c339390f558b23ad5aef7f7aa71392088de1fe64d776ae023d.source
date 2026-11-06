# -*- coding: utf-8 -*-
"""Редакторы конфигов: php.ini, пул FPM, nginx, apache — с валидацией
перед применением и автоматическим откатом при ошибке.

В демо-режиме все конфиги «живут» в домашней папке панели — редактор
работает с реальными файлами, просто не трогает /etc.
"""
import os
import re
import shutil

from .. import config
from .. import utils
from ..context import CTX, run, have

PHP_INI_RULES = {
    # директива: (тип, допустимый диапазон/значения, описание)
    "memory_limit": ("mem", ("128M", "4G"), "Память на скрипт"),
    "upload_max_filesize": ("mem", ("2M", "1G"), "Максимум загрузки"),
    "post_max_size": ("mem", ("8M", "2G"), "Максимум POST-запроса"),
    "max_execution_time": ("int", (0, 86400), "Время выполнения, сек"),
    "max_input_time": ("int", (-1, 86400), "Время разбора входа, сек"),
    "max_input_vars": ("int", (100, 100000), "Переменных входа"),
    "display_errors": ("bool", None, "Показ ошибок в ответе"),
    "log_errors": ("bool", None, "Журналирование ошибок"),
    "error_reporting": ("str", None, "Уровень ошибок"),
    "error_log": ("str", None, "Файл журнала ошибок"),
    "date.timezone": ("str", None, "Часовой пояс"),
    "opcache.enable": ("bool", None, "Кэш байткода"),
    "opcache.memory_consumption": ("int", (64, 2048), "Память opcache, МБ"),
    "session.gc_maxlifetime": ("int", (60, 2592000), "Жизнь сессии, сек"),
    "expose_php": ("bool", None, "Показывать версию PHP"),
    "allow_url_fopen": ("bool", None, "Открывать URL в функциях файлов"),
    "disable_functions": ("str", None, "Запрещённые функции"),
    "output_buffering": ("int", (0, 65536), "Буфер вывода, байт"),
    "cgi.fix_pathinfo": ("bool", None, "fix_pathinfo (безопасность)"),
}

FPM_RULES = {
    "pm": ("enum", ("dynamic", "static", "ondemand"), "Режим процессов"),
    "pm.max_children": ("int", (1, 10000), "Максимум воркеров"),
    "pm.start_servers": ("int", (1, 10000), "Стартовых воркеров"),
    "pm.min_spare_servers": ("int", (1, 10000), "Мин. запасных"),
    "pm.max_spare_servers": ("int", (1, 10000), "Макс. запасных"),
    "pm.max_requests": ("int", (1, 10000000), "Рестарт воркера после N"),
    "request_terminate_timeout": ("int", (0, 86400), "Убивать после, сек"),
}


def _demo_conf_dir():
    d = os.path.join(CTX.home, "demo_etc")
    for sub in ("php", "nginx", "apache2"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def php_ini_path(version, site=None):
    """Путь к php.ini версии (глобальный fpm php.ini; файлы pool.d/*.ini
    php-fpm не читает). В демо — файлы в домашней папке панели."""
    if CTX.demo:
        d = os.path.join(_demo_conf_dir(), "php", version)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "php.ini")
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(DEMO_PHP_INI)
        return p
    return "/etc/php/%s/fpm/php.ini" % version


def php_version_from_path(path):
    """Версия PHP из пути вида /etc/php/8.3/fpm/… (или '')."""
    m = re.search(r"/etc/php/(\d+\.\d+)/", path or "")
    return m.group(1) if m else ""


def fpm_conf_path(site):
    if CTX.demo:
        from .templates import pool_name
        d = os.path.join(_demo_conf_dir(), "php", site.get("php") or "8.2",
                         "pool.d")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, pool_name(site["domain"]) + ".conf")
    from .templates import fpm_conf_path as real_path
    return real_path(site)


def nginx_conf_path(domain):
    if CTX.demo:
        return os.path.join(_demo_conf_dir(), "nginx", domain + ".conf")
    from .templates import nginx_conf_path as real_path
    return real_path(domain)


def apache_conf_path(domain):
    if CTX.demo:
        return os.path.join(_demo_conf_dir(), "apache2", domain + ".conf")
    from .templates import apache_conf_path as real_path
    return real_path(domain)


DEMO_PHP_INI = """; Демонстрационный php.ini (HostPanel)
[PHP]
memory_limit = 256M
upload_max_filesize = 32M
post_max_size = 48M
max_execution_time = 120
max_input_time = 120
max_input_vars = 3000
display_errors = Off
log_errors = On
error_log = /var/log/hostpanel/php-error.log
date.timezone = Europe/Moscow
expose_php = Off
allow_url_fopen = On
cgi.fix_pathinfo = 0

[opcache]
opcache.enable = 1
opcache.memory_consumption = 192

[Session]
session.gc_maxlifetime = 3600
"""

DEMO_FPM_CONF = """; HostPanel: пул PHP-FPM (демо)
[pool]
user = www-data
group = www-data
pm = dynamic
pm.max_children = 10
pm.start_servers = 3
pm.min_spare_servers = 2
pm.max_spare_servers = 5
pm.max_requests = 500
request_terminate_timeout = 300
"""


def ensure_demo_fpm(site):
    p = fpm_conf_path(site)
    if CTX.demo and not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(DEMO_FPM_CONF)
    return p


DEMO_NGINX_CONF = """# HostPanel: сайт {domain} (демо-конфиг)
server {{
    listen 80;
    server_name {domain} www.{domain};
    root /var/www/{domain}/public_html;
    index index.php index.html index.htm;

    access_log /var/log/hostpanel/{domain}.access.log;
    error_log  /var/log/hostpanel/{domain}.error.log;

    client_max_body_size 64m;

    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php{php}-fpm.sock;
    }}

    location ~ /\\.ht {{ deny all; }}
}}
"""

DEMO_APACHE_CONF = """# HostPanel: сайт {domain} (демо-конфиг)
<VirtualHost *:80>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot /var/www/{domain}/public_html
    <Directory /var/www/{domain}/public_html>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}-error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}-access.log combined
</VirtualHost>
"""


def ensure_demo_nginx(site):
    p = nginx_conf_path(site["domain"])
    if CTX.demo and not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(DEMO_NGINX_CONF.format(
                domain=site["domain"], php=site.get("php") or "8.2"))
    return p


def ensure_demo_apache(site):
    p = apache_conf_path(site["domain"])
    if CTX.demo and not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(DEMO_APACHE_CONF.format(domain=site["domain"]))
    return p


# ------------------------------------------------------------- валидация ---

def validate_ini_rules(text, rules):
    """Проверяет директивы ini-файла по правилам. Возвращает список ошибок."""
    errors = []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#", "[")):
            continue
        if "=" not in stripped:
            errors.append("строка %d: нет знака «=»" % line_no)
            continue
        key, val = stripped.split("=", 1)
        key = key.strip()
        val = val.split(";")[0].strip()
        if key not in rules:
            continue
        kind, rng, _desc = rules[key]
        err = _check_value(kind, rng, key, val)
        if err:
            errors.append("строка %d: %s" % (line_no, err))
    return errors


def _check_value(kind, rng, key, val):
    if kind == "mem" and str(val).strip() == "-1":
        return ""  # -1 = без лимита, валидное значение PHP
    if kind == "bool":
        if val.lower() not in ("on", "off", "true", "false", "1", "0"):
            return "%s: ожидается on/off" % key
        return None
    if kind == "enum":
        if val not in rng:
            return "%s: допустимо %s" % (key, "/".join(rng))
        return None
    if kind == "int":
        try:
            v = int(val)
        except ValueError:
            return "%s: ожидается число" % key
        if not (rng[0] <= v <= rng[1]):
            return "%s: допустимо %d–%d" % (key, rng[0], rng[1])
        return None
    if kind == "mem":
        m = re.match(r"^(\d+)([KMG]?)$", val, re.I)
        if not m:
            return "%s: ожидается число с суффиксом K/M/G" % key
        n = int(m.group(1))
        low = _mem_to_int(rng[0])
        high = _mem_to_int(rng[1])
        if not (low <= n * (1 if not m.group(2) else
                            {"K": 1024, "M": 1024 ** 2,
                             "G": 1024 ** 3}[m.group(2).upper()]) <= high):
            return "%s: допустимо %s–%s" % (key, rng[0], rng[1])
        return None
    return None


def _mem_to_int(s):
    m = re.match(r"^(\d+)([KMG]?)$", s, re.I)
    mult = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    return int(m.group(1)) * mult[m.group(2).upper()]


def validate_php_ini(text):
    return validate_ini_rules(text, PHP_INI_RULES)


def validate_fpm(text):
    errors = []
    if not re.search(r"^\[.+\]", text, re.M):
        errors.append("нет секции [pool]")
    errors += validate_ini_rules(text, FPM_RULES)
    # согласованность pm-значений
    vals = dict(re.findall(r"^(pm(?:\.\w+)?)\s*=\s*(\S+)", text, re.M))
    try:
        mn = int(vals.get("pm.min_spare_servers", 1))
        mx = int(vals.get("pm.max_spare_servers", 5))
        if mn > mx:
            errors.append("pm.min_spare_servers больше pm.max_spare_servers")
        if int(vals.get("pm.start_servers", 2)) > int(
                vals.get("pm.max_children", 10)):
            errors.append("pm.start_servers больше pm.max_children")
    except ValueError:
        errors.append("pm-значения должны быть числами")
    return errors


def validate_nginx(text):
    """Синтаксис проверяется самим nginx -t при применении; здесь —
    грубая проверка баланса скобок и запрет опасных директив."""
    errors = []
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                errors.append("лишняя закрывающая скобка (позиция %d)" % i)
                depth = 0
    if depth != 0:
        errors.append("скобки не сбалансированы: %d незакрытых блоков" % depth)
    for danger in ("include /etc/shadow", "alias /etc/", "root /etc/"):
        if danger in text:
            errors.append("запрещённая директива: %s" % danger)
    return errors


def validate_apache(text):
    errors = []
    for tag in re.findall(r"<(\w+)", text):
        if not re.search(r"</%s>" % tag, text):
            errors.append("нет закрывающего </%s>" % tag)
    return errors


# --------------------------------------------------------------- применение --

def save_php_ini(path, content):
    errors = validate_php_ini(content)
    if errors:
        return False, "; ".join(errors)
    v = php_version_from_path(path)
    services = ["php%s-fpm" % v] if (v and not CTX.demo) else []
    return _save_and_apply(path, content, services)


def save_fpm(path, content):
    errors = validate_fpm(content)
    if errors:
        return False, "; ".join(errors)
    v = php_version_from_path(path)
    if not CTX.demo and v:
        # проверяем синтаксис всех пулов реальным бинарником до применения
        # (бинарник php-fpm8.3, юнит php8.3-fpm)
        code, _out, err = run(["php-fpm" + v, "-t"], timeout=30)
        if code != 0:
            return False, "php-fpm: %s" % (err or "ошибка конфигурации")
        return _save_and_apply(path, content, ["php%s-fpm" % v])
    return _save_and_apply(path, content, [])


def save_nginx(path, content):
    errors = validate_nginx(content)
    if errors:
        return False, "; ".join(errors)
    return _save_and_apply(path, content, ["nginx"])


def save_apache(path, content):
    errors = validate_apache(content)
    if errors:
        return False, "; ".join(errors)
    return _save_and_apply(path, content, ["apache2"])


def _save_and_apply(path, content, services):
    """Сохраняет с бэкапом, проверяет синтаксис, при ошибке откат."""
    backup = None
    if os.path.exists(path):
        backup = path + ".hp-bak"
        shutil.copy2(path, backup)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if CTX.demo:
        return True, "демо: конфиг сохранён"
    # проверка синтаксиса реальными бинарниками
    problems = []
    for svc in services:
        if svc == "nginx":
            from .templates import validate_nginx
            if not validate_nginx():
                problems.append("nginx -t: ошибка")
        elif svc == "apache2" and have("apache2ctl"):
            from .templates import validate_apache
            if not validate_apache():
                problems.append("apachectl configtest: ошибка")
    if problems:
        if backup and os.path.exists(backup):
            shutil.copy2(backup, path)  # откат
            os.remove(backup)
        else:
            # нового файла не было — битый конфиг нельзя оставлять на диске
            try:
                os.remove(path)
            except OSError:
                pass
        return False, "; ".join(problems) + " — конфиг откачен"
    for svc in services:
        run(["systemctl", "reload", svc], timeout=30, as_root=True)
    return True, ""
