# -*- coding: utf-8 -*-
"""Настройки установленного ПО (раздел «Настройки ПО»).

Для каждой службы из каталога «Установка ПО» (и phpMyAdmin) здесь есть:
  • понятные поля — текущие значения читаются из конфигов/СУБД, при
    сохранении панель пишет управляемый конфиг (drop-in / правка строк);
  • редактор главных конфигов: перед применением бэкап, проверка
    синтаксиса реальными бинарниками (nginx -t, apachectl configtest,
    postfix check, dovecot -n, fail2ban-client -t, php -l), при ошибке
    или если служба не поднялась — автоматический откат;
  • смена паролей: Redis (requirepass), MariaDB (root по TCP, unix_socket
    для панели сохраняется), PostgreSQL (postgres), phpMyAdmin (basic-auth).

Все изменения пишутся в журнал панели. В демо-режиме дисковые конфиги
не трогаются — возвращается демо-ответ.
"""
import os
import re
import secrets
import shutil
import string
import time

from .. import config, utils
from ..context import CTX, have, run
from . import software as sw
from . import files as files_mod
from . import confeditor

CONFIG_BACKUPS = "config-backups"


# ------------------------------------------------------------ помощники ---
def _backup_dir(entry_id):
    d = os.path.join(CTX.home, CONFIG_BACKUPS, entry_id)
    os.makedirs(d, exist_ok=True)
    return d


