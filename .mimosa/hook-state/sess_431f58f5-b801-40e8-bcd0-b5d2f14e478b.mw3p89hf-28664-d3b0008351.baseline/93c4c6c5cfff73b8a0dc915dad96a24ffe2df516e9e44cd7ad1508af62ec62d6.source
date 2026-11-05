# -*- coding: utf-8 -*-
"""Каталог ПО (в духе ISPmanager): установка и удаление служб из панели.

Каждый элемент каталога: id, название, описание, группа, apt-пакеты,
способ проверки наличия (бинарник/юнит) и post-команды после установки
(включение модулей, настройка портов и т.п.).

PHP 7.4–8.5 ставятся из репозитория packages.sury.org (официальный
источник PHP-пакетов для новых Ubuntu/Debian; PPA ondrej/php новые
выпуски Ubuntu не поддерживает). Долгие apt-операции выполняются в фоне
через тот же механизм задач, что и установка PHP-модулей (packages.TASKS).
"""
import os
import re

from ..context import CTX, STATE_LOCK, run, have
from .. import utils

APT_ENV = {"DEBIAN_FRONTEND": "noninteractive"}

# GeoLite2-Country.mmdb: официальная раздача MaxMind требует личного
# ключа, DB-IP из РФ не резолвится — берём автоматически обновляемый
# публичный снимок GeoLite2 (P3TERX/GeoLite.mmdb, daily GitHub Actions).
# Сразу ставим и ежемесячное обновление базы через cron.monthly.
GEO_DB_URL = ("https://github.com/P3TERX/GeoLite.mmdb/releases/"
              "latest/download/GeoLite2-Country.mmdb")
GEO_DB_SH = (
    "mkdir -p /usr/share/GeoIP /etc/cron.monthly && "
    "curl -fsSL --max-time 600 -o /tmp/hp-geodb.mmdb " + GEO_DB_URL + " && "
    "mv /tmp/hp-geodb.mmdb /usr/share/GeoIP/GeoLite2-Country.mmdb && "
    "(systemctl reload nginx || true); "
    "{ echo '#!/bin/sh'; "
    "echo 'curl -fsSL --max-time 600 -o /tmp/hp-geodb.mmdb " + GEO_DB_URL +
    " || exit 0'; "
    "echo 'mv /tmp/hp-geodb.mmdb /usr/share/GeoIP/GeoLite2-Country.mmdb.new"
    " || exit 0'; "
    "echo 'mv /usr/share/GeoIP/GeoLite2-Country.mmdb.new"
    " /usr/share/GeoIP/GeoLite2-Country.mmdb'; "
    "echo 'rm -f /tmp/hp-geodb.mmdb'; "
    "echo 'systemctl reload nginx || true'; "
    "} > /etc/cron.monthly/hostpanel-geodb && "
    "chmod 755 /etc/cron.monthly/hostpanel-geodb")

# подключение репозитория sury (PHP 7.4–8.5) — идемпотентно
ENSURE_SURY = [
    ["bash", "-c",
     "test -s /etc/apt/sources.list.d/php-sury.list || { "
     "(curl -fsSL https://packages.sury.org/php/apt.gpg "
     "-o /etc/apt/trusted.gpg.d/sury.gpg || "
     "wget -qO /etc/apt/trusted.gpg.d/sury.gpg "
     "https://packages.sury.org/php/apt.gpg) && "
     ". /etc/os-release && "
     "echo \"deb https://packages.sury.org/php/ $VERSION_CODENAME main\" "
     "> /etc/apt/sources.list.d/php-sury.list && apt-get update -qq; }"],
]


def _php_item(ver):
    """Элемент каталога для одной версии PHP (FPM + набор модулей).

    Отсутствующие в репозитории пакеты (например, в новых Ubuntu opcache
    встроен в phpX.Y-common) пропускаются при установке с пометкой в логе.
    """
    pkgs = ["php%s-fpm" % ver, "php%s-cli" % ver, "php%s-mysql" % ver,
            "php%s-curl" % ver, "php%s-gd" % ver, "php%s-mbstring" % ver,
            "php%s-xml" % ver, "php%s-zip" % ver, "php%s-bcmath" % ver,
            "php%s-intl" % ver, "php%s-opcache" % ver]
    return {"id": "php" + ver.replace(".", ""), "group": "PHP",
            "name": "PHP %s (FPM + модули)" % ver,
            "desc": "PHP %s из репозитория sury: FPM, mysql, curl, gd, "
                    "mbstring, xml, zip, bcmath, intl, opcache; остальные "
                    "модули — на странице «Пакеты и обновления»" % ver,
            "apt": pkgs, "skip_missing": True,
            "provide_bins": ["php%s" % ver], "provide_units": ["php%s-fpm" % ver],
            "pre_install": ENSURE_SURY,
            "post_install": [["systemctl", "enable", "--now",
                              "php%s-fpm" % ver]]}


