# -*- coding: utf-8 -*-
"""Пакеты: установка PHP-модулей, обновления PHP/модулей/системы (apt).

Долгие операции apt запускаются в фоне с отслеживанием статуса —
UI показывает прогресс и лог операции.
"""
import os
import re
import threading

from ..context import CTX, STATE_LOCK, run, have
from .. import utils

# статус текущей фоновой операции: {running, kind, log, started, queued}
# долгие операции (apt, установка pma, ionCube…) выполняются ПОСЛЕДОВАТЕЛЬНО
# одним рабочим потоком; новые задачи встают в очередь вместо отказа.
TASKS = {"running": False, "kind": "", "log": [], "started": "", "queued": []}
# журнал завершённых фоновых операций (последние 20): виден в UI
TASK_HISTORY = []
TASKS_LOCK = threading.Lock()
_COND = threading.Condition(TASKS_LOCK)
_QUEUE = []          # [(kind, fn)]
_WORKER = None
_QUEUE_LIMIT = 20


def _task_log(line):
    with TASKS_LOCK:
        TASKS["log"].append("[%s] %s" % (utils.now_str()[11:], line))
        TASKS["log"] = TASKS["log"][-400:]


def php_versions():
    """Доступные версии PHP -> {версия: [модули]}."""
    import glob
    if CTX.demo:
        from ..config import DEMO_PHP
        return DEMO_PHP
    versions = {}
    for path in sorted(glob.glob("/etc/php/*/fpm")) + \
            sorted(glob.glob("/etc/php/*/cli")):
        v = path.split("/")[3]
        versions.setdefault(v, [])
    if not versions and have("php"):
        code, out, _ = run(["php", "-r",
                            "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"])
        if code == 0 and out.strip():
            versions[out.strip()] = []
    for v in list(versions):
        binname = "php" + v if have("php" + v) else "php"
        code, out, _ = run([binname, "-m"], timeout=20)
        versions[v] = [m.strip() for m in out.splitlines() if m.strip() and not m.strip().startswith("[")] \
            if code == 0 else []
    return versions


def php_module_packages(version):
    """Список phpX.Y-* пакетов, доступных в apt (кэш apt-cache)."""
    if CTX.demo:
        return ["bcmath", "bz2", "curl", "dba", "enchant", "ffi", "gd",
                "gmp", "igbinary", "imagick", "imap", "intl", "ldap",
                "memcached", "mongodb", "mysqli", "odbc", "opcache",
                "pdo_pgsql", "pgsql", "pspell", "readline", "redis",
                "snmp", "soap", "sqlite3", "ssh2", "tidy", "xml", "xsl",
                "yaml", "zip", "zstd"]
    code, out, _ = run(["apt-cache", "search", "--names-only",
                        "php%s-" % version], timeout=60)
    names = []
    for line in out.splitlines():
        pkg = line.split(" - ")[0].strip()
        m = re.match(r"^php%s-([a-z0-9]+)$" % re.escape(version), pkg)
        if m:
            names.append(m.group(1))
    return sorted(set(names))


def apt_available():
    return CTX.demo or have("apt-get")


def upgradable():
    """Доступные обновления пакетов (apt list --upgradable)."""
    store = CTX.store
    if CTX.demo:
        return store.data.get("packages", {}).get("demo_upgradable", [])
    code, out, _ = run(["apt", "list", "--upgradable"], timeout=120)
    result = []
    for line in out.splitlines():
        if line.startswith("Внимание") or "/" not in line:
            continue
        parts = line.split()
        name = parts[0].split("/")[0]
        cur = new = ""
        m = re.search(r"\[.*(?:обновление с|upgradable from): ([^\]]+)\]", line)
        if m:
            cur = m.group(1)
        if " " in parts[0]:
            pass
        # формат: name/repo suite arch [version] [upgradable from: ver]
        # parts[1] — новая версия; parts[3] — "[upgradable", не версия
        new = parts[1] if len(parts) > 1 else ""
        kind = "система"
        if name.startswith("php"):
            kind = "PHP"
        elif "nginx" in name:
            kind = "веб-сервер"
        elif "apache" in name:
            kind = "веб-сервер"
        elif "mariadb" in name or "mysql" in name:
            kind = "БД"
        elif "nodejs" in name:
            kind = "Node.js"
        result.append({"pkg": name, "cur": cur, "new": new, "kind": kind})
    return result


# человекочитаемые названия фоновых задач (для уведомлений)
TASK_NAMES = {
    "pma-install": "Установка phpMyAdmin",
    "pma-remove": "Удаление phpMyAdmin",
    "software-install": "Установка ПО из каталога",
    "software-remove": "Удаление ПО",
    "install-php-module": "Установка PHP-модуля",
    "upgrade": "Обновление пакетов",
    "apt-update": "Обновление индексов apt",
    "ioncube-install": "Установка ionCube Loader",
    "ioncube-remove": "Удаление ionCube Loader",
}


def _task_title(kind):
    return TASK_NAMES.get(kind, kind)