def _ts_backup(entry_id, path):
    """Тimestamped-копия конфига перед изменением."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = os.path.basename(path) + "." + stamp
    dest = os.path.join(_backup_dir(entry_id), name)
    try:
        shutil.copy2(path, dest)
        os.chmod(dest, 0o600)
        return dest
    except OSError:
        return ""


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _cfg_set(content, key, value):
    """Правка одной директивы key value в конфиге: заменяем существующую
    раскомментированную строку, иначе дописываем управляемый блок.
    Пустое value — директива удаляется."""
    full = r"^(\s*)(#?\s*)%s(\s+.*|\s*)$" % re.escape(key)
    if value == "":
        return re.sub(full + r"\n?", "", content, flags=re.MULTILINE)
    rx = re.compile(full, re.MULTILINE)
    if rx.search(content):
        # lambda-replacement: значение с backslash не трактуется
        # как подстановка групп re
        return rx.sub(lambda m: "%s%s %s" % (m.group(1), key, value),
                      content, count=1)
    # повторные вхождения ключа гасим (последнее значение должно выиграть)
    content = re.sub(r"^(\s*)#?\s*%s(\s+.*|\s*)$\n?" % re.escape(key),
                     "", content, flags=re.MULTILINE)
    if not content.endswith("\n"):
        content += "\n"
    return content + "# -- HostPanel --\n%s %s\n" % (key, value)


def _cfg_get(content, key, default=""):
    # два формата: «key value» (redis/memcached) и «key = value» (INI:
    # fail2ban) — иначе int('= 600') ронял страницу «Настройки ПО»
    m = re.search(r"^\s*#?\s*%s(?:\s*=\s*|\s+)(.+?)\s*$" % re.escape(key),
                  content, re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else default


def _mem_to_mb(text, default):
    m = re.match(r"^(\d+)\s*([kKmMgG]?)(b?B?)?$", str(text).strip())
    if not m:
        return default
    n = int(m.group(1))
    mult = {"k": 1 / 1024.0, "": 1 / (1024.0 * 1024.0), "m": 1, "g": 1024}
    return int(round(n * mult.get(m.group(2).lower(), 1)))


def _restart(units, timeout=90):
    """Перезапуск и проверка, что служба поднялась. False — если нет.

    Type=simple-юниты считаются active сразу после fork — процесс может
    упасть через полсекунды при разборе конфига. Поэтому проверяем
    is-active дважды с паузой: пережить мгновенный crash при старте."""
    for unit in units:
        run(["systemctl", "restart", unit], as_root=True, timeout=timeout)
        state = ""
        for _check in (0.4, 1.6):
            time.sleep(_check)
            _code, out, _ = run(["systemctl", "is-active", unit], timeout=10)
            state = out.strip()
            if state == "active":
                break
            # activating/reloading — служба ещё стартует, даём вторую паузу;
            # failed/inactive — однозначный провал
            if state not in ("activating", "reloading"):
                return False
        if state != "active":
            return False
    return True


def _apply_files(entry, files, label):
    """Бэкап → запись → рестарт → откат при провале.
    files: [(path, content)]. Возвращает (ok, message)."""
    if CTX.demo:
        return True, ("демо: настройки «%s» сохранены (на диске ничего "
                      "не менялось)" % label)
    backups = {}
    for path, content in files:
        if os.path.exists(path):
            backups[path] = _ts_backup(entry["id"], path)
            shutil.copy2(path, path + ".hp-bak")
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    if not _restart(entry.get("units", [])):
        for path, _content in files:
            if path in backups:
                shutil.copy2(backups[path], path)
            elif os.path.exists(path):
                os.remove(path)
        _restart(entry.get("units", []))
        return False, ("служба %s не запустилась с новыми настройками — "
                       "всё откачено к прежним значениям"
                       % ", ".join(entry.get("units", [])))
    return True, "настройки «%s» сохранены, %s перезапущен" % (
        label, ", ".join(entry.get("units", [])))


def _validators():
    """Проверки синтаксиса для файлов по имени."""
    from . import templates

    def v_nginx(path):
        return (True, "") if templates.validate_nginx() \
            else (False, "nginx -t: ошибка в конфигурации")

    def v_apache(path):
        return (True, "") if templates.validate_apache() \
            else (False, "apachectl configtest: ошибка в конфигурации")

    def v_postfix(path):
        code, _o, e = run(["postfix", "check"], timeout=30, as_root=True)
        return (True, "") if code == 0 \
            else (False, "postfix check: %s" % (e or "ошибка").strip()[:200])

    def v_dovecot(path):
        code, _o, e = run(["dovecot", "-n"], timeout=30)
        return (True, "") if code == 0 \
            else (False, "dovecot -n: %s" % (e or "ошибка").strip()[:200])

    def v_fail2ban(path):
        code, _o, e = run(["fail2ban-client", "-t"], timeout=30)
        return (True, "") if code == 0 \
            else (False, "fail2ban-client -t: %s"
                  % (e or "ошибка").strip()[:200])

    def v_php(path):
        # lint тем PHP, что есть в системе (обычно совпадает с версией сайта)
        for ver in ("8.4", "8.3", "8.2", "8.1", "8.0", "7.4"):
            if have("php" + ver):
                code, _o, e = run(["php" + ver, "-l", path], timeout=30)
                return (True, "") if code == 0 else \
                    (False, ("php -l: %s" % e).strip()[:200])
        return True, ""

    def v_fpm(path):
        from . import confeditor
        errors = confeditor.validate_fpm(_read_text(path))
        return (True, "") if not errors else \
            (False, "; ".join(errors)[:200])

    def v_none(path):
        return True, ""

    return {"nginx": v_nginx, "apache": v_apache, "postfix": v_postfix,
            "dovecot": v_dovecot, "fail2ban": v_fail2ban, "php": v_php,
            "fpm": v_fpm, "ini": v_none, "conf": v_none,
            "none": v_none}


# ------------------------------------------------------- текущие значения ---
def _mariadb_values():
    d = {"max_connections": 100, "innodb_buffer_pool_size": 128,
         "bind_address": "127.0.0.1", "character_set_server": "utf8mb4",
         "slow_query_log": False, "long_query_time": 2}
    if CTX.demo:
        return dict(d, max_connections=150, innodb_buffer_pool_size=512,
                    slow_query_log=True)
    code, out, _e = run(["mysql", "-Nse",
                         "SELECT @@global.max_connections,"
                         " @@global.innodb_buffer_pool_size,"
                         " @@global.bind_address,"
                         " @@global.character_set_server,"
                         " @@global.slow_query_log,"
                         " @@global.long_query_time"], timeout=30)
    if code == 0 and out.count("\t") >= 5:
        p = out.strip().split("\t")
        try:
            d["max_connections"] = int(p[0])
            d["innodb_buffer_pool_size"] = max(16, int(round(int(p[1])
                                                            / 1048576)))
            d["bind_address"] = p[2] or "127.0.0.1"
            d["character_set_server"] = p[3] or "utf8mb4"
            d["slow_query_log"] = p[4] == "1"
            d["long_query_time"] = float(p[5])
        except (ValueError, IndexError):
            pass
    return d


def _mariadb_apply(vals):
    lines = ["# Управляемый конфиг HostPanel — правится в разделе "
             "«Настройки ПО»", "[mysqld]",
             "max_connections = %d" % int(vals["max_connections"]),
             "innodb_buffer_pool_size = %dM"
             % int(vals["innodb_buffer_pool_size"]),
             "bind_address = %s" % vals["bind_address"],
             "character_set_server = %s" % vals["character_set_server"],
             "slow_query_log = %s"
             % ("ON" if vals["slow_query_log"] else "OFF"),
             "long_query_time = %s" % vals["long_query_time"]]
    return [("/etc/mysql/mariadb.conf.d/99-hostpanel.cnf",
             "\n".join(lines) + "\n")]


def _postgresql_version():
    if os.path.isdir("/etc/postgresql"):
        for v in sorted(os.listdir("/etc/postgresql"), reverse=True):
            if re.match(r"^\d+(\.\d+)?$", v):
                return v
    return ""


def _postgresql_values():
    d = {"max_connections": 100, "shared_buffers": 128,
         "effective_cache_size": 4096, "listen_addresses": "localhost"}
    if CTX.demo:
        return dict(d, max_connections=200, shared_buffers=256)
    ver = _postgresql_version()
    if not ver:
        return d
    code, out, _e = run(["su", "-", "postgres", "-c",
                         "psql -tAc \"show max_connections; show "
                         "shared_buffers; show effective_cache_size; show "
                         "listen_addresses\""], timeout=30)
    if code == 0 and len(out.strip().splitlines()) >= 4:
        p = [x.strip() for x in out.strip().splitlines()][:4]
        try:
            d["max_connections"] = int(p[0])
            d["shared_buffers"] = _mem_to_mb(p[1], d["shared_buffers"])
            d["effective_cache_size"] = _mem_to_mb(p[2],
                                                   d["effective_cache_size"])
            d["listen_addresses"] = p[3] or "localhost"
        except ValueError:
            pass
    return d


def _postgresql_apply(vals):
    ver = _postgresql_version()
    if not ver:
        return []
    lines = ["# Управляемый конфиг HostPanel — правится в разделе "
             "«Настройки ПО»",
             "max_connections = %d" % int(vals["max_connections"]),
             "shared_buffers = %dMB" % int(vals["shared_buffers"]),
             "effective_cache_size = %dMB"
             % int(vals["effective_cache_size"]),
             "listen_addresses = '%s'" % vals["listen_addresses"]]
    main = "/etc/postgresql/%s/main/postgresql.conf" % ver
    files = [("/etc/postgresql/%s/main/conf.d/99-hostpanel.conf" % ver,
              "\n".join(lines) + "\n")]
    conf = _read_text(main)
    if conf and "conf.d" not in conf:
        with open(main, "a", encoding="utf-8") as f:
            f.write("\ninclude_dir = 'conf.d'\n")
    return files


def _redis_values():
    d = {"maxmemory": 0, "maxmemory_policy": "noeviction",
         "bind": "127.0.0.1", "appendonly": False}
    if CTX.demo:
        return dict(d, maxmemory=256, maxmemory_policy="allkeys-lru")
    conf = _read_text("/etc/redis/redis.conf")
    if not conf:
        return d
    raw = _cfg_get(conf, "bind", "127.0.0.1")
    d["bind"] = "0.0.0.0" if "0.0.0.0" in raw else "127.0.0.1"
    d["maxmemory"] = _mem_to_mb(_cfg_get(conf, "maxmemory", "0"), 0)
    d["maxmemory_policy"] = _cfg_get(conf, "maxmemory-policy",
                                     "noeviction")
    d["appendonly"] = _cfg_get(conf, "appendonly", "no").lower() == "yes"
    return d


def _redis_apply(vals):
    conf = _read_text("/etc/redis/redis.conf")
    if not conf:
        if CTX.demo:
            conf = "# демо-конфиг Redis\n"
        else:
            return []
    bind = "bind 0.0.0.0" if vals["bind"] == "0.0.0.0" \
        else "bind 127.0.0.1 ::1"
    conf = _cfg_set(conf, "bind", bind.split(" ", 1)[1])
    conf = _cfg_set(conf, "maxmemory",
                    "%dmb" % int(vals["maxmemory"]))
    conf = _cfg_set(conf, "maxmemory-policy", vals["maxmemory_policy"])
    conf = _cfg_set(conf, "appendonly",
                    "yes" if vals["appendonly"] else "no")
    return [("/etc/redis/redis.conf", conf)]


def _memcached_values():
    d = {"memory": 64, "port": 11211, "listen": "127.0.0.1",
         "maxconn": 1024}
    if CTX.demo:
        return dict(d, memory=256)
    conf = _read_text("/etc/memcached.conf")
    if not conf:
        return d
    for line in conf.splitlines():
        m = re.match(r"^-(m|p|l|c)\s+(.+?)\s*$", line.strip())
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if k == "m":
            d["memory"] = int(v)
        elif k == "p":
            d["port"] = int(v)
        elif k == "l":
            d["listen"] = "0.0.0.0" if "0.0.0.0" in v else "127.0.0.1"
        elif k == "c":
            d["maxconn"] = int(v)
    return d


def _memcached_apply(vals):
    conf = _read_text("/etc/memcached.conf")
    if not conf:
        conf = "# memcached — настройка в панели HostPanel\n"
    lines = []
    for line in conf.splitlines():
        key = line.strip()[:2]
        if key == "-m":
            lines.append("-m %d" % int(vals["memory"]))
        elif key == "-p":
            lines.append("-p %d" % int(vals["port"]))
        elif key == "-l":
            lines.append("-l %s" % vals["listen"])
        elif key == "-c":
            lines.append("-c %d" % int(vals["maxconn"]))
        else:
            lines.append(line)
    return [("/etc/memcached.conf", "\n".join(lines) + "\n")]


def _postfix_values():
    d = {"myhostname": "", "inet_interfaces": "all",
         "message_size_limit": 10, "mydestination": ""}
    if CTX.demo:
        return dict(d, myhostname="mail.example.ru",
                    mydestination="example.ru, localhost")
    for key in ("myhostname", "inet_interfaces", "message_size_limit",
                "mydestination"):
        code, out, _e = run(["postconf", "-h", key], timeout=15)
        if code == 0 and out.strip():
            v = out.strip()
            d[key] = int(round(int(v) / 1048576)) \
                if key == "message_size_limit" and v.isdigit() else v
    return d


def _postfix_apply(vals):
    mb = int(vals["message_size_limit"]) * 1024 * 1024
    cmds = [["postconf", "-e", "myhostname=%s" % vals["myhostname"]],
            ["postconf", "-e",
             "inet_interfaces=%s" % vals["inet_interfaces"]],
            ["postconf", "-e", "message_size_limit=%d" % mb],
            ["postconf", "-e", "mydestination=%s" % vals["mydestination"]]]
    if not CTX.demo:
        for c in cmds:
            run(c, timeout=30, as_root=True)
    return []


F2B_DROPIN = "/etc/fail2ban/jail.d/hostpanel-defaults.local"


def _fail2ban_values():
    d = {"bantime": 600, "findtime": 600, "maxretry": 5, "ignoreip": "",
         "destemail": "root@localhost"}
    if CTX.demo:
        return dict(d, bantime=3600, maxretry=4)
    # читаем сначала свой drop-in, потом jail.local (для истории)
    conf = _read_text(F2B_DROPIN) or _read_text("/etc/fail2ban/jail.local")
    if not conf:
        return d
    for key in d:
        v = _cfg_get(conf, key, "")
        if v:
            d[key] = int(v) if isinstance(d[key], int) else v
    return d


def _fail2ban_apply(vals):
    # пишем ТОЛЬКО свой drop-in jail.d/hostpanel-defaults.local: полный
    # перезаписью jail.local раньше уничтожались пользовательские jail'ы.
    # INI-формат: разделитель «ключ = значение» (не «ключ значение»).
    path = F2B_DROPIN
    lines = ["# HostPanel: основные параметры блокировки", "[DEFAULT]"]
    for key in ("bantime", "findtime", "maxretry", "ignoreip", "destemail"):
        if str(vals.get(key) or "").strip():
            lines.append("%s = %s" % (key, str(vals[key]).strip()))
    return [(path, "\n".join(lines) + "\n")]


# ------------------------------------------------------------ реестр ------
def _installed_fn(catalog_id):
    def fn():
        if CTX.demo:
            return True
        item = sw.CATALOG_BY_ID.get(catalog_id)
        return bool(item) and sw.item_status(item) != "missing"
    return fn


def _php_files(ver):
    return [{"name": "www.conf (пул FPM)",
             "path": "/etc/php/%s/fpm/pool.d/www.conf" % ver,
             "kind": "fpm"}]


# ------------------------------------------------------------ PHP (php.ini) ---
PHP_FIELDS = (
    "memory_limit", "upload_max_filesize", "post_max_size",
    "max_execution_time", "max_input_vars", "display_errors",
    "opcache.enable", "date.timezone")


def _php_entry(ver):
    """Запись «Настроек ПО» для одной версии PHP: ключевые директивы
    глобального php.ini (FPM) понятными полями + редакторы конфигов."""
    return {
        "id": "php" + ver.replace(".", ""),
        "name": "PHP " + ver + " (FPM)", "group": "PHP",
        "units": ["php" + ver + "-fpm"],
        "catalog": "php" + ver.replace(".", ""),
        "installed": (lambda v=ver: have("php" + v)),
        "get": (lambda v=ver: _php_values(v)),
        "apply": (lambda vals, v=ver: _php_apply(v, vals)),
        "fields": [
            {"key": "memory_limit", "label": "Память на один скрипт",
             "type": "choice",
             "options": ["128M", "256M", "512M", "1024M", "2048M"],
             "hint": "сколько RAM может съесть один PHP-процесс; для "
                     "WordPress обычно 256M"},
            {"key": "upload_max_filesize", "label": "Максимальный размер "
             "загружаемого файла", "type": "choice",
             "options": ["2M", "8M", "16M", "32M", "64M", "128M"],
             "hint": "не больше post_max_size"},
            {"key": "post_max_size", "label": "Максимум POST-запроса",
             "type": "choice",
             "options": ["8M", "16M", "32M", "64M", "128M", "256M"]},
            {"key": "max_execution_time", "label": "Время выполнения "
             "скрипта, сек", "type": "int", "min": 1, "max": 86400,
             "hint": "долгие импорты/парсеры требуют больше 30"},
            {"key": "max_input_vars", "label": "Переменных во входе",
             "type": "int", "min": 100, "max": 100000,
             "hint": "увеличивают для больших форм WooCommerce"},
            {"key": "display_errors", "label": "Показывать ошибки на "
             "странице", "type": "choice", "options": ["Off", "On"],
             "hint": "на рабочем сайте держите Off"},
            {"key": "opcache.enable", "label": "Кэш байткода (opcache)",
             "type": "choice", "options": ["1", "0"],
             "hint": "ускоряет PHP в разы — не выключайте без причины"},
            {"key": "date.timezone", "label": "Часовой пояс",
             "type": "str", "hint": "например, Europe/Moscow; пусто — "
             "не менять"},
        ],
        "files": [{"name": "php.ini (FPM)",
                   "path": confeditor.php_ini_path(ver), "kind": "ini"}]
                  + _php_files(ver),
        "passwords": [],
        "note": "Глобальные настройки для всех сайтов на этой версии PHP. "
                "Индивидуальные настройки сайта — в его карточке, вкладка "
                "«PHP и FPM». При сохранении панель перезапускает FPM и "
                "откатывает изменения, если он не поднялся.",
    }


def _php_values(ver):
    """Текущие значения директив из php.ini (FPM); None — нет в файле."""
    path = confeditor.php_ini_path(ver)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        text = ""
    vals = {k: None for k in PHP_FIELDS}
    # только раскомментированные строки: в ini действует последнее значение
    for m in re.finditer(r"^([A-Za-z0-9._]+)\s*=\s*(.*?)\s*$", text, re.M):
        k, v = m.group(1), m.group(2).strip().strip('"')
        if k in vals and v:
            vals[k] = v
    if vals["display_errors"]:
        vals["display_errors"] = ("On" if vals["display_errors"].lower()
                                  in ("1", "on", "true") else "Off")
    if vals["opcache.enable"]:
        vals["opcache.enable"] = ("1" if vals["opcache.enable"].lower()
                                  in ("1", "on", "true") else "0")
    return vals


def _php_apply(ver, vals):
    """Правит директивы в php.ini: активная строка заменяется, закомм. —
    раскомментируется (первое вхождение), остальные вхождения гасятся
    комментарием (в ini действует последнее значение), отсутствующие —
    дописываются в секцию [PHP]. Возвращает [(путь, новое содержимое)]."""
    path = confeditor.php_ini_path(ver)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        text = ""
    wanted = {}
    for k, v in vals.items():
        if v is None or v == "":
            continue
        wanted[k] = ("1" if v else "0") if isinstance(v, bool) else str(v)
    out, seen = [], set()
    for ln in text.splitlines():
        m_act = re.match(r"^([A-Za-z0-9._]+)\s*=.*$", ln)
        m_com = re.match(r"^;\s*([A-Za-z0-9._]+)\s*=.*$", ln)
        key = m_act.group(1) if m_act else \
            (m_com.group(1) if m_com else None)
        if key and key in wanted:
            if key not in seen:
                seen.add(key)
                out.append("%s = %s" % (key, wanted[key]))
            elif m_act:
                out.append("; HostPanel: дубль отключён — " + ln)
            else:
                out.append(ln)
            continue
        out.append(ln)
    missing = [k for k in wanted if k not in seen]
    if missing:
        block = ["", "; HostPanel: добавлено из «Настроек ПО»"]
        block += ["%s = %s" % (k, wanted[k]) for k in missing]
        # вставляем сразу после [PHP], чтобы строки не попали в секцию
        # другого расширения (в php.ini секции влияют на область действия)
        idx = None
        for i, ln in enumerate(out):
            if ln.strip() == "[PHP]":
                idx = i + 1
                break
        out = (out[:idx] + block + out[idx:]) if idx is not None \
            else block + out
    eol = "\n" if text.endswith("\n") or not text else ""
    return [(path, "\n".join(out) + eol)]


def _entries():
    """Реестр настраиваемого ПО. Функции — чтобы не дёргать систему при
    импорте модуля."""
    php_files = {v: _php_files(v) for v in
                 ("7.4", "8.0", "8.1", "8.2", "8.3", "8.4", "8.5")}
    entries = {
        "mariadb": {
            "id": "mariadb", "name": "MariaDB", "group": "Базы данных",
            "units": ["mariadb"], "catalog": "mariadb",
            "installed": _installed_fn("mariadb"),
            "get": _mariadb_values, "apply": _mariadb_apply,
            "fields": [
                {"key": "max_connections", "label": "Одновременных "
                 "подключений", "type": "int", "min": 10, "max": 10000,
                 "hint": "сколько приложений могут держать соединения "
                         "одновременно"},
                {"key": "innodb_buffer_pool_size", "label": "Память под "
                 "данные, МБ", "type": "int", "min": 16, "max": 65536,
                 "hint": "главный параметр производительности; обычно "
                         "50–70% всей памяти сервера"},
                {"key": "bind_address", "label": "Прослушивать адрес",
                 "type": "choice",
                 "options": ["127.0.0.1", "0.0.0.0"],
                 "hint": "127.0.0.1 — только локальные приложения "
                         "(безопаснее)"},
                {"key": "character_set_server", "label": "Кодировка",
                 "type": "choice",
                 "options": ["utf8mb4", "utf8", "latin1", "cp1251"]},
                {"key": "slow_query_log", "label": "Журнал медленных "
                 "запросов", "type": "bool"},
                {"key": "long_query_time", "label": "«Медленный» запрос, "
                 "сек", "type": "float", "min": 0, "max": 3600},
            ],
            "files": [{"name": "50-server.cnf (основной конфиг)",
                       "path": "/etc/mysql/mariadb.conf.d/50-server.cnf",
                       "kind": "ini"}],
            "passwords": [{"key": "root", "label": "Пароль root для "
                           "внешних подключений (TCP)",
                           "hint": "панель и локальные приложения работают "
                                   "через unix-сокет и не требуют пароля"}],
            "note": "Панель подключается к MariaDB через unix-socket — "
                    "смена пароля root по TCP на её работу не влияет.",
        },
        "postgresql": {
            "id": "postgresql", "name": "PostgreSQL", "group": "Базы данных",
            "units": ["postgresql"], "catalog": "postgresql",
            "installed": _installed_fn("postgresql"),
            "get": _postgresql_values, "apply": _postgresql_apply,
            "fields": [
                {"key": "max_connections", "label": "Одновременных "
                 "подключений", "type": "int", "min": 10, "max": 10000},
                {"key": "shared_buffers", "label": "Память под данные, МБ",
                 "type": "int", "min": 16, "max": 65536,
                 "hint": "обычно 25% памяти сервера"},
                {"key": "effective_cache_size", "label": "Кэш ОС (оценка), "
                 "МБ", "type": "int", "min": 16, "max": 131072,
                 "hint": "подсказка планировщику; обычно 50–75% памяти"},
                {"key": "listen_addresses", "label": "Прослушивать адрес",
                 "type": "choice", "options": ["localhost", "*"],
                 "hint": "localhost — только локальные подключения"},
            ],
            "files": [],
            "passwords": [{"key": "postgres", "label": "Пароль "
                           "пользователя postgres",
                           "hint": "для подключений по сети; локально "
                                   "psql работает через peer-авторизацию"}],
            "note": "",
        },
        "redis": {
            "id": "redis", "name": "Redis", "group": "Кэш и очереди",
            "units": ["redis-server"], "catalog": "redis",
            "installed": _installed_fn("redis"),
            "get": _redis_values, "apply": _redis_apply,
            "fields": [
                {"key": "maxmemory", "label": "Лимит памяти, МБ "
                 "(0 — без лимита)", "type": "int", "min": 0, "max": 262144},
                {"key": "maxmemory_policy", "label": "Что делать при "
                 "переполнении", "type": "choice",
                 "options": ["noeviction", "allkeys-lru", "allkeys-lfu",
                             "volatile-lru", "allkeys-random",
                             "volatile-ttl"],
                 "hint": "для кэша обычно allkeys-lru — вытеснять старые "
                         "ключи"},
                {"key": "bind", "label": "Прослушивать адрес",
                 "type": "choice", "options": ["127.0.0.1", "0.0.0.0"],
                 "hint": "127.0.0.1 — только локальные приложения"},
                {"key": "appendonly", "label": "Сохранять данные на диск "
                 "(AOF)", "type": "bool"},
            ],
            "files": [{"name": "redis.conf", "path": "/etc/redis/redis.conf",
                       "kind": "conf"}],
            "passwords": [{"key": "requirepass", "label": "Пароль "
                           "подключения (requirepass)",
                           "hint": "обязательно, если разрешаете внешние "
                                   "подключения"}],
            "note": "",
        },
        "memcached": {
            "id": "memcached", "name": "Memcached", "group": "Кэш и очереди",
            "units": ["memcached"], "catalog": "memcached",
            "installed": _installed_fn("memcached"),
            "get": _memcached_values, "apply": _memcached_apply,
            "fields": [
                {"key": "memory", "label": "Память, МБ", "type": "int",
                 "min": 8, "max": 65536},
                {"key": "port", "label": "Порт", "type": "int",
                 "min": 1, "max": 65535},
                {"key": "listen", "label": "Прослушивать адрес",
                 "type": "choice", "options": ["127.0.0.1", "0.0.0.0"]},
                {"key": "maxconn", "label": "Максимум подключений",
                 "type": "int", "min": 16, "max": 65535},
            ],
            "files": [],
            "passwords": [],
            "note": "Memcached не имеет пароля: не включайте прослушивание "
                    "0.0.0.0, если порт закрыт брандмауэром.",
        },
        "postfix": {
            "id": "postfix", "name": "Postfix (SMTP)",
            "group": "Почта", "units": ["postfix"], "catalog": "postfix",
            "installed": _installed_fn("postfix"),
            "get": _postfix_values, "apply": _postfix_apply,
            "fields": [
                {"key": "myhostname", "label": "Имя почтового сервера "
                 "(myhostname)", "type": "hostname"},
                {"key": "inet_interfaces", "label": "Принимать почту",
                 "type": "choice", "options": ["all", "loopback-only"]},
                {"key": "message_size_limit", "label": "Максимальный "
                 "размер письма, МБ", "type": "int", "min": 1, "max": 512},
                {"key": "mydestination", "label": "Локальные домены "
                 "(mydestination)", "type": "str",
                 "hint": "домены, которые сервер считает «своими»; "
                         "виртуальные домены — в разделе «Почта»"},
            ],
            "files": [{"name": "main.cf", "path": "/etc/postfix/main.cf",
                       "kind": "postfix"}],
            "passwords": [],
            "note": "Ящики и домены управляются в разделе «Почта».",
        },
        "dovecot": {
            "id": "dovecot", "name": "Dovecot (IMAP/POP3)",
            "group": "Почта", "units": ["dovecot"], "catalog": "dovecot",
            "installed": _installed_fn("dovecot"),
            "get": lambda: {}, "apply": lambda vals: [],
            "fields": [],
            "files": [{"name": "dovecot.conf",
                       "path": "/etc/dovecot/dovecot.conf",
                       "kind": "dovecot"}],
            "passwords": [],
            "note": "",
        },
        "nginx": {
            "id": "nginx", "name": "nginx", "group": "Веб-серверы",
            "units": ["nginx"], "catalog": "nginx",
            "installed": _installed_fn("nginx"),
            "get": lambda: {}, "apply": lambda vals: [],
            "fields": [],
            "files": [{"name": "nginx.conf", "path": "/etc/nginx/nginx.conf",
                       "kind": "nginx"}],
            "passwords": [],
            "note": "Конфиги сайтов редактируются на странице каждого "
                    "сайта; здесь — глобальный конфиг.",
        },
        "apache": {
            "id": "apache", "name": "Apache 2.4", "group": "Веб-серверы",
            "units": ["apache2"], "catalog": "apache",
            "installed": _installed_fn("apache"),
            "get": lambda: {}, "apply": lambda vals: [],
            "fields": [],
            "files": [{"name": "apache2.conf",
                       "path": "/etc/apache2/apache2.conf",
                       "kind": "apache"},
                      {"name": "ports.conf",
                       "path": "/etc/apache2/ports.conf",
                       "kind": "apache"}],
            "passwords": [],
            "note": "Apache работает backend-ом на порту 8081.",
        },
        "fail2ban": {
            "id": "fail2ban", "name": "Fail2ban",
            "group": "SSL и безопасность", "units": ["fail2ban"],
            "catalog": "fail2ban",
            "installed": _installed_fn("fail2ban"),
            "get": _fail2ban_values, "apply": _fail2ban_apply,
            "fields": [
                {"key": "bantime", "label": "Длительность блокировки, сек",
                 "type": "int", "min": 60, "max": 2592000},
                {"key": "findtime", "label": "Окно подсчёта попыток, сек",
                 "type": "int", "min": 60, "max": 86400},
                {"key": "maxretry", "label": "Попыток до блокировки",
                 "type": "int", "min": 1, "max": 100},
                {"key": "ignoreip", "label": "Не блокировать IP",
                 "type": "str", "hint": "через пробел, например "
                 "127.0.0.1/8 203.0.113.7"},
                {"key": "destemail", "label": "E-mail для уведомлений",
                 "type": "email"},
            ],
            "files": [{"name": "jail.local",
                       "path": "/etc/fail2ban/jail.local",
                       "kind": "fail2ban"}],
            "passwords": [],
            "note": "",
        },
    }
    # PHP: по записи на каждую версию — фронт показывает только
    # установленные (installed()), пустых записей не будет
    for _v in ("7.4", "8.0", "8.1", "8.2", "8.3", "8.4", "8.5"):
        entries["php" + _v.replace(".", "")] = _php_entry(_v)
    return entries


def _pma_entry():
    """phpMyAdmin появляется в настройках, когда он установлен хотя бы на
    одном сайте: смена пароля basic-auth и редактор config.inc.php."""
    from . import pma
    installs = [r for r in pma.status() if r.get("installed")]
    if not installs:
        return None
    files = []
    for r in installs:
        site = next((s for s in CTX.store.data["sites"]
                     if s["domain"] == r["domain"]), None)
        if site:
            files.append({
                "name": "config.inc.php (%s)" % r["domain"],
                "path": os.path.join(pma._docroot(site), "pma",
                                     "config.inc.php"),
                "kind": "php"})
    return {
        "id": "pma", "name": "phpMyAdmin",
        "group": "Приложения сайтов", "units": [],
        "installed": lambda: True,
        "get": lambda: {}, "apply": lambda vals: [],
        "fields": [],
        "files": files,
        "passwords": [{"key": r["domain"],
                       "label": "Пароль входа (basic-auth) — %s" % r["url"],
                       "hint": "текущий: %s" % (r.get("password")
                                                or "не задан")}
                      for r in installs],
        "note": "Установки phpMyAdmin управляются в разделе «Установка ПО» "
                "(блок «Приложения сайтов»).",
    }


def list_entries():
    """Что показывать: только установленное ПО + phpMyAdmin."""
    out = []
    for e in _entries().values():
        if not e["installed"]():
            continue
        out.append(_entry_view(e, None))
    pma = _pma_entry()
    if pma:
        out.append(_entry_view(pma, None))
    return out


def _entry_view(e, values):
    values = values if values is not None else e["get"]()
    active = None
    if CTX.demo:
        active = True
    elif e["units"]:
        code, out, _ = run(["systemctl", "is-active", e["units"][0]],
                           timeout=10)
        active = out.strip() == "active"
    return {"id": e["id"], "name": e["name"], "group": e["group"],
            "units": e.get("units", []), "active": active,
            "note": e.get("note", ""),
            "fields": [dict(f, value=values.get(f["key"])) for f in
                       e["fields"]],
            "files": e["files"], "passwords": e["passwords"]}


def _find(entry_id):
    if entry_id == "pma":
        return _pma_entry()
    return _entries().get(entry_id)


# ------------------------------------------------------------- поля -------
def _validate_field(f, val):
    """Возвращает (нормализованное значение, ошибка)."""
    t = f["type"]
    if t == "int":
        try:
            v = int(str(val).strip())
        except (TypeError, ValueError):
            return None, "%s: введите число" % f["label"]
        if v < f.get("min", 0) or v > f.get("max", 1 << 40):
            return None, "%s: допустимо %s—%s" % (f["label"], f.get("min"),
                                                  f.get("max"))
        return v, ""
    if t == "float":
        try:
            v = float(str(val).strip().replace(",", "."))
        except (TypeError, ValueError):
            return None, "%s: введите число" % f["label"]
        if v < f.get("min", 0) or v > f.get("max", 1 << 40):
            return None, "%s: допустимо %s—%s" % (f["label"], f.get("min"),
                                                  f.get("max"))
        return v, ""
    if t == "choice":
        if val not in f["options"]:
            return None, "%s: выберите значение из списка" % f["label"]
        return val, ""
    if t == "bool":
        return str(val).strip().lower() in ("1", "true", "on", "yes",
                                            "да", "вкл"), ""
    if t == "hostname":
        v = str(val).strip()
        if v and not re.match(r"^[a-zA-Z0-9.\-]+$", v):
            return None, "%s: недопустимые символы" % f["label"]
        return v, ""
    if t == "email":
        v = str(val).strip()
        if v and (" " in v or "@" not in v):
            return None, "%s: введите адрес почты" % f["label"]
        return v, ""
    v = str(val).strip()
    if ";" in v or "\n" in v or "`" in v or "$(" in v:
        return None, "%s: недопустимые символы" % f["label"]
    return v, ""


def save_fields(entry_id, fields_in):
    e = _find(entry_id)
    if not e:
        return False, "запись не найдена"
    if not e["fields"]:
        return False, "у этой службы нет полей настройки — правьте конфиг"
    vals = {}
    for f in e["fields"]:
        v, err = _validate_field(f, fields_in.get(f["key"]))
        if err:
            return False, err
        vals[f["key"]] = v
    files = e["apply"](vals)
    if not files:
        return True, "настройки применены"
    okc, msg = _apply_files(e, files, e["name"])
    if okc:
        CTX.store.log_action("Настройки ПО «%s» изменены (%s)"
                             % (e["name"],
                                ", ".join(sorted(vals.keys()))))
        CTX.store.save()
    return okc, msg


# ------------------------------------------------------------- файлы ------
def read_file(entry_id, name):
    e = _find(entry_id)
    if not e:
        return None, "", "запись не найдена"
    f = next((x for x in e["files"] if x["name"] == name), None)
    if not f or not f["path"]:
        return None, "", "файл не найден или редактируется в другом разделе"
    if CTX.demo:
        return f, ("# демо-содержимое %s\n# редактирование доступно "
                   "на рабочем сервере" % f["path"]), ""
    if not os.path.exists(f["path"]):
        return f, "", "файл отсутствует"
    text, err = files_mod.read(f["path"])
    return f, (text or ""), err


def save_file(entry_id, name, content):
    e = _find(entry_id)
    if not e:
        return False, "запись не найдена"
    f = next((x for x in e["files"] if x["name"] == name), None)
    if not f or not f["path"]:
        return False, "файл не найден или редактируется в другом разделе"
    if len(content) > 1_500_000:
        return False, "файл слишком большой"
    if CTX.demo:
        return True, "демо: конфиг сохранён (на диске ничего не менялось)"
    backup = _ts_backup(e["id"], f["path"])
    if os.path.exists(f["path"]):
        shutil.copy2(f["path"], f["path"] + ".hp-bak")
    d = os.path.dirname(f["path"])
    if d:
        os.makedirs(d, exist_ok=True)
    try:
        with open(f["path"], "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as ex:
        return False, "не удалось записать: %s" % ex
    vfn = _validators()[f.get("kind", "none") or "none"]
    okc, err = vfn(f["path"])
    if not okc:
        if os.path.exists(f["path"] + ".hp-bak"):
            shutil.copy2(f["path"] + ".hp-bak", f["path"])
        return False, "%s — конфиг откачен, ничего не изменилось" % err
    if e["units"]:
        reloaded = True
        for unit in e["units"]:
            code, _o, _e = run(["systemctl", "reload", unit],
                               as_root=True, timeout=30)
            if code != 0:
                code, _o, _e = run(["systemctl", "restart", unit],
                                   as_root=True, timeout=90)
                reloaded = _restart_ok(unit)
            if not reloaded:
                if backup:
                    shutil.copy2(backup, f["path"])
                run(["systemctl", "restart", unit], as_root=True,
                    timeout=90)
                return False, ("служба %s не поднялась — конфиг откачен"
                               % unit)
    if backup:
        msg = "конфиг сохранён (предыдущая версия: %s)" % backup
    else:
        msg = "конфиг сохранён"
    CTX.store.log_action("Настройки ПО «%s»: сохранён %s"
                         % (e["name"], f["path"]))
    CTX.store.save()
    return True, msg


def _restart_ok(unit):
    code, out, _ = run(["systemctl", "is-active", unit], timeout=10)
    return out.strip() == "active"


def list_backups(entry_id, name):
    e = _find(entry_id)
    if not e:
        return []
    f = next((x for x in e["files"] if x["name"] == name), None)
    if not f:
        return []
    d = _backup_dir(entry_id)
    base = os.path.basename(f["path"]) + "."
    out = []
    for n in sorted(os.listdir(d), reverse=True):
        if n.startswith(base) and len(out) < 20:
            p = os.path.join(d, n)
            out.append({"file": n, "size": os.path.getsize(p),
                        "ts": os.path.getmtime(p)})
    return out


def restore_backup(entry_id, name, backup_file):
    e = _find(entry_id)
    if not e:
        return False, "запись не найдена"
    f = next((x for x in e["files"] if x["name"] == name), None)
    if not f:
        return False, "файл не найден"
    if "/" in backup_file or ".." in backup_file or not backup_file:
        return False, "некорректное имя файла"
    src = os.path.join(_backup_dir(entry_id), backup_file)
    if not os.path.exists(src):
        return False, "копия не найдена"
    if CTX.demo:
        return True, "демо: конфиг восстановлен из копии"
    shutil.copy2(src, f["path"])
    vfn = _validators()[f.get("kind", "none") or "none"]
    okc, err = vfn(f["path"])
    if not okc:
        return False, "восстановленный конфиг не проходит проверку: %s" % err
    for unit in e["units"]:
        run(["systemctl", "reload", unit], as_root=True, timeout=30)
    CTX.store.log_action("Настройки ПО «%s»: %s восстановлен из копии %s"
                         % (e["name"], f["path"], backup_file))
    CTX.store.save()
    return True, "конфиг восстановлен из копии %s" % backup_file


# ------------------------------------------------------------ пароли ------
def _sql_esc(s):
    return s.replace("\\", "\\\\").replace("'", "''")


def set_password(entry_id, key, password="", clear=False):
    """Смена паролей: redis (requirepass), mariadb (root TCP),
    postgresql (postgres), pma (basic-auth установки)."""
    e = _find(entry_id)
    if not e:
        return False, "запись не найдена"
    known = [p["key"] for p in e["passwords"]]
    if key not in known:
        return False, "у этой службы нет пароля «%s»" % key
    if not clear and password and len(password) < 6:
        return False, "пароль слишком короткий — минимум 6 символов"
    if not password and not clear:
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(16))

    if CTX.demo:
        return True, "демо: пароль %s" % ("удалён" if clear else "изменён")

    if entry_id == "pma":
        return _pma_password(key, password)

    if entry_id == "redis":
        conf_path = "/etc/redis/redis.conf"
        conf = _read_text(conf_path)
        if not conf:
            return False, "redis.conf не найден"
        if clear:
            conf = _cfg_set(conf, "requirepass", "")
            okc, msg = _apply_files(e, [(conf_path, conf)], "Redis")
        else:
            conf = _cfg_set(conf, "requirepass", password)
            okc, msg = _apply_files(e, [(conf_path, conf)], "Redis")
        return okc, msg

    if entry_id == "mariadb":
        if clear:
            code, out, err = run(["mysql", "-Nse",
                                  "ALTER USER 'root'@'localhost' "
                                  "IDENTIFIED VIA unix_socket"],
                                 as_root=True, timeout=30)
            okc = code == 0
            return okc, ("пароль root по TCP отключён (остался unix_socket)"
                         if okc else "не удалось: %s" % (err or out)[:200])
        code, out, err = run(["mysql", "-Nse",
                              "ALTER USER 'root'@'localhost' IDENTIFIED VIA "
                              "unix_socket OR mysql_native_password USING "
                              "PASSWORD('%s')" % _sql_esc(password)],
                             as_root=True, timeout=30)
        if code != 0:
            return False, "не удалось: %s" % (err or out)[:200]
        # пароль через окружение, не в argv (виден в ps//proc)
        code, out, err = run(["mysql", "-h", "127.0.0.1", "-uroot",
                              "-Nse", "SELECT 1"], timeout=15,
                             env={"MYSQL_PWD": password})
        if code != 0:
            return False, ("пароль задан, но вход по TCP не прошёл — "
                           "проверьте вручную")
        return True, "пароль root по TCP установлен, unix_socket сохранён"

    if entry_id == "postgresql":
        sql = "ALTER USER postgres WITH PASSWORD '%s';" % _sql_esc(password)
        code, out, err = run(["su", "-", "postgres", "-c",
                              "psql -v ON_ERROR_STOP=1"],
                             input_text=sql, timeout=30)
        if code != 0:
            return False, "не удалось: %s" % (err or out)[:200]
        code, out, _ = run(["psql", "-h", "127.0.0.1", "-U", "postgres",
                            "-tAc", "SELECT 1"],
                           env={"PGPASSWORD": password,
                                "PGHOST": "127.0.0.1"}, timeout=15)
        if code != 0:
            return True, ("пароль изменён, но проверка по TCP не прошла "
                          "(проверьте pg_hba.conf)")
        return True, "пароль пользователя postgres изменён"
    return False, "неподдерживаемая служба"


def _pma_password(domain, password):
    from . import pma as pma_mod
    site = next((s for s in CTX.store.data["sites"]
                 if s["domain"] == domain), None)
    if not site:
        return False, "сайт не найден"
    if not (site.get("apps") or {}).get("pma"):
        return False, "phpMyAdmin не установлен на этом сайте"
    err = pma_mod._write_protection(site, password)
    if err:
        return False, err
    site.setdefault("apps", {}).setdefault("pma", {})["password"] = password
    CTX.store.log_action("Настройки ПО «phpMyAdmin»: изменён пароль входа "
                         "для %s" % domain)
    CTX.store.save()
    if site["webserver"] == "nginx":
        run(["systemctl", "reload", "nginx"], as_root=True, timeout=30)
    return True, ("пароль входа в phpMyAdmin (%s) изменён" % domain)