# ---------------------------------------------------------------- каталог ---
# provide: (бинарники, юниты systemd) — наличие хотя бы одного из каждой
# категории означает «уже установлен»
CATALOG = [
    {"id": "nginx", "group": "Веб-серверы", "name": "nginx",
     "desc": "Быстрый веб-сервер и reverse-proxy (основной веб-сервер панели)",
     "apt": ["nginx", "libnginx-mod-http-geoip2"],
     "provide_bins": ["nginx"], "provide_units": ["nginx"],
     "post_install": [["systemctl", "enable", "--now", "nginx"]]},
    {"id": "apache", "group": "Веб-серверы", "name": "Apache 2.4",
     "desc": "Классический веб-сервер (backend на порту 8081 для панели)",
     "apt": ["apache2"],
     "provide_bins": ["apache2ctl"], "provide_units": ["apache2"],
     "post_install": [
         ["a2enmod", "proxy_fcgi", "rewrite", "headers", "expires"],
         ["a2dissite", "000-default"],
         ["bash", "-c",
          "grep -q '^Listen 8081' /etc/apache2/ports.conf || "
          "(sed -i 's/^Listen 80$/Listen 8081/' /etc/apache2/ports.conf; "
          "grep -q '^Listen 8081' /etc/apache2/ports.conf || "
          "echo 'Listen 8081' >> /etc/apache2/ports.conf)"],
         ["bash", "-c",
          "echo 'ServerName localhost' > /etc/apache2/conf-available/"
          "servername.conf && a2enconf servername"],
         ["systemctl", "enable", "--now", "apache2"]]},

    _php_item("7.4"), _php_item("8.0"), _php_item("8.1"), _php_item("8.2"),
    _php_item("8.3"), _php_item("8.4"), _php_item("8.5"),
    {"id": "composer", "group": "PHP", "name": "Composer",
     "desc": "Менеджер зависимостей PHP",
     "apt": ["composer"], "provide_bins": ["composer"], "provide_units": []},

    {"id": "mariadb", "group": "Базы данных", "name": "MariaDB",
     "desc": "СУБД MySQL-совместимая (базы создаются в разделе «Базы данных»)",
     "apt": ["mariadb-server", "mariadb-client"],
     "provide_bins": ["mysql"], "provide_units": ["mariadb"],
     "post_install": [["systemctl", "enable", "--now", "mariadb"]]},
    {"id": "postgresql", "group": "Базы данных", "name": "PostgreSQL",
     "desc": "Объектно-реляционная СУБД",
     "apt": ["postgresql", "postgresql-contrib"],
     "provide_bins": ["psql"], "provide_units": ["postgresql"],
     "post_install": [["systemctl", "enable", "--now", "postgresql"]]},
    {"id": "redis", "group": "Кэш и очереди", "name": "Redis",
     "desc": "Хранилище ключ-значение, кэш и очереди",
     "apt": ["redis-server", "php-redis"], "provide_bins": ["redis-cli"],
     "provide_units": ["redis-server"],
     "post_install": [["systemctl", "enable", "--now", "redis-server"]]},
    {"id": "memcached", "group": "Кэш и очереди", "name": "Memcached",
     "desc": "Распределённый кэш в памяти",
     "apt": ["memcached", "php-memcached"], "provide_bins": ["memcached"],
     "provide_units": ["memcached"],
     "post_install": [["systemctl", "enable", "--now", "memcached"]]},

    {"id": "postfix", "group": "Почта", "name": "Postfix (SMTP-сервер)",
     "desc": "Отправка и приём почты (SMTP, порты 25 и 587); виртуальные "
             "домены и ящики настраиваются в разделе «Почта»",
     "apt": ["postfix"],
     "provide_bins": ["postconf"], "provide_units": ["postfix"],
     "post_install": [["systemctl", "enable", "--now", "postfix"]]},
    {"id": "dovecot", "group": "Почта", "name": "Dovecot (IMAP/POP3)",
     "desc": "Доступ к ящикам из почтовых клиентов (IMAP 143/993, "
             "POP3 110/995) + SMTP-авторизация",
     "apt": ["dovecot-core", "dovecot-imapd", "dovecot-pop3d"],
     "provide_bins": ["dovecot"], "provide_units": ["dovecot"],
     "post_install": [["systemctl", "enable", "--now", "dovecot"]]},
    {"id": "mailutils", "group": "Почта", "name": "Mailutils",
     "desc": "Почтовый клиент командной строки (mail) для отправки писем "
             "и тестов доставки из панели",
     "apt": ["mailutils"],
     "provide_bins": ["mail"], "provide_units": []},

    {"id": "certbot", "group": "SSL и безопасность", "name": "Certbot",
     "desc": "Бесплатные сертификаты Let's Encrypt (нужен для SSL сайтов)",
     "apt": ["certbot", "python3-certbot-nginx", "python3-certbot-apache"],
     "provide_bins": ["certbot"], "provide_units": []},
    {"id": "fail2ban", "group": "SSL и безопасность", "name": "Fail2ban",
     "desc": "Автоблокировка подбирающих пароль и сканеров",
     "apt": ["fail2ban"], "provide_bins": ["fail2ban-client"],
     "provide_units": ["fail2ban"],
     "post_install": [["systemctl", "enable", "--now", "fail2ban"]]},
    {"id": "geoip2", "group": "SSL и безопасность",
     "name": "GeoIP2 для nginx (блокировка по странам)",
     "desc": "Модуль ngx_http_geoip2 и база стран GeoLite2 — включает "
             "гео-фильтр на вкладке «Безопасность» каждого сайта. База "
             "свежая, обновляется автоматически раз в месяц",
     "apt": ["libnginx-mod-http-geoip2"],
     "provide_files": ["/usr/lib/nginx/modules/ngx_http_geoip2_module.so",
                       "/usr/share/GeoIP/GeoLite2-Country.mmdb"],
     "post_install": [["bash", "-c", GEO_DB_SH]]},
    {"id": "nodejs", "group": "Инструменты", "name": "Node.js + npm",
     "desc": "Среда выполнения JavaScript (для сайтов nginx + Node.js)",
     "apt": ["nodejs", "npm"], "provide_bins": ["node"], "provide_units": []},
    {"id": "git", "group": "Инструменты", "name": "Git",
     "desc": "Система контроля версий (деплой из репозитория)",
     "apt": ["git"], "provide_bins": ["git"], "provide_units": []},
    {"id": "unzip", "group": "Инструменты", "name": "Архиваторы",
     "desc": "unzip/zip — работа с архивами в файловом менеджере",
     "apt": ["unzip", "zip"], "provide_bins": ["unzip"], "provide_units": []},
]

