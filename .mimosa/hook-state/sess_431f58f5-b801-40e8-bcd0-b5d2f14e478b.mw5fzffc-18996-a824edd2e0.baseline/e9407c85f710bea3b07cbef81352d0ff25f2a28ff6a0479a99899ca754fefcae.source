# -*- coding: utf-8 -*-
"""Маршруты движка Omro (cld): установка на сайт, статус, журнал."""
from .router import get, post, ok, err
from ..context import CTX, STATE_LOCK
from .. import utils
from ..core import cld as cld_mod, db as db_mod


def _site(handler, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return None, err("сайт не найден", 404)
    return site, None


@get("/api/site/:sid/cld")
def cld_status(handler, qs, sid):
    """Статус движка: установлен/идёт установка/журнал/токен."""
    site, e = _site(handler, sid)
    if e:
        return e
    running, log, error, done = cld_mod.task_for_site(site["id"])
    cld = site.get("cld") or {}
    return ok(cld=cld, running=running, log=log, error=error,
              task_done=done)


@post("/api/site/:sid/cld/install")
def cld_install(handler, body, sid):
    """Установка движка на сайт.

    body: {db_mode: "new"|"existing", db_name?, db_password?,
           confirm_overwrite?: bool}
    """
    site, e = _site(handler, sid)
    if e:
        return e

    # --- проверки окружения ---
    if not site.get("php"):
        return err("для движка нужен PHP — выберите версию во вкладке "
                   "«PHP и FPM»")
    if not site.get("fpm"):
        return err("для движка нужен пул PHP-FPM (вкладка «PHP и FPM»)")

    # --- БД: новая или существующая ---
    db_mode = body.get("db_mode") or "new"
    if db_mode not in ("new", "existing"):
        return err("некорректный режим базы данных")
    import re
    domain = site["domain"]

    if db_mode == "new":
        # новая база: имя автогенерируется или проверяется
        import secrets as _secrets
        suffix = re.sub(r"[^a-z0-9]", "", domain.lower())[:20] or "site"
        db_name = str(body.get("db_name") or "").strip().lower() or \
            ("cld_" + suffix)
        db_user = ("cld_" + suffix)[:32]
        db_password = _secrets.token_urlsafe(18)
        if not db_mod.valid_name(db_name, "mysql"):
            return err("некорректное имя базы данных")
        okc, msg = db_mod.create(db_name, db_user, db_password, "mysql")
        if not okc:
            return err("создание базы: " + msg)
        CTX.store.log_action("движок Omro: создана база %s" % db_name)
    else:
        db_name = str(body.get("db_name") or "").strip().lower()
        db_password = str(body.get("db_password") or "")
        if not db_name or not db_mod.valid_name(db_name, "mysql"):
            return err("укажите существующую базу данных")
        if not db_password:
            return err("укажите пароль существующей базы данных")

    # --- предупреждение о перезаписи подтверждено? ---
    if not body.get("confirm_overwrite"):
        return err("подтвердите, что файлы в корневой папке могут быть "
                   "перезаписаны движком")

    # --- токен админки ---
    import secrets as _secrets
    admin_token = _secrets.token_hex(24)

    if CTX.demo:
        # демо-симуляция: без запуска скрипта, чтобы вкладку можно было
        # посмотреть на любой машине (например, Windows)
        def _demo_worker():
            import time as _t
            for line in ("Скачиваю установщик движка…",
                         "Установка Omro (PANEL_MODE=1)…",
                         "Ставлю зависимости (composer, npm)…",
                         "Миграции базы данных…",
                         "Сборка интерфейсов…",
                         "Готово! Движок Omro установлен (демо)."):
                cld_mod._log(line)
                _t.sleep(0.8)
            with STATE_LOCK:
                site["engine_cld"] = True
                site["cld"] = {"engine": "omro", "version": "demo",
                               "installed_at": utils.now_str(),
                               "db_name": db_name, "db_user": db_user,
                               "db_password": db_password,
                               "admin_token": admin_token}
                CTX.store.save()
                cld_mod.TASK.update({"running": False, "done": True})
        import threading as _th
        _th.Thread(target=_demo_worker, daemon=True).start()
        return ok(message="демо: установка движка запущена",
                  admin_token=admin_token)

    okc, msg = cld_mod.install_task(site, db_name, db_user, db_password,
                                    admin_token)
    if not okc:
        return err(msg)
    CTX.store.log_action("движок Omro: установка запущена для %s "
                         "(база %s)" % (domain, db_name))
    return ok(message=msg, admin_token=admin_token)
