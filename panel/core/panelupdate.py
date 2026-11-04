# -*- coding: utf-8 -*-
"""Обновление панели с GitHub: проверка новой версии, скачивание,
замена файлов, рестарт службы.

Репозиторий: github.com/enikov1/hostPanel (ветка main).
Версия релиза — файл VERSION в корне репозитория. Обновление доступно,
если версия в репо выше установленной (сравнение по числовым сегментам).

Безопасность: в демо-режиме обновление запрещено; перед заменой файлов
старая панель копируется в /opt/hostpanel/panel.bak-<метка времени>;
REST API-состояние (/opt/hostpanel/state.json) не входит в panel/ и
не затрагивается.
"""
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.request

from .. import config, utils
from ..context import CTX

REPO = "enikov1/hostPanel"
RAW_VERSION = "https://raw.githubusercontent.com/%s/main/VERSION" % REPO
ARCHIVE_URL = "https://github.com/%s/archive/refs/heads/main.tar.gz" % REPO

# фоновая задача обновления (одна одновременно)
TASK = {"running": False, "log": [], "started": "", "error": "", "done": False}
LOCK = threading.Lock()

# кеш последней проверки версии GitHub: [timestamp, версия] — чтобы не
# блокировать request-поток urlopen'ом на каждый опрос статуса
_last_check = [0.0, ""]


def _log(msg):
    with LOCK:
        TASK["log"].append("[%s] %s" % (utils.now_str()[11:], msg))
        TASK["log"] = TASK["log"][-200:]


def _version_tuple(v):
    """'2.15.1' -> (2, 15, 1); нечисловые сегменты отбрасываются."""
    out = []
    for part in str(v).strip().split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out)


def version_newer(a, b):
    """True, если a строго новее b."""
    ta, tb = _version_tuple(a), _version_tuple(b)
    n = max(len(ta), len(tb))
    ta += (0,) * (n - len(ta))
    tb += (0,) * (n - len(tb))
    return ta > tb


def fetch_latest_version(timeout=8):
    req = urllib.request.Request(
        RAW_VERSION, headers={"User-Agent": "HostPanel/" + config.VERSION})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8").strip()


def status():
    """Текущее состояние: версии, доступность обновления, лог задачи."""
    latest, error = "", ""
    running = TASK["running"]
    if not running:  # свежая проверка только когда задача не идёт
        if _last_check[0] and time.time() - _last_check[0] < 300:
            latest = _last_check[1]   # кеш свежее 300 сек — не ходим в сеть
        else:
            try:
                latest = fetch_latest_version()
                _last_check[0], _last_check[1] = time.time(), latest
            except Exception as e:  # noqa: BLE001 — сеть может быть недоступна
                error = "нет связи с GitHub (%s)" % str(e)[:120]
    with LOCK:
        task = {"running": TASK["running"], "log": TASK["log"][-40:],
                "started": TASK["started"], "error": TASK["error"],
                "done": TASK["done"]}
    return {
        "ok": True,
        "current": config.VERSION,
        "latest": latest,
        "update_available": bool(
            latest and version_newer(latest, config.VERSION)),
        "error": error,
        "repo": REPO,
        "task": task,
    }


def run_update():
    """Запуск обновления в фоне. Возвращает (ok, message)."""
    if CTX.demo:
        return False, "в демо-режиме обновление недоступно"
    with LOCK:
        if TASK["running"]:
            return False, "обновление уже выполняется"
        TASK.update({"running": True, "log": [], "started": utils.now_str(),
                     "error": "", "done": False})
    threading.Thread(target=_worker, daemon=True).start()
    return True, "обновление запущено — панель перезапустится автоматически"


def _worker():
    try:
        _do_update()
    except Exception as e:  # noqa: BLE001
        _log("ОШИБКА: %s" % e)
        with LOCK:
            TASK["error"] = str(e)[:300]
    finally:
        with LOCK:
            TASK["running"] = False
            TASK["done"] = True


