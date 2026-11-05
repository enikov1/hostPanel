# -*- coding: utf-8 -*-
"""phpMyAdmin: установка в 1 клик в папку выбранного сайта (/pma).

Скачивает официальный архив с files.phpmyadmin.net, распаковывает
в docroot/pma, создаёт config.inc.php со случайным blowfish-ключом,
по желанию закрывает папку basic-auth в nginx (пароль хранится
в состоянии панели, доступы видны администратору).
"""
import os
import secrets
import shutil
import string
import tarfile
import tempfile

from ..context import CTX, STATE_LOCK, run
from .. import config, utils

PMA_VERSION = "5.2.2"
PMA_URL = ("https://files.phpmyadmin.net/phpMyAdmin/%s/"
           "phpMyAdmin-%s-all-languages.tar.gz"
           % (PMA_VERSION, PMA_VERSION))
# минимальный размер архива, МБ — защита от битой загрузки
PMA_MIN_SIZE = 5 * 1024 * 1024

BLOWFISH_CHARS = string.ascii_letters + string.digits


def _task_log(line):
    from .packages import _task_log as log_line
    log_line(line)


def _docroot(site):
    p = site["docroot"]
    return p if os.path.isabs(p) else os.path.join(CTX.home, p)


def _gen_password(n=14):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def status():
    """Где phpMyAdmin установлен и как защищён."""
    out = []
    for site in CTX.store.data.get("sites", []):
        if not site.get("php"):
            continue
        info = (site.get("apps") or {}).get("pma") or {}
        installed = os.path.exists(os.path.join(_docroot(site),
                                                "pma", "index.php"))
        row = {"domain": site["domain"], "installed": installed}
        if installed:
            ssl = (site.get("ssl") or {}).get("kind", "none")
            scheme = "https" if ssl != "none" else "http"
            # apache-сайты слушают :8081, nginx — :80
            port = ":8081" if site["webserver"] == "apache" \
                and ssl == "none" else ""
            row["url"] = "%s://%s%s/pma/" % (scheme, site["domain"], port)
            row["protected"] = bool(info.get("protected"))
            row["user"] = info.get("user", "pma")
            row["password"] = info.get("password", "")
            row["version"] = info.get("version", PMA_VERSION)
        out.append(row)
    return out


def _download(dest):
    _task_log("загрузка phpMyAdmin %s…" % PMA_VERSION)
    import urllib.request
    try:
        with urllib.request.urlopen(PMA_URL, timeout=120) as r, \
                open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:  # noqa: BLE001
        return "не удалось скачать архив: %s" % e
    if os.path.getsize(dest) < PMA_MIN_SIZE:
        return "архив загрузился не полностью — попробуйте ещё раз"
    return ""


def _safe_members(tf):
    """Члены архива без выхода за целевую папку (анти path-traversal)."""
    for m in tf.getmembers():
        name = os.path.normpath(m.name)
        if name.startswith("..") or os.path.isabs(name) or m.name.startswith("/"):
            continue
        yield m


def _htpasswd_hash(password):
    """Хэш apr1 через openssl (или htpasswd из apache2-utils).
    Пароль через stdin — не в argv (виден в ps//proc)."""
    code, out, _ = run(["openssl", "passwd", "-apr1", "-stdin"],
                       input_text=password, timeout=15)
    if code == 0 and out.strip():
        return out.strip()
    code, out, _ = run(["htpasswd", "-ni", "pma"], input_text=password,
                       timeout=15)
    if code == 0 and ":" in out:
        return out.strip().split(":", 1)[1]
    return ""


def _htpasswd_path(site):
    from .templates import pool_name
    return os.path.join(config.PMA_HTPASSWD_DIR,
                        "%s.htpasswd" % pool_name(site["domain"]))


def _write_protection(site, password):
    """Создаёт htpasswd и включает basic auth: nginx — location в конфиге,
    apache — .htaccess в папке pma (AllowOverride All в шаблоне панели)."""
    h = _htpasswd_hash(password)
    if not h:
        return "openssl и htpasswd недоступны — не удалось создать пароль"
    os.makedirs(config.PMA_HTPASSWD_DIR, exist_ok=True)
    path = _htpasswd_path(site)
    with open(path, "w", encoding="utf-8") as f:
        f.write("pma:%s\n" % h)
    os.chmod(path, 0o640)
    run(["chown", "root:www-data", path], as_root=True)
    if site["webserver"] == "nginx":
        from . import templates
        okc, errs = templates.write_site_configs(site)
        if not okc:
            return "конфиг nginx не применён: %s" % errs
        return ""
    # apache / nginx+apache: защита на уровне .htaccess
    ht = os.path.join(_docroot(site), "pma", ".htaccess")
    try:
        with open(ht, "w", encoding="utf-8") as f:
            f.write("AuthType Basic\nAuthName \"phpMyAdmin\"\n"
                    "AuthUserFile %s\nRequire valid-user\n" % path)
        run(["chown", "www-data:www-data", ht], as_root=True)
    except OSError as e:
        return "не удалось записать .htaccess: %s" % e
    return ""