def _worker():
    """Единственный исполнитель задач: берёт из очереди по одной."""
    while True:
        with _COND:
            while not _QUEUE:
                _COND.wait()
            kind, fn = _QUEUE.pop(0)
            TASKS.update({"running": True, "kind": kind, "log": [],
                          "started": utils.now_str()})
            TASKS["queued"] = [k for k, _f in _QUEUE]
        error = ""
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            error = str(e)
            _task_log("ОШИБКА: %s" % e)
            with STATE_LOCK:
                CTX.store.notify("%s — ошибка: %s"
                                 % (_task_title(kind), error[:150]), "error")
        finally:
            with _COND:
                TASKS["running"] = False
                TASK_HISTORY.insert(0, {
                    "kind": kind, "started": TASKS.get("started", ""),
                    "finished": utils.now_str(),
                    "ok": not error, "error": error[:200],
                    "log_tail": (TASKS.get("log") or [])[-5:]})
                del TASK_HISTORY[20:]


def _run_bg(kind, fn):
    """Ставит фоновую операцию в очередь с логом; возвращает (ok, err).

    Раньше при занятом исполнителе задача отклонялась — установка
    phpMyAdmin «блокировала» apt-обновления. Теперь задачи выстраиваются
    и выполняются по одной в порядке поступления."""
    global _WORKER
    with _COND:
        if len(_QUEUE) >= _QUEUE_LIMIT:
            return False, "очередь задач переполнена — попробуйте позже"
        first = not _QUEUE and not TASKS["running"]
        _QUEUE.append((kind, fn))
        TASKS["queued"] = [k for k, _f in _QUEUE]
        # анонс в уведомления (колокольчик): что запущено и где прогресс
        with STATE_LOCK:
            CTX.store.notify(
                "%s — запущено в фоне. Прогресс: Система → Пакеты и "
                "обновления (или Установка ПО)" % _task_title(kind), "info")
        if not first:
            return True, "задача добавлена в очередь — выполнится после " \
                         "текущей (%s)" % (TASKS["kind"] or "задачи")
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_worker, daemon=True)
            _WORKER.start()
        TASKS.update({"running": True, "kind": kind, "log": [],
                      "started": utils.now_str()})
        _COND.notify()
    return True, ""


def task_status():
    with TASKS_LOCK:
        d = dict(TASKS)
        d["history"] = list(TASK_HISTORY)
        return d


def install_php_module(version, module):
    """Устанавливает phpX.Y-модуль через apt (в фоне)."""
    import re
    if not re.match(r"^\d+\.\d+$", version or ""):
        return False, "некорректная версия PHP"
    if not re.match(r"^[a-z0-9]{1,32}$", module or ""):
        return False, "некорректное имя модуля"
    if CTX.demo:
        _demo_install(version, module)
        return True, "демо: модуль php%s-%s установлен" % (version, module)

    def job():
        _task_log("apt-get update…")
        run(["apt-get", "update"], timeout=300, as_root=True)
        _task_log("apt-get install -y php%s-%s…" % (version, module))
        code, out, err = run(["apt-get", "install", "-y",
                              "php%s-%s" % (version, module)],
                             timeout=900, as_root=True)
        _task_log("готово" if code == 0 else
                  "ошибка: %s" % ((err or out)[:400]))
        if code == 0:
            run(["systemctl", "reload", "php%s-fpm" % version], as_root=True)
            CTX.store.notify("Установлен модуль php%s-%s" % (version, module))
            CTX.store.log_action("Установлен модуль php%s-%s"
                                 % (version, module))
    return _run_bg("install-php-module", job)


def _demo_install(version, module):
    pkgs = CTX.store.data.setdefault("packages", {})
    installed = pkgs.setdefault("demo_installed", {})
    installed["php%s-%s" % (version, module)] = utils.now_str()
    # добавляем в список модулей версии
    _task_log("установка php%s-%s (демо)…" % (version, module))
    _task_log("готово")
    CTX.store.save()


def upgrade_packages(names):
    """Обновляет выбранные пакеты через apt (в фоне)."""
    clean = []
    for n in (names or []):
        n = re.sub(r"[^a-z0-9.+\-]", "", str(n).lower())
        if n and n not in clean:
            clean.append(n)
    if not clean:
        return False, "не выбраны пакеты"
    if CTX.demo:
        def job():
            _task_log("обновление (демо): %s" % ", ".join(clean))
            _task_log("готово")
            store = CTX.store
            up = [u for u in store.data["packages"].get("demo_upgradable", [])
                  if u["pkg"] not in clean]
            store.data["packages"]["demo_upgradable"] = up
            store.save()
        return _run_bg("upgrade", job)

    def job():
        _task_log("apt-get install --only-upgrade -y %s…" % " ".join(clean))
        code, out, err = run(
            ["apt-get", "install", "--only-upgrade", "-y"] + clean,
            timeout=1800, as_root=True)
        _task_log("готово" if code == 0 else "ошибка: %s" %
                  ((err or out)[:400]))
        if code == 0:
            CTX.store.notify("Обновлены пакеты: %s" % ", ".join(clean))
            CTX.store.log_action("Обновлены пакеты: %s" % ", ".join(clean))
    return _run_bg("upgrade", job)


def apt_update():
    """Обновляет индексы apt (в фоне)."""
    if CTX.demo:
        def job():
            _task_log("apt-get update (демо)…")
            _task_log("готово")
        return _run_bg("apt-update", job)

    def job():
        _task_log("apt-get update…")
        code, out, err = run(["apt-get", "update"], timeout=600, as_root=True)
        _task_log("готово" if code == 0 else "ошибка: %s" %
                  ((err or out)[:400]))
        if code == 0:
            with STATE_LOCK:
                CTX.store.data["packages"]["apt_updated"] = utils.now_str()
                CTX.store.save()
    return _run_bg("apt-update", job)
