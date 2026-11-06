# -*- coding: utf-8 -*-
"""Установка движка Omro (репозиторий enikov1/cld) на сайт панели.

Панель скачивает install.sh из репозитория движка и запускает его в режиме
PANEL_MODE=1: скрипт получает APP_DIR/DOMAIN/DB_*/ADMIN_TOKEN через
переменные окружения и сам ставит зависимости, миграции и собирает
интерфейсы. Пул PHP-FPM и веб-сервер остаётся на стороне панели; после
успешной установки docroot сайта переключается на public/ (см.
templates.write_site_configs — флаг site["engine_cld"]).

Установка идёт в фоновой задаче с живым журналом (TASK), как apt-задачи
в core/packages.py.
"""
import ipaddress
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import urllib.request

from .. import config, utils
from ..context import CTX, STATE_LOCK, run

CLD_INSTALL_URL = "https://raw.githubusercontent.com/enikov1/cld/main/install.sh"
CLD_INSTALL_HOST = "raw.githubusercontent.com"
CLD_TIMEOUT = 1800  # 30 минут на composer/npm/миграции
INSTALL_MAX_BYTES = 1024 * 1024

TASK = {"running": False, "site_id": 0, "log": [], "error": "", "done": False}
LOCK = threading.Lock()


def _log(msg):
    with LOCK:
        TASK["log"].append("[%s] %s" % (utils.now_str()[11:], msg))
        TASK["log"] = TASK["log"][-500:]


def task_for_site(site_id):
    with LOCK:
        return (TASK["running"] and TASK["site_id"] == site_id,
                TASK["log"][-120:], TASK["error"], TASK["done"])


def _safe_url_open(url):
    """Открывает только https и только проверенный хост; IP-адрес хоста
    резолвится и проверяется (никаких private/loopback — защита от
    SSRF и DNS rebinding); редиректы запрещены."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != CLD_INSTALL_HOST:
        raise RuntimeError("недопустимый источник установщика")
    infos = socket.getaddrinfo(parts.hostname, 443, proto=socket.IPPROTO_TCP)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast):
            raise RuntimeError("хост установщика резолвится в "
                               "недопустимый адрес")
    opener = urllib.request.OpenerDirector()
    opener.add_handler(urllib.request.HTTPSHandler())
    # без HTTPRedirectHandler: редирект = ошибка (хост и схема фиксируются)
    req = urllib.request.Request(
        url, headers={"User-Agent": "HostPanel/" + config.VERSION})
    return opener.open(req, timeout=60)


def _download_installer(tmp):
    """Скачивает install.sh движка (https, проверенный хост, лимит размера)."""
    with _safe_url_open(CLD_INSTALL_URL) as r:
        if r.status != 200:
            raise RuntimeError("install.sh не скачался (код %d)" % r.status)
        data = r.read(INSTALL_MAX_BYTES + 1)
    if len(data) > INSTALL_MAX_BYTES:
        raise RuntimeError("install.sh слишком большой")
    if len(data) < 50 or not data.lstrip().startswith(b"#!"):
        raise RuntimeError("install.sh не похож на скрипт")
    path = os.path.realpath(os.path.join(tmp, "install.sh"))
    if not path.startswith(os.path.realpath(tmp) + os.sep):
        raise RuntimeError("некорректный путь установщика")
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, 0o700)
    import hashlib
    sha = hashlib.sha256(data).hexdigest()[:32]
    _log("install.sh скачан (%d КБ, sha256 %s…)" % (len(data) // 1024, sha))
    utils.log("cld: install.sh SHA256 %s" % sha)
    return path


def _log_stream(proc):
    """Живой журнал: читает stdout процесса в TASK log."""
    for line in iter(proc.stdout.readline, ""):
        if not line:
            break
        _log(line.rstrip()[:300])


def install_task(site, db_name, db_user, db_password, admin_token):
    """Запускает установку в фоне. Все проверки — в вызывающем коде."""
    with LOCK:
        if TASK["running"]:
            return False, "установка уже выполняется"
        TASK.update({"running": True, "site_id": site["id"], "log": [],
                     "error": "", "done": False})
    t = threading.Thread(
        target=_worker,
        args=(dict(site), db_name, db_user, db_password, admin_token),
        daemon=True)
    t.start()
    return True, "установка движка запущена — займёт несколько минут"


def _worker(site, db_name, db_user, db_password, admin_token):
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="cld-install-")
        tmp_real = os.path.realpath(tmp)
        docroot = site_docroot_abs(site)
        domain = site["domain"]

        _log("Скачиваю установщик движка…")
        script = _download_installer(tmp)

        _log("Запускаю установку Omro (PANEL_MODE=1) — это займёт несколько минут…")
        env = dict(os.environ)
        env.update({
            "PANEL_MODE": "1", "DEBIAN_FRONTEND": "noninteractive",
            "APP_DIR": docroot, "DOMAIN": domain,
            "DB_NAME": db_name, "DB_USER": db_user,
            "DB_PASSWORD": db_password, "ADMIN_TOKEN": admin_token,
        })
        proc = subprocess.Popen(
            ["bash", script], cwd=tmp_real, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace")
        _log_stream(proc)
        try:
            code = proc.wait(timeout=CLD_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError("установка не уложилась в 30 минут — "
                               "процесс остановлен")
        if code != 0:
            raise RuntimeError("install.sh завершился с кодом %d" % code)
        _log("Установщик завершился успешно")

        # состояние движка на сайте + права как после создания сайта
        with STATE_LOCK:
            site["engine_cld"] = True
            site["cld"] = {
                "engine": "omro", "version": "main",
                "installed_at": utils.now_str(),
                "db_name": db_name, "db_user": db_user,
                "db_password": db_password,
                "admin_token": admin_token,
            }
            CTX.store.save()

        _log("Переключаю docroot сайта на public/ и перечитываю nginx…")
        from . import templates
        okc, errc = templates.write_site_configs(site)
        if not okc:
            raise RuntimeError("переключение docroot: " + errc)
        if not CTX.demo:
            run(["systemctl", "reload", "nginx"], as_root=True, timeout=30)

        _log("Готово! Движок Omro установлен: https://%s (админка: /admin/)"
             % domain)
    except Exception as e:  # noqa: BLE001
        _log("ОШИБКА: %s" % e)
        with LOCK:
            TASK["error"] = str(e)[:300]
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        with LOCK:
            TASK["running"] = False
            TASK["done"] = True


def site_docroot_abs(site):
    """Абсолютный docroot сайта (как его видит сервер)."""
    if CTX.demo:
        return os.path.join(CTX.home, "demo_www", site["domain"])
    docroot = site["docroot"]
    if not os.path.isabs(docroot):
        docroot = os.path.join("/var/www", docroot)
    return docroot