def install(site_domain, protect=True, password=""):
    """Установка phpMyAdmin в сайт (запускается в фоне). Пароль папки
    можно передать из формы — иначе генерируется на сервере."""
    site = next((s for s in CTX.store.data.get("sites", [])
                 if s["domain"] == site_domain), None)
    if not site:
        return False, "сайт не найден"
    if not site.get("php"):
        return False, "phpMyAdmin требует PHP-сайт"
    password = (password or "").strip()
    if protect and password and len(password) < 6:
        return False, "пароль папки короче 6 символов"
    docroot = _docroot(site)
    pma_dir = os.path.join(docroot, "pma")
    if os.path.exists(pma_dir):
        return False, "папка pma уже существует в этом сайте"

    from .packages import _run_bg

    if CTX.demo:
        def demo_job():
            _task_log("демо: установка phpMyAdmin в %s" % site_domain)
            _task_log("готово: http://%s/pma/" % site_domain)
        return _run_bg("pma-install", demo_job)

    def job():
        pw = password or _gen_password()
        tmp = tempfile.mkdtemp(prefix="pma-")
        try:
            e = _download(os.path.join(tmp, "pma.tar.gz"))
            if e:
                _task_log("ОШИБКА: %s" % e)
                CTX.store.notify("phpMyAdmin: %s" % e, "error")
                return
            os.makedirs(pma_dir)
            _task_log("распаковка…")
            with tarfile.open(os.path.join(tmp, "pma.tar.gz")) as tf:
                tf.extractall(pma_dir, members=_safe_members(tf),
                              filter="data")
            # в архиве один корневой каталог phpMyAdmin-x.y.z/
            entries = os.listdir(pma_dir)
            if len(entries) == 1 and os.path.isdir(
                    os.path.join(pma_dir, entries[0])):
                inner = os.path.join(pma_dir, entries[0])
                for name in os.listdir(inner):
                    shutil.move(os.path.join(inner, name),
                                os.path.join(pma_dir, name))
                os.rmdir(inner)
            _task_log("конфигурация…")
            blowfish = "".join(secrets.choice(BLOWFISH_CHARS)
                               for _ in range(32))
            os.makedirs(os.path.join(pma_dir, "tmp"), exist_ok=True)
            with open(os.path.join(pma_dir, "config.inc.php"), "w",
                      encoding="utf-8") as f:
                f.write("<?php\n"
                        "// сгенерировано HostPanel\n"
                        "$cfg['blowfish_secret'] = '%s';\n"
                        "$cfg['TempDir'] = __DIR__ . '/tmp/';\n"
                        "$cfg['Servers'][1]['host'] = 'localhost';\n"
                        "$cfg['Servers'][1]['auth_type'] = 'cookie';\n"
                        % blowfish)
            run(["chown", "-R", "www-data:www-data", pma_dir],
                as_root=True)
            run(["find", pma_dir, "-type", "d", "-exec", "chmod", "750",
                 "{}", "+"], as_root=True)
            _ensure_php_modules(site)
            prot_err = ""
            if protect:
                prot_err = _write_protection(site, pw)
                if prot_err:
                    _task_log("предупреждение: %s" % prot_err)
            with STATE_LOCK:
                site.setdefault("apps", {})["pma"] = {
                    "protected": protect and not prot_err,
                    "user": "pma", "password": pw,
                    "version": PMA_VERSION, "ts": utils.now_str()}
                CTX.store.save()
            ssl = (site.get("ssl") or {}).get("kind", "none")
            port = ":8081" if site["webserver"] == "apache" \
                and ssl == "none" else ""
            url = "%s://%s%s/pma/" % ("https" if ssl != "none" else "http",
                                      site["domain"], port)
            _task_log("готово: %s" % url)
            msg = "phpMyAdmin установлен: %s" % url
            if protect and not prot_err:
                msg += " (закрыт паролем — доступы в разделе ПО)"
            CTX.store.notify(msg, "ok")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return _run_bg("pma-install", job)


def _ensure_php_modules(site):
    """Лучше-усилие: ставит php-модули, нужные phpMyAdmin (zip, gd)."""
    php = site.get("php") or "8.2"
    code, out, _ = run(["php%s" % php, "-m"], timeout=20)
    have_mods = set((out or "").lower().split())
    missing = [m for m in ("zip", "gd", "mbstring") if m not in have_mods]
    if not missing:
        return
    _task_log("установка PHP-модулей: %s" % ", ".join(missing))
    pkgs = ["php%s-%s" % (php, m) for m in missing]
    run(["apt-get", "install", "-y"] + pkgs, timeout=600, as_root=True)


def remove(site_domain):
    """Удаление папки /pma и защиты из конфига сайта."""
    site = next((s for s in CTX.store.data.get("sites", [])
                 if s["domain"] == site_domain), None)
    if not site:
        return False, "сайт не найден"
    pma_dir = os.path.join(_docroot(site), "pma")
    if not os.path.exists(pma_dir):
        return False, "phpMyAdmin в этом сайте не найден"

    from .packages import _run_bg

    if CTX.demo:
        def demo_job():
            _task_log("демо: удаление phpMyAdmin из %s" % site_domain)
        return _run_bg("pma-remove", demo_job)

    def job():
        shutil.rmtree(pma_dir, ignore_errors=True)
        try:
            os.remove(_htpasswd_path(site))
        except OSError:
            pass
        with STATE_LOCK:
            if (site.get("apps") or {}).get("pma"):
                del site["apps"]["pma"]
                if not site["apps"]:
                    del site["apps"]
                CTX.store.save()
        from . import templates
        templates.write_site_configs(site)
        _task_log("phpMyAdmin удалён из %s" % site_domain)
        CTX.store.notify("phpMyAdmin удалён из сайта %s" % site["domain"],
                         "info")

    return _run_bg("pma-remove", job)