CATALOG_BY_ID = {c["id"]: c for c in CATALOG}

# чего нельзя сносить, пока панель им пользуется
# (кортеж кортежей: (тип_проверки, аргумент))
DEPENDS = {
    "nginx": (("sites_nginx",),),
    "apache": (("sites_apache",),),
    "php74": (("php_version", "7.4"),),
    "php80": (("php_version", "8.0"),),
    "php81": (("php_version", "8.1"),),
    "php82": (("php_version", "8.2"),),
    "php83": (("php_version", "8.3"),),
    "php84": (("php_version", "8.4"),),
    "php85": (("php_version", "8.5"),),
    "postfix": (("mail_domains",),),
    "dovecot": (("mail_domains",),),
}


def _used_by(kind, arg=""):
    sites = CTX.store.data.get("sites", []) if CTX.store else []
    if kind == "sites_nginx":
        return [s["domain"] for s in sites if s.get("webserver") != "apache"]
    if kind == "sites_apache":
        return [s["domain"] for s in sites
                if "apache" in (s.get("webserver") or "")]
    if kind == "php_version":
        return [s["domain"] for s in sites if s.get("php") == arg]
    if kind == "mail_domains":
        mail = CTX.store.data.get("mail", {}) if CTX.store else {}
        return [d["domain"] for d in mail.get("domains", [])]
    return []


def item_status(item):
    """Статус одного элемента каталога: installed/active/missing."""
    if CTX.demo:
        return "installed"
    has_bin = any(have(b) for b in item.get("provide_bins", []))
    has_unit = False
    for unit in item.get("provide_units", []):
        code, out, _ = run(["systemctl", "is-active", unit], timeout=10)
        # is-active возвращает 0 даже для "inactive"? нет: inactive = 3,
        # но юнит существует — считаем установленным по коду 0/3
        if code in (0, 3) and out.strip() in ("active", "inactive",
                                              "failed"):
            has_unit = True
    has_files = all(os.path.exists(p)
                    for p in item.get("provide_files", []))
    state = "missing"
    if has_bin or has_unit or has_files:
        state = "installed"
        for unit in item.get("provide_units", []):
            code, out, _ = run(["systemctl", "is-active", unit], timeout=10)
            if code == 0 and out.strip() == "active":
                state = "active"
                break
    return state


def catalog():
    """Каталог + статус каждого элемента."""
    return [{"id": c["id"], "group": c["group"], "name": c["name"],
             "desc": c["desc"], "status": item_status(c),
             "apt": " ".join(c["apt"])}
            for c in CATALOG]


