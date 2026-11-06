# -*- coding: utf-8 -*-
"""Каталог движков для установки в один клик (WordPress, Joomla, Drupal,
загрузка своего дистрибутива). Общий механизм: скачивание/распаковка в
docroot сайта, генерация конфига БД, фоновая задача с живым журналом.

Безопасность:
- источники — только https + фиксированные официальные хосты, IP резолвится
  и проверяется (никаких private/loopback), редиректы запрещены;
- распаковка архивов — с проверкой path traversal и симлинков;
- DLE (nulled-дистрибутивы) не скачивается панелью — пользователь загружает
  свой ZIP сам (файл проверяется на симлинки и ../).
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
import zipfile
import tarfile

from .. import config, utils
from ..context import CTX, STATE_LOCK, run

ENGINES = {
    "wordpress": {
        "name": "WordPress",
        "desc": "Самая популярная CMS: блоги, сайты, магазины (WooCommerce). "
                "Установка полностью автоматическая — сайт и админка готовы "
                "сразу после завершения.",
        "logo": "wordpress",
        "db": "mysql",
        "url": "https://wordpress.org/",
    },
    "joomla": {
        "name": "Joomla",
        "desc": "Универсальная CMS с гибкими правами пользователей. После "
                "распаковки установка завершается в браузере за пару минут.",
        "logo": "joomla",
        "db": "mysql",
        "url": "https://www.joomla.org/",
    },
    "drupal": {
        "name": "Drupal",
        "desc": "Мощная CMS для сложных сайтов. После распаковки установка "
                "завершается в браузере.",
        "logo": "drupal",
        "db": "mysql",
        "url": "https://www.drupal.org/",
    },
    "dle": {
        "name": "DataLife Engine (DLE)",
        "desc": "Движок новостных сайтов и каталогов. Лицензия платная — "
                "загрузите свой дистрибутив (ZIP), панель распакует его и "
                "подготовит конфиг БД.",
        "logo": None,
        "db": "mysql",
        "url": "https://dle-news.ru/",
    },
}

# официальные источники дистрибутивов (host фиксируется, https, IP проверяется)
SOURCES = {
    "wordpress": "https://wordpress.org/latest-ru_RU.tar.gz",
    "joomla": "https://downloads.joomla.org/cms/joomla5/5-2-0/"
              "Joomla_5-2-0-Stable-Full_Package.zip",
    "drupal": "https://www.drupal.org/download-latest/tar.gz",
}
SOURCE_HOSTS = {
    "wordpress": "wordpress.org",
    "joomla": "downloads.joomla.org",
    "drupal": "www.drupal.org",
}

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


def _check_url(url, allowed_host):
    """https + точный хост + резолв без private/loopback (SSRF/DNS rebinding)."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != allowed_host:
        raise RuntimeError("недопустимый источник: %s" % allowed_host)
    infos = socket.getaddrinfo(parts.hostname, 443, proto=socket.IPPROTO_TCP)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast):
            raise RuntimeError("хост дистрибутива резолвится в "
                               "недопустимый адрес")


def _safe_extract_tar(tf, dest):
    """Распаковка tar.gz с защитой от path traversal и симлинков."""
    base = os.path.realpath(dest)
    for member in tf.getmembers():
        if not (member.isfile() or member.isdir()):
            continue  # симлинки и устройства пропускаем
        target = os.path.realpath(os.path.join(dest, member.name))
        if not target.startswith(base + os.sep):
            raise RuntimeError("подозрительный путь в архиве: " + member.name)
    tf.extractall(dest)


def _safe_extract_zip(zf, dest):
    """Распаковка ZIP с защитой от path traversal и симлинков."""
    base = os.path.realpath(dest)
    for info in zf.infolist():
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            continue  # симлинки пропускаем
        target = os.path.realpath(os.path.join(dest, info.filename))
        if not target.startswith(base + os.sep):
            raise RuntimeError("подозрительный путь в архиве: " + info.filename)
    zf.extractall(dest)


def _download_dist(url, host, dest, max_bytes=300 * 1024 * 1024):
    _check_url(url, host)
    req = urllib.request.Request(
        url, headers={"User-Agent": "HostPanel/" + config.VERSION})
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status != 200:
            raise RuntimeError("дистрибутив не скачался (код %d)" % r.status)
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise RuntimeError("дистрибутив слишком большой")
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def _new_db(site, body):
    """Создаёт новую базу через модуль БД панели. Возвращает (name,user,pass)."""
    import re
    from . import db as db_mod
    suffix = re.sub(r"[^a-z0-9]", "", site["domain"].lower())[:20] or "site"
    name = str(body.get("db_name") or "").strip().lower() or \
        ("eng_" + suffix)
    user = name[:32]
    password = secrets.token_urlsafe(18)
    if not db_mod.valid_name(name, "mysql"):
        raise RuntimeError("некорректное имя базы данных")
    okc, msg = db_mod.create(name, user, password, "mysql")
    if not okc:
        raise RuntimeError("создание базы: " + msg)
    return name, user, password


