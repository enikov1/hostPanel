# -*- coding: utf-8 -*-
"""ionCube Loader: установка, обновление и удаление для каждой версии PHP.

Загрузчики скачиваются с официального сайта ioncube.com (архив всегда
содержит самые свежие версии для всех поддерживаемых PHP), поэтому
«обновление» — это повторная установка. Файл .so хранится в
/opt/hostpanel/ioncube, подключение — через conf.d обеих SAPI (fpm, cli).
"""
import os
import re
import shutil
import tarfile
import urllib.request

from ..context import CTX, STATE_LOCK, run, have
from .. import utils

ARCHIVE_URL = {
    "x86_64": "https://downloads.ioncube.com/loader_downloads/"
              "ioncube_loaders_lin_x86-64.tar.gz",
    "aarch64": "https://downloads.ioncube.com/loader_downloads/"
               "ioncube_loaders_lin_aarch64.tar.gz",
}
LOADER_DIR = "/opt/hostpanel/ioncube"


def _task_log(line):
    from .packages import _task_log as log_line
    log_line(line)


def loader_state(version):
    """(установлен, версия загрузчика) для одной версии PHP."""
    if CTX.demo or not have("php" + version):
        return False, ""
    code, out, _ = run(["php" + version, "-v"], timeout=20)
    # формат различается по версиям: "Loader v15.5.1" (PHP 8+) и
    # "Loader + ionCube24 v15.5.1" (PHP 7.x)
    m = re.search(r"ionCube PHP Loader.*?v([0-9][\w.\-]*)",
                  (out or "").replace("\n", " "))
    if m:
        return True, m.group(1)
    return False, ""


def status():
    """Список установленных PHP с состоянием ionCube для каждой."""
    from .packages import php_versions
    versions = []
    for v in sorted(php_versions().keys()):
        installed, loader = loader_state(v)
        versions.append({"version": v, "installed": installed,
                         "loader": loader})
    return {"versions": versions}


def _ini_paths(version):
    return ["/etc/php/%s/%s/conf.d/01-ioncube.ini" % (version, sapi)
            for sapi in ("fpm", "cli", "apache2")]


def _download_and_extract():
    """Скачивает архив загрузчиков, возвращает путь к распакованному кат."""
    import platform
    url = ARCHIVE_URL.get(platform.machine())
    if not url:
        raise RuntimeError("архитектура %s не поддерживается ionCube"
                           % platform.machine())
    tmp_dir = os.path.join(CTX.home, "tmp", "ioncube")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)
    archive = os.path.join(tmp_dir, "loaders.tar.gz")
    _task_log("скачиваю %s…" % url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HostPanel"})
        with urllib.request.urlopen(req, timeout=180) as r, \
                open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("не удалось скачать архив ioncube.com: %s" % e)
    dest = os.path.join(tmp_dir, "x")
    os.makedirs(dest, exist_ok=True)
    try:
        with tarfile.open(archive) as tf:
            tf.extractall(dest, filter="data")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("не удалось распаковать архив: %s" % e)
    return dest


def install(version):
    """Устанавливает/обновляет ionCube Loader для PHP-версии (в фоне)."""
    if not re.match(r"^\d+\.\d+$", version or ""):
        return False, "некорректная версия PHP"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    if not have("php" + version):
        return False, ("PHP %s не установлен — сначала установите его "
                       "в каталоге ПО" % version)
    from .packages import _run_bg

    def job():
        _task_log("ionCube Loader для PHP %s…" % version)
        try:
            dest = _download_and_extract()
        except RuntimeError as e:
            _task_log("ОШИБКА: %s" % e)
            CTX.store.notify("ionCube PHP %s: %s" % (version, e), "error")
            return
        so_name = "ioncube_loader_lin_%s.so" % version
        so = os.path.join(dest, "ioncube", so_name)
        if not os.path.exists(so):
            _task_log("ОШИБКА: в архиве нет загрузчика для PHP %s — "
                      "ionCube эту версию пока не поддерживает" % version)
            CTX.store.notify("ionCube не поддерживает PHP %s" % version,
                             "error")
            return
        try:
            os.makedirs(LOADER_DIR, exist_ok=True)
            shutil.copy2(so, os.path.join(LOADER_DIR, so_name))
            ini = "zend_extension=%s\n" % os.path.join(LOADER_DIR, so_name)
            for path in _ini_paths(version):
                if os.path.isdir(os.path.dirname(path)):
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(ini)
        except OSError as e:
            _task_log("ОШИБКА: %s" % e)
            CTX.store.notify("ionCube PHP %s: %s" % (version, e), "error")
            return
        _task_log("загрузчик сохранён в %s, перезапускаю php%s-fpm…"
                  % (LOADER_DIR, version))
        run(["systemctl", "restart", "php%s-fpm" % version],
            as_root=True, timeout=60)
        installed, loader = loader_state(version)
        if installed:
            _task_log("готово: ionCube %s подключён к PHP %s"
                      % (loader, version))
            CTX.store.notify("ionCube %s подключён к PHP %s"
                             % (loader, version))
            with STATE_LOCK:
                CTX.store.log_action(
                    "ionCube Loader %s установлен для PHP %s"
                    % (loader, version))
                CTX.store.save()
        else:
            _task_log("ОШИБКА: загрузчик не подключился, проверьте "
                      "journalctl -u php%s-fpm" % version)
            CTX.store.notify("ionCube для PHP %s не подключился" % version,
                             "error")
    return _run_bg("ioncube-install", job)


def remove(version):
    """Отключает и удаляет ionCube Loader для PHP-версии (в фоне)."""
    if not re.match(r"^\d+\.\d+$", version or ""):
        return False, "некорректная версия PHP"
    if CTX.demo:
        return False, "в демо-режиме недоступно"
    if not have("php" + version):
        return False, "PHP %s не установлен" % version
    if not loader_state(version)[0]:
        return False, "ionCube для PHP %s и так не установлен" % version
    from .packages import _run_bg

    def job():
        _task_log("Удаление ionCube для PHP %s…" % version)
        for path in _ini_paths(version) + \
                [os.path.join(LOADER_DIR,
                              "ioncube_loader_lin_%s.so" % version)]:
            try:
                os.remove(path)
            except OSError:
                pass
        run(["systemctl", "restart", "php%s-fpm" % version],
            as_root=True, timeout=60)
        installed, _ = loader_state(version)
        if not installed:
            _task_log("готово")
            CTX.store.notify("ionCube удалён для PHP %s" % version, "warn")
            with STATE_LOCK:
                CTX.store.log_action(
                    "ionCube Loader удалён для PHP %s" % version)
                CTX.store.save()
        else:
            _task_log("ОШИБКА: загрузчик всё ещё активен")
    return _run_bg("ioncube-remove", job)