def _ensure_apt_lists():
    """Обновляем индексы, если их ещё ни разу не обновляли в панели."""
    st = CTX.store.data.get("packages", {})
    if not st.get("apt_updated"):
        _task_log("apt-get update…")
        run(["apt-get", "update"], timeout=600, as_root=True)
        CTX.store.data.setdefault("packages", {})[
            "apt_updated"] = utils.now_str()
        CTX.store.save()


def _task_log(line):
    from .packages import _task_log as log_line
    log_line(line)


def _run_steps(steps, label):
    for cmd in (steps or []):
        _task_log("%s: %s…" % (label, " ".join(cmd[:3])))
        code, out, err = run(cmd, timeout=900, as_root=True, env=APT_ENV)
        if code != 0:
            _task_log("предупреждение: %s" % ((err or out)[:200]))


def _available_apt(pkgs):
    """Разделяет список пакетов на (доступные, отсутствующие в apt)."""
    present, missing = [], []
    for p in pkgs:
        code, out, _ = run(["apt-cache", "policy", p], timeout=30)
        if code == 0 and ("Кандидат" in (out or "")
                          or "Candidate" in (out or "")):
            present.append(p)
        else:
            missing.append(p)
    return present, missing


def install(name):
    """Устанавливает элемент каталога (в фоне). Возвращает (ok, err)."""
    item = CATALOG_BY_ID.get(name)
    if not item:
        return False, "неизвестный элемент каталога"
    from .packages import _run_bg
    if CTX.demo:
        def demo_job():
            _task_log("демо: установка %s" % item["name"])
            _task_log("готово")
        return _run_bg("software-install", demo_job)

    def job():
        _task_log("Установка %s (%s)…" % (item["name"], " ".join(item["apt"])))
        _ensure_apt_lists()
        _run_steps(item.get("pre_install"), "подготовка")
        pkgs = list(item["apt"])
        if item.get("skip_missing"):
            present, missing = _available_apt(pkgs)
            if missing:
                _task_log("нет в репозиториях (пропускаю): %s"
                          % ", ".join(missing))
            if not present:
                _task_log("ОШИБКА: ни одного доступного пакета")
                CTX.store.notify("Не удалось установить %s" % item["name"],
                                 "error")
                return
            pkgs = present
        code, out, err = run(["apt-get", "install", "-y"] + pkgs,
                             timeout=1800, as_root=True, env=APT_ENV)
        if code != 0:
            _task_log("ОШИБКА: %s" % ((err or out)[:400]))
            CTX.store.notify("Не удалось установить %s" % item["name"],
                             "error")
            return
        _run_steps(item.get("post_install"), "настройка")
        _task_log("готово")
        with STATE_LOCK:
            CTX.store.notify("Установлено: %s" % item["name"])
            CTX.store.log_action("Через каталог ПО установлено: %s"
                                 % item["name"])
            CTX.store.save()
    return _run_bg("software-install", job)


def remove(name):
    """Удаляет элемент каталога (в фоне) с проверкой зависимостей."""
    item = CATALOG_BY_ID.get(name)
    if not item:
        return False, "неизвестный элемент каталога"
    if item_status(item) == "missing":
        return False, "%s и так не установлен" % item["name"]
    for dep in DEPENDS.get(name, ()):
        used = _used_by(dep[0], dep[1] if len(dep) > 1 else "")
        if used:
            return False, ("сначала удалите/переведите сайты: %s"
                           % ", ".join(used[:5]))
    from .packages import _run_bg
    if CTX.demo:
        def demo_job():
            _task_log("демо: удаление %s" % item["name"])
            _task_log("готово")
        return _run_bg("software-remove", demo_job)

    def job():
        _task_log("Удаление %s…" % item["name"])
        code, out, err = run(["apt-get", "purge", "-y"] + item["apt"],
                             timeout=1800, as_root=True, env=APT_ENV)
        if code != 0:
            _task_log("ОШИБКА: %s" % ((err or out)[:400]))
            return
        # зависимости (например, phpX.Y-common) не входят в список пакета,
        # но оставляют /etc/php/X.Y — панель продолжала считать версию
        # установленной; подчищаем автоматически установленные пакеты
        _task_log("очистка зависимостей (autoremove)…")
        run(["apt-get", "autoremove", "--purge", "-y"],
            timeout=1800, as_root=True, env=APT_ENV)
        _task_log("готово")
        with STATE_LOCK:
            CTX.store.notify("Удалено: %s" % item["name"], "warn")
            CTX.store.log_action("Через каталог ПО удалено: %s" % item["name"])
            CTX.store.save()
    return _run_bg("software-remove", job)


def valid_id(name):
    return bool(re.match(r"^[a-z0-9]{1,32}$", name or ""))
