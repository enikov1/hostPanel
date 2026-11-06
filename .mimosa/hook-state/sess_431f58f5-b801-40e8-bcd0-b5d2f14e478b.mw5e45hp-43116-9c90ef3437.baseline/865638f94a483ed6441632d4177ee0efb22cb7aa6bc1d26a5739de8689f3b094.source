# -*- coding: utf-8 -*-
"""API «Настройки ПО»: понятные поля, конфиги с бэкапом/откатом, пароли."""
from ..context import CTX
from ..core import swset
from .router import get, post, ok, err, done


@get("/api/swset")
def swset_list(handler, qs):
    return ok(entries=swset.list_entries())


@post("/api/swset/save")
def swset_save(handler, body):
    entry_id = str(body.get("id") or "")
    fields = body.get("fields") or {}
    if not isinstance(fields, dict):
        return err("некорректные поля")
    okc, msg = swset.save_fields(entry_id, fields)
    if not okc:
        return err(msg)
    return done(msg)


@get("/api/swset/file")
def swset_file_read(handler, qs):
    entry_id = qs.get("id", [""])[0]
    name = qs.get("name", [""])[0]
    f, text, e = swset.read_file(entry_id, name)
    if e:
        return err(e, 400)
    return ok(path=f["path"], kind=f.get("kind", ""), content=text,
              backups=swset.list_backups(entry_id, name))


@post("/api/swset/file")
def swset_file_save(handler, body):
    entry_id = str(body.get("id") or "")
    name = str(body.get("name") or "")
    content = str(body.get("content") or "")
    okc, msg = swset.save_file(entry_id, name, content)
    if not okc:
        return err(msg)
    return done(msg)


@get("/api/swset/backups")
def swset_backups(handler, qs):
    entry_id = qs.get("id", [""])[0]
    name = qs.get("name", [""])[0]
    return ok(backups=swset.list_backups(entry_id, name))


@post("/api/swset/restore")
def swset_restore(handler, body):
    entry_id = str(body.get("id") or "")
    name = str(body.get("name") or "")
    backup = str(body.get("file") or "")
    okc, msg = swset.restore_backup(entry_id, name, backup)
    if not okc:
        return err(msg)
    return done(msg)


@post("/api/swset/password")
def swset_password(handler, body):
    entry_id = str(body.get("id") or "")
    key = str(body.get("key") or "")
    password = str(body.get("password") or "")
    clear = bool(body.get("clear"))
    if CTX.demo:
        return done("в демо-режиме пароли не меняются — это демо-ответ")
    okc, msg = swset.set_password(entry_id, key, password, clear)
    if not okc:
        return err(msg)
    if password or not clear:
        # не печатаем пароль в журнал — только факт смены
        return done(msg, {"password": password} if not clear else None)
    return done(msg)