def _do_update():
    home = CTX.home or "/opt/hostpanel"
    target = os.path.join(home, "panel")
    _log("Скачиваю архив репозитория…")
    tmp = tempfile.mkdtemp(prefix="hostpanel-update-")
    archive = os.path.join(tmp, "repo.tar.gz")
    req = urllib.request.Request(
        ARCHIVE_URL, headers={"User-Agent": "HostPanel/" + config.VERSION})
    with urllib.request.urlopen(req, timeout=120) as r, \
            open(archive, "wb") as f:
        shutil.copyfileobj(r, f)
    _log("Архив скачан (%d КБ), распаковываю…" %
         (os.path.getsize(archive) // 1024))
    with tarfile.open(archive, "r:gz") as tf:
        # защита от path traversal: только обычные файлы/папки внутри tmp
        for member in tf.getmembers():
            target = os.path.realpath(os.path.join(tmp, member.name))
            if not target.startswith(os.path.realpath(tmp) + os.sep):
                raise RuntimeError("подозрительный путь в архиве: "
                                   + member.name)
        tf.extractall(tmp)
    src_root = next(os.path.join(tmp, d) for d in os.listdir(tmp)
                    if os.path.isdir(os.path.join(tmp, d)))
    new_panel = os.path.join(src_root, "panel")
    if not os.path.isdir(new_panel) or \
            not os.path.isfile(os.path.join(new_panel, "server.py")):
        raise RuntimeError("в архиве нет panel/server.py — архив повреждён")
    new_version = (open(os.path.join(src_root, "VERSION")).read().strip()
                   if os.path.isfile(os.path.join(src_root, "VERSION"))
                   else "")
    _log("Версия в репозитории: %s (установлена %s)"
         % (new_version or "?", config.VERSION))

    # бэкап текущей панели
    stamp = utils.now_str().replace(" ", "_").replace(":", "-")
    backup = target + ".bak-" + stamp
    _log("Копирую текущую панель в %s…" % backup)
    shutil.copytree(target, backup,
                    ignore=shutil.ignore_patterns("__pycache__"))

    # замена файлов: чистим всё, кроме пользовательских каталогов рядом
    _log("Заменяю файлы панели…")
    parent = os.path.dirname(target)
    tmp_new = os.path.join(parent, ".panel-new-%s" % stamp)
    shutil.copytree(new_panel, tmp_new,
                    ignore=shutil.ignore_patterns("__pycache__"))
    os.rename(target, target + ".old-tmp")
    try:
        os.rename(tmp_new, target)
    except OSError:
        os.rename(target + ".old-tmp", target)  # откат
        raise
    shutil.rmtree(target + ".old-tmp", ignore_errors=True)
    shutil.rmtree(tmp_new, ignore_errors=True)

    # права: как расставлял install.sh
    try:
        import pwd  # noqa: F401 — только на Linux
        subprocess.run(["chown", "-R", "hostpanel:hostpanel", target],
                       check=False)
        subprocess.run(["chmod", "-R", "go-w", target], check=False)
    except ImportError:
        pass

    shutil.rmtree(tmp, ignore_errors=True)
    # старые бэкапы: оставляем последние 3
    baks = sorted(
        (d for d in os.listdir(parent)
         if d.startswith("panel.bak-") or d.startswith("panel.bak-spa")),
        reverse=True)
    for old in baks[3:]:
        shutil.rmtree(os.path.join(parent, old), ignore_errors=True)

    _log("Файлы заменены. Перезапуск службы hostpanel…")
    from ..context import STATE_LOCK
    with STATE_LOCK:   # мутация state + save — только под замком
        utils.log("Обновление панели: %s -> %s" % (config.VERSION, new_version))
        CTX.store.log_action("Обновление панели до версии %s" %
                             (new_version or "?"))
        CTX.store.save()
    # рестарт после короткой паузы: успеть отдать HTTP-ответ клиенту
    timer = threading.Timer(2.0, lambda: subprocess.run(
        ["systemctl", "restart", "hostpanel"], check=False))
    timer.daemon = True
    timer.start()
    _log("Готово. Панель перезапускается — страница обновится сама.")