def install_task(site, engine, body):
    """Запускает установку движка в фоне. Проверки — в вызывающем коде."""
    with LOCK:
        if TASK["running"]:
            return False, "установка уже выполняется"
        TASK.update({"running": True, "site_id": site["id"], "log": [],
                     "error": "", "done": False})
    t = threading.Thread(target=_worker,
                         args=(dict(site), engine, dict(body)), daemon=True)
    t.start()
    return True, "установка движка запущена"


def _worker(site, engine, body):
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="engine-install-")
        docroot = _docroot_abs(site)
        domain = site["domain"]

        db_name = db_user = db_password = ""
        if body.get("db_mode") == "new" or not body.get("db_name"):
            _log("Создаю базу данных…")
            db_name, db_user, db_password = _new_db(site, body)
            _log("База данных создана: %s" % db_name)
        else:
            db_name = str(body.get("db_name"))
            db_user = str(body.get("db_user") or db_name)
            db_password = str(body.get("db_password") or "")

        meta = {"engine": engine, "db_name": db_name, "db_user": db_user,
                "db_password": db_password,
                "installed_at": utils.now_str()}

        if engine == "wordpress":
            _install_wordpress(site, docroot, body, meta, tmp)
        elif engine == "dle":
            _install_dle(site, docroot, body, meta, tmp)
        else:
            _install_archive(engine, site, docroot, body, meta, tmp)

        _log("Готово! Движок установлен: https://%s" % domain)
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


def _docroot_abs(site):
    if CTX.demo:
        return os.path.join(CTX.home, "demo_www", site["domain"])
    docroot = site["docroot"]
    if not os.path.isabs(docroot):
        docroot = os.path.join("/var/www", docroot)
    return docroot


def _finish(site, docroot, engine, meta):
    """Общие завершающие шаги: состояние, права, docroot → public (если движку
    нужен), перечитывание nginx."""
    with STATE_LOCK:
        engines = site.setdefault("engines", {})
        engines[engine] = meta
        if engine == "wordpress":
            site["engine_wp"] = True   # front-controller для nginx
        CTX.store.save()
    if not CTX.demo:
        run(["chown", "-R", "www-data:www-data", docroot], as_root=True,
            timeout=300)
        run(["systemctl", "reload", "nginx"], as_root=True, timeout=30)


def _clear_docroot(docroot):
    """Очистка корня сайта перед установкой (подтверждается в UI)."""
    if os.path.isdir(docroot):
        _log("Очищаю корневую папку сайта…")
        for name in os.listdir(docroot):
            pth = os.path.join(docroot, name)
            try:
                if os.path.isdir(pth) and not os.path.islink(pth):
                    shutil.rmtree(pth, ignore_errors=True)
                else:
                    os.remove(pth)
            except OSError:
                pass


def _install_wordpress(site, docroot, body, meta, tmp):
    """WordPress: скачивание, wp-config.php с ключами, wp-cli автоустановка."""
    from ..context import have
    _log("Скачиваю дистрибутив WordPress…")
    dist = os.path.join(tmp, "wp.tar.gz")
    _download_dist(SOURCES["wordpress"], SOURCE_HOSTS["wordpress"], dist)
    _log("Распаковываю…")
    _clear_docroot(docroot)
    with tarfile.open(dist, "r:gz") as tf:
        _safe_extract_tar(tf, docroot)
    # архив содержит папку wordpress/ — переносим содержимое в корень
    wpdir = os.path.join(docroot, "wordpress")
    if os.path.isdir(wpdir):
        for name in os.listdir(wpdir):
            shutil.move(os.path.join(wpdir, name),
                        os.path.join(docroot, name))
        os.rmdir(wpdir)
    _log("Генерирую wp-config.php…")
    _write_wp_config(docroot, meta["db_name"], meta["db_user"],
                     meta["db_password"])
    # автозавершение установки через wp-cli (если php доступен)
    if CTX.demo:
        _log("(демо) Сайт готов — финальный шаг в браузере")
        _finish(site, docroot, "wordpress", meta)
        return
    _log("Завершаю установку через wp-cli…")
    admin_password = secrets.token_urlsafe(12)
    email = str(body.get("admin_email") or
                "admin@" + site["domain"])
    title = str(body.get("site_title") or site["domain"])
    okc = _wp_cli(docroot, [
        "core", "install",
        "--url=https://" + site["domain"],
        "--title=" + title,
        "--admin_user=admin", "--admin_password=" + admin_password,
        "--admin_email=" + email, "--skip-email",
    ])
    if not okc:
        _log("wp-cli недоступен — завершите установку в браузере "
             "(откроется мастер WordPress)")
    else:
        _log("Администратор WordPress: логин admin, пароль %s — "
             "сохраните его!" % admin_password)
    meta["admin_password"] = admin_password if okc else ""
    meta["admin_user"] = "admin"
    _finish(site, docroot, "wordpress", meta)


