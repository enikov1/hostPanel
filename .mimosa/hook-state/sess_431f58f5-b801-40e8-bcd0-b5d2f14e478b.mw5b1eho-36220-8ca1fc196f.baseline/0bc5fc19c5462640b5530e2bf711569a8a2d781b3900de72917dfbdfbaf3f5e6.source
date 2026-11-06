# -*- coding: utf-8 -*-
"""Маршруты обновления панели с GitHub."""
from .router import get, post, ok, err
from ..context import CTX
from ..core import panelupdate


@get("/api/panel/update")
def panel_update_status(handler, qs):
    """Текущая/последняя версия, доступность обновления, лог задачи."""
    return panelupdate.status()


@post("/api/panel/update/run")
def panel_update_run(handler, body):
    """Запуск обновления в фоне (демо-режим запрещён)."""
    okr, message = panelupdate.run_update()
    if not okr:
        return err(message, 400)
    return ok(message=message)
