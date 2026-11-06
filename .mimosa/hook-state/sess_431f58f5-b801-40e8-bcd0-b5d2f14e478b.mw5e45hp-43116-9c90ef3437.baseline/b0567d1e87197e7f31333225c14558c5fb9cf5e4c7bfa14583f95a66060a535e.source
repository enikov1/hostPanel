# -*- coding: utf-8 -*-
"""Маршрутизатор API: собирает таблицу маршрутов из модулей api/*.

Каждый модуль регистрирует обработчики GET/POST c префиксами /api/...
Маршруты объявлены явно — никакой динамики по строкам запроса.
"""
import re

from .. import config
from .. import utils
from ..context import CTX

ROUTES_GET = []
ROUTES_POST = []


def get(path):
    def deco(fn):
        ROUTES_GET.append((path, fn))
        return fn
    return deco


def post(path):
    def deco(fn):
        ROUTES_POST.append((path, fn))
        return fn
    return deco


def dispatch_get(route, qs, handler):
    """Возвращает (obj, code) или (None, 0) если ответ уже отправлен."""
    for path, fn in ROUTES_GET:
        m = _match(path, route)
        if m is not None:
            return fn(handler, qs, *m)
    return {"ok": False, "error": "маршрут не найден"}, 404


def dispatch_post(route, body, handler):
    for path, fn in ROUTES_POST:
        m = _match(path, route)
        if m is not None:
            return fn(handler, body, *m)
    return {"ok": False, "error": "маршрут не найден"}, 404


def _match(pattern, route):
    """Паттерн с параметрами :name -> список значений или None."""
    if pattern == route:
        return []
    rx = re.sub(r":(\w+)", r"(\\d+)", pattern)
    m = re.match("^" + rx + "$", route)
    if not m:
        return None
    return [int(g) for g in m.groups()]


# ---- общий помощник для ответов --------------------------------------------

def ok(**extra):
    r = {"ok": True}
    r.update(extra)
    return r, 200


def err(message, code=400):
    return {"ok": False, "error": message}, code


def done(message, extra=None):
    """Успешная мутация: аудит + сохранение состояния."""
    store = CTX.store
    store.log_action(message)
    store.save()
    r = {"ok": True, "message": message}
    if extra:
        r.update(extra)
    return r, 200


def site_or_404(body):
    site = CTX.store.find_site(body.get("id"))
    if not site:
        return None, err("сайт не найден", 404)
    return site, None
