# -*- coding: utf-8 -*-
"""Маршруты каталога движков: список, установка, статус/журнал."""
from .router import get, post, ok, err
from ..context import CTX
from ..core import engines as engines_mod


@get("/api/engines")
def engines_catalog(handler, qs):
    """Каталог доступных движков."""
    return ok(engines=engines_mod.ENGINES)


def _site(handler, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return None, err("сайт не найден", 404)
    return site, None


@get("/api/site/:sid/engine")
def engine_status(handler, qs, sid):
    """Статус установки движков на сайте + журнал текущей задачи."""
    site, e = _site(handler, sid)
    if e:
        return e
    running, log, error, done = engines_mod.task_for_site(site["id"])
    return ok(engines=site.get("engines") or {}, running=running,
              log=log, error=error, task_done=done)


@post("/api/site/:sid/engine/install")
def engine_install(handler, body, sid):
    """Установка выбранного движка на сайт.

    body: {engine: "omro"|"wordpress"|..., db_mode?: "new"|"existing",
           db_name?, db_user?, db_password?, site_title?, admin_email?,
           dist_b64?, dist_name? (для dle), confirm_overwrite?: bool}
    """
    site, e = _site(handler, sid)
    if e:
        return e
    engine = str(body.get("engine") or "")
    if engine not in engines_mod.ENGINES:
        return err("неизвестный движок")

    if not site.get("php"):
        return err("для движка нужен PHP — выберите версию во вкладке "
                   "«PHP и FPM»")

    # повторная установка уже установленного движка — только с confirm
    if (site.get("engines") or {}).get(engine) and \
            not body.get("confirm_reinstall"):
        return err("движок уже установлен — подтвердите переустановку")

    # DLE: дистрибутив должен быть загружен пользователем
    if engine == "dle" and not body.get("dist_b64"):
        return err("загрузите ZIP-дистрибутив DLE")

    okc, msg = engines_mod.install_task(site, engine, dict(body))
    if not okc:
        return err(msg)
    CTX.store.log_action("установка движка %s на %s запущена"
                         % (engine, site["domain"]))
    return ok(message=msg)


@post("/api/site/:sid/engine/remove")
def engine_remove(handler, body, sid):
    """Сброс отметки об установленном движке (файлы не удаляются)."""
    site, e = _site(handler, sid)
    if e:
        return e
    engine = str(body.get("engine") or "")
    eng = site.get("engines") or {}
    if engine not in eng:
        return err("движок не установлен")
    del eng[engine]
    if engine == "wordpress":
        site.pop("engine_wp", None)
    CTX.store.log_action("движок %s снят с сайта %s (файлы сохранены)"
                         % (engine, site["domain"]))
    CTX.store.save()
    return ok(message="отметка снята — файлы движка в корневой папке "
                      "удалите вручную при необходимости")