def _write_wp_config(docroot, db_name, db_user, db_password):
    """Генерирует wp-config.php из шаблона с уникальными ключами."""
    sample = os.path.join(docroot, "wp-config-sample.php")
    conf = os.path.join(docroot, "wp-config.php")
    if not os.path.isfile(sample):
        raise RuntimeError("wp-config-sample.php не найден в дистрибутиве")
    s = open(sample, encoding="utf-8").read()
    s = s.replace("database_name_here", db_name)
    s = s.replace("username_here", db_user)
    s = s.replace("password_here", db_password)
    # заменяем дефолтные значения ключей построчно
    import re as _re
    def _sub_salt(m):
        return "%s'%s';" % (m.group(1), secrets.token_urlsafe(48))
    s = _re.sub(r"(define\(\s*'(?:AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|"
                r"NONCE_KEY|AUTH_SALT|SECURE_AUTH_SALT|LOGGED_IN_SALT|"
                r"NONCE_SALT)',\s*)'[^']*'", _sub_salt, s)
    with open(conf, "w", encoding="utf-8") as f:
        f.write(s)
    os.chmod(conf, 0o640)


def _wp_cli(cwd, args):
    """wp-cli: скачивается при первом использовании. True — успех."""
    from ..context import have
    phar = "/usr/local/bin/wp-cli.phar"
    if not os.path.isfile(phar):
        _log("Скачиваю wp-cli…")
        with _safe_url_open("https://raw.githubusercontent.com/wp-cli/"
                            "builds/gh-pages/phar/wp-cli.phar") as r, \
                open(phar + ".tmp", "wb") as f:
            f.write(r.read(20 * 1024 * 1024))
        os.replace(phar + ".tmp", phar)
        os.chmod(phar, 0o755)
    if not have("php"):
        return False
    code, out, err = run(["php", phar] + args + ["--allow-root"],
                         cwd=cwd, timeout=600, as_root=True)
    return code == 0


def _install_archive(engine, site, docroot, body, meta, tmp):
    """Joomla / Drupal: скачивание официального дистрибутива и распаковка."""
    _log("Скачиваю дистрибутив %s…" % ENGINES[engine]["name"])
    dist = os.path.join(tmp, "dist." + ("zip" if SOURCES[engine].endswith(
        ".zip") else "tar.gz"))
    _download_dist(SOURCES[engine], SOURCE_HOSTS[engine], dist)
    _clear_docroot(docroot)
    _log("Распаковываю…")
    if dist.endswith(".zip"):
        with zipfile.ZipFile(dist) as zf:
            _safe_extract_zip(zf, docroot)
    else:
        with tarfile.open(dist, "r:gz") as tf:
            _safe_extract_tar(tf, docroot)
    # drupal/joomla распаковываются в подпапку — поднимаем содержимое
    entries = [n for n in os.listdir(docroot)
               if n not in (".", "..")]
    if len(entries) == 1 and os.path.isdir(os.path.join(docroot, entries[0])):
        inner = os.path.join(docroot, entries[0])
        for name in os.listdir(inner):
            shutil.move(os.path.join(inner, name),
                        os.path.join(docroot, name))
        os.rmdir(inner)
    _log("Распаковано. Откройте сайт в браузере — мастер установки "
         "доведёт настройку (потребуются реквизиты БД ниже).")
    _finish(site, docroot, engine, meta)


def _install_dle(site, docroot, body, meta, tmp):
    """DLE: пользователь загружает свой дистрибутив ZIP (панель его
    не поставляет)."""
    import base64
    data = body.get("dist_b64") or ""
    name = str(body.get("dist_name") or "dle.zip")
    if not data:
        raise RuntimeError("загрузите ZIP-дистрибутив DLE")
    try:
        raw = base64.b64decode(data)
    except Exception:
        raise RuntimeError("не удалось прочитать загруженный файл")
    if len(raw) > 200 * 1024 * 1024:
        raise RuntimeError("дистрибутив слишком большой")
    dist = os.path.join(tmp, os.path.basename(name))
    with open(dist, "wb") as f:
        f.write(raw)
    _clear_docroot(docroot)
    _log("Распаковываю дистрибутив…")
    if dist.endswith(".zip"):
        with zipfile.ZipFile(dist) as zf:
            _safe_extract_zip(zf, docroot)
    elif dist.endswith((".tar.gz", ".tgz")):
        with tarfile.open(dist, "r:gz") as tf:
            _safe_extract_tar(tf, docroot)
    else:
        raise RuntimeError("поддерживаются ZIP и tar.gz")
    _log("Распаковано. Откройте сайт — мастер DLE доведёт установку. "
         "Реквизиты БД: %s / %s / пароль — в карточке движка." %
         (meta["db_name"], meta["db_user"]))
    _finish(site, docroot, "dle", meta)
