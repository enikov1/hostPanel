# -*- coding: utf-8 -*-
"""API: бэкапы, базы данных, cron, брандмауэр, файловый менеджер."""
import json
import os
import urllib.parse

from .. import config, utils
from ..context import CTX, fm_allowed, run, site_docroot_abs
from ..core import backup, db as db_mod, services, files as files_mod
from .router import get, post, ok, err, done


# ------------------------------------------------------------- бэкапы ---
@get("/api/backups")
def backups_list(handler, qs):
    return ok(backups=CTX.store.data.get("backups", []))


@post("/api/backups/create")
def backups_create(handler, body):
    meta = backup.create(body.get("site_ids"), bool(body.get("with_db", True)))
    return done("резервная копия создана: %s"
                % utils.human_size(meta["size"]), {"backup": meta})


@post("/api/backups/restore")
def backups_restore(handler, body):
    okc, msg = backup.restore(body.get("id"), body.get("domains"))
    if okc:
        return done(msg)
    return err(msg, 500)


@post("/api/backups/delete")
def backups_delete(handler, body):
    backup.delete(body.get("id"))
    return done("копия удалена")


# ------------------------------------------------------------------ БД ---
@get("/api/db")
def db_list(handler, qs):
    # обе СУБД одним списком: у каждой записи поле engine, UI фильтрует
    dbs = db_mod.list_dbs("mysql") + db_mod.list_dbs("pg")
    return ok(dbs=dbs, engines=db_mod.engines(),
              mysql_available=db_mod.available())


@post("/api/db/create")
def db_create(handler, body):
    name = str(body.get("name") or "").lower()
    user = str(body.get("user") or "").lower()
    engine = str(body.get("engine") or "mysql")
    if not db_mod.engine_ok(engine):
        return err("СУБД %s не установлена" %
                   db_mod.engine_name(engine), 400)
    if not db_mod.valid_name(name, engine) or \
            not db_mod.valid_name(user, engine):
        return err("имя базы и пользователя: латиница, цифры, _, "
                   "до 63 симв.")
    okc, errs = db_mod.create(name, user, body.get("password") or
                              utils.gen_password(), engine)
    if okc:
        return done("база %s создана (%s)"
                    % (name, db_mod.engine_name(engine)))
    return err(errs, 500)


@post("/api/db/delete")
def db_delete(handler, body):
    name = str(body.get("name") or "").lower()
    engine = str(body.get("engine") or "mysql")
    if not db_mod.valid_name(name, engine):
        return err("некорректное имя базы")
    okc, msg = db_mod.delete(name, engine)
    if okc:
        return done("база %s удалена" % name)
    return err(msg, 500)


@get("/api/db/users")
def db_users(handler, qs):
    name = (qs.get("name", [""])[0] or "").lower()
    engine = (qs.get("engine", ["mysql"])[0] or "mysql")
    if not db_mod.valid_name(name, engine):
        return err("некорректное имя базы")
    return ok(users=db_mod.users(name, engine))


@post("/api/db/pass")
def db_pass(handler, body):
    """Смена пароля пользователя базы данных."""
    name = str(body.get("name") or "").lower()
    user = str(body.get("user") or "").lower()
    engine = str(body.get("engine") or "mysql")
    okc, errs = db_mod.change_password(name, user,
                                       body.get("password") or "", engine)
    if okc:
        return done("пароль пользователя %s изменён" % user)
    return err(errs, 400)


def db_export_file(qs):
    """Готовит временный файл дампа; вызывается из server (do_GET).

    Возвращает (path, filename, error, code)."""
    import datetime
    import tempfile
    name = (qs.get("name", [""])[0] or "").lower()
    engine = (qs.get("engine", ["mysql"])[0] or "mysql")
    if not db_mod.valid_name(name, engine):
        return None, None, "некорректное имя базы", 400
    if not db_mod.engine_ok(engine):
        return None, None, ("СУБД %s не установлена"
                            % db_mod.engine_name(engine)), 400
    okc, data = db_mod.dump(name, engine)
    if not okc:
        return None, None, ("дамп не создан: %s" % (data or
                            "ошибка mysqldump/pg_dump"))[:400], 500
    fd, path = tempfile.mkstemp(prefix="hp-export-", suffix=".sql")
    with os.fdopen(fd, "wb") as f:
        f.write(data.encode("utf-8", "replace"))
    fname = "%s_%s.sql" % (name,
                           datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    return path, fname, "", 0


@post("/api/db/import")
def db_import(handler, body):
    """Импорт SQL-дампа в базу (multipart: name, engine, file).

    Тело читается из handler напрямую (как в /api/files/upload)."""
    if getattr(handler, "_oversized", False):
        return err("файл слишком большой", 413)
    ctype = handler.headers.get("Content-Type", "")
    parts = utils.parse_multipart(handler.read_body(), ctype)
    name, engine, data, fname = "", "mysql", None, ""
    for part in parts:
        if part["name"] == "name":
            name = part["data"].decode("utf-8", "replace").strip().lower()
        elif part["name"] == "engine":
            engine = (part["data"].decode("utf-8", "replace").strip()
                      or "mysql")
        elif part["name"] == "file" and part["filename"]:
            data, fname = part["data"], part["filename"]
    if data is None:
        return err("файл не найден в запросе", 400)
    if len(data) > config.MAX_UPLOAD_BODY:
        return err("файл больше 200 МБ", 400)
    if not db_mod.engine_ok(engine):
        return err("СУБД %s не установлена" % db_mod.engine_name(engine),
                   400)
    if not db_mod.valid_name(name, engine):
        return err("некорректное имя базы", 400)
    okc, msg = db_mod.import_dump(name, data, fname, engine)
    if okc:
        return done(msg)
    return err(msg, 500)


@post("/api/cron/run")
def cron_run(handler, body):
    """Разовый запуск задачи планировщика — «проверить, что работает»."""
    import time as _time
    try:
        idx = int(body.get("index", -1))
    except (TypeError, ValueError):
        return err("некорректный номер задачи")
    jobs = CTX.store.data.get("cron", [])
    if not (0 <= idx < len(jobs)):
        return err("задача не найдена")
    cmd = str(jobs[idx].get("command") or "").strip()
    if not cmd:
        return err("у задачи нет команды")
    CTX.store.log_action("Ручной запуск задачи cron: %s" % cmd)
    # cron выполняет команду через /bin/sh — так же и здесь: работают
    # перенаправления, конвейеры и &&, как в настоящем расписании
    t0 = _time.time()
    code, out, errtxt = run(["/bin/sh", "-c", cmd], timeout=120)
    took = max(1, int((_time.time() - t0) * 1000))
    tail = ((out or "") + ("\n" + errtxt if errtxt else "")).strip()
    _append_manual_log(cmd, code, tail, took)
    return ok(code=code, output=tail[-2000:])


def _append_manual_log(cmd, code, tail, took_ms):
    """Ручной запуск пишется в журнал задачи — как настоящий запуск."""
    import datetime
    try:
        from ..core import services
        path = services.cron_log_slot(cmd)
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write("=== %s запускаю: %s (вручную)\n" % (stamp, cmd))
            if tail:
                f.write("\n".join(tail.splitlines()[-25:]) + "\n")
            f.write("[код завершения: %d, время: %d мс]\n" % (code, took_ms))
    except OSError:
        pass


@get("/api/cron/log")
def cron_log(handler, qs):
    """Журнал запусков задачи (последние 60 строк)."""
    command = qs.get("command", [""])[0]
    if not command:
        return err("не указана команда")
    from ..core import services
    return ok(lines=services.cron_read_log(command))


@post("/api/db/query")
def db_query(handler, body):
    """SQL-консоль: произвольный запрос к выбранной базе."""
    name = str(body.get("db") or "").lower()
    sql = str(body.get("sql") or "")
    engine = str(body.get("engine") or "mysql")
    if len(sql) > 200_000:
        return err("запрос слишком длинный (>200 КБ)")
    okc, columns, rows, info = db_mod.query(name, sql, engine)
    if not okc:
        return err(info, 400)
    return ok(columns=columns, rows=rows, info=info)


# --------------------------------------------------------------- cron ---
@get("/api/cron")
def cron_list(handler, qs):
    st = CTX.store.data
    return ok(jobs=st.get("cron", []),
              system_jobs=services.cron_read_system(),
              auto=st["settings"].get("auto_backup_enabled", False),
              auto_cron=st["settings"].get("auto_backup_cron", ""),
              ssl_auto=st["settings"].get("ssl_autorenew_enabled", True),
              ssl_auto_cron=st["settings"].get("ssl_renew_cron",
                                               "30 3,15 * * *"))


@post("/api/cron/save")
def cron_save(handler, body):
    st = CTX.store.data
    jobs = body.get("jobs", [])
    if not isinstance(jobs, list):
        return err("некорректный список задач")
    for j in jobs:
        if not isinstance(j, dict):
            return err("некорректная задача")
        if not services.valid_cron_expr(j.get("expr") or ""):
            return err("некорректное расписание: %s" % j.get("expr"))
        cmd = str(j.get("command") or "")
        if not cmd or len(cmd) > 500 or "\n" in cmd or "\r" in cmd:
            return err("некорректная команда")
    st["cron"] = jobs
    if body.get("auto") is not None:
        expr = body.get("auto_cron") or "0 3 * * *"
        if not services.valid_cron_expr(expr):
            return err("некорректное расписание автобэкапа: %s" % expr)
        st["settings"]["auto_backup_enabled"] = bool(body["auto"])
        st["settings"]["auto_backup_cron"] = expr
    if body.get("ssl_auto") is not None:
        ssl_expr = body.get("ssl_auto_cron") or "30 3,15 * * *"
        if not services.valid_cron_expr(ssl_expr):
            return err("некорректное расписание автопродления SSL: %s"
                       % ssl_expr)
        st["settings"]["ssl_autorenew_enabled"] = bool(body["ssl_auto"])
        st["settings"]["ssl_renew_cron"] = ssl_expr
    # в crontab пишем ВСЕ служебные задачи (пользовательские + автобэкап +
    # автопродление SSL) — единый источник: services._cron_system_jobs
    services.cron_write_system(services._cron_system_jobs(st))
    return done("планировщик сохранён")


# --------------------------------------------------------- брандмауэр ---
@get("/api/firewall")
def firewall(handler, qs):
    return ok(**services.firewall_status())


@post("/api/firewall/add")
def firewall_add(handler, body):
    import re
    port = str(body.get("port", ""))
    if not re.match(r"^\d{1,5}(/\d{1,5})?(:\d{1,5})?$", port):
        return err("некорректный порт")
    # диапазон (8000:8080, 100/200) — проверяем ОБА конца на 1–65535
    for part in re.split(r"[:/]", port):
        if not (1 <= int(part) <= 65535):
            return err("некорректный порт")
    if body.get("action", "allow") not in ("allow", "deny"):
        return err("некорректное действие")
    proto = str(body.get("proto", "tcp") or "tcp").lower()
    if proto not in ("tcp", "udp", "both"):
        return err("некорректный протокол (tcp/udp)")
    # ufw: proto указывается один раз; 'both' — правило без proto
    okc, errs = services.firewall_add(port, body.get("action", "allow"),
                                      "" if proto == "both" else proto,
                                      body.get("comment", ""))
    if okc:
        return done("правило добавлено")
    return err(errs, 500)


# ---------------------------------------------------------------- файлы ---
@get("/api/files")
def files_list(handler, qs):
    path = qs.get("path", [""])[0] or (
        os.path.join(CTX.home, "demo_www") if CTX.demo else CTX.www_root)
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    data, e = files_mod.list_dir(path)
    if e:
        return err(e, 400)
    return ok(**data)


@get("/api/files/read")
def files_read(handler, qs):
    path = qs.get("path", [""])[0]
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    text, e = files_mod.read(path)
    if e:
        return err(e, 400)
    return ok(content=text)


@post("/api/files/mkdir")
def files_mkdir(handler, body):
    path = body.get("path", "")
    if not fm_allowed(os.path.join(path, "x")):
        return err("путь недоступен", 403)
    okc, e = files_mod.mkdir(path)
    if okc:
        return done("папка создана")
    return err(e, 500)


@post("/api/files/save")
def files_save(handler, body):
    path = body.get("path", "")
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    okc, e = files_mod.save(path, body.get("content", ""))
    if okc:
        return done("файл сохранён")
    return err(e, 500)


@post("/api/files/delete")
def files_delete(handler, body):
    paths = body.get("paths", [])
    if not isinstance(paths, list) or len(paths) > 200:
        return err("некорректный список путей")
    errs = []
    for path in paths:
        if not fm_allowed(path):
            errs.append("%s: путь недоступен" % path)
            continue
        okc, e = files_mod.delete(path)
        if not okc:
            errs.append("%s: %s" % (path, e))
    if errs:
        return err("; ".join(errs[:5]), 500)
    return done("удалено объектов: %d" % len(paths))


@post("/api/files/rename")
def files_rename(handler, body):
    path = body.get("path", "")
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    okc, res = files_mod.rename(path, body.get("new_name", ""))
    if okc:
        return done("переименовано в %s" % res)
    return err(res, 500)


@post("/api/files/move")
def files_move(handler, body):
    """Перемещение объектов в папку (drag&drop, вырезать/вставить)."""
    paths = body.get("paths", [])
    dest_dir = body.get("dest", "")
    if not isinstance(paths, list) or not dest_dir or             not fm_allowed(dest_dir):
        return err("некорректный запрос")
    errs = []
    moved = 0
    for path in paths:
        if not fm_allowed(path):
            errs.append("%s: путь недоступен" % path)
            continue
        okc, e = files_mod.move(path, dest_dir)
        if okc:
            moved += 1
        else:
            errs.append("%s: %s" % (os.path.basename(path), e))
    if errs:
        return err("; ".join(errs[:5]), 500)
    return done("перемещено объектов: %d" % moved)


@post("/api/files/copy")
def files_copy(handler, body):
    """Копирование объектов в папку."""
    paths = body.get("paths", [])
    dest_dir = body.get("dest", "")
    if not isinstance(paths, list) or not dest_dir or             not fm_allowed(dest_dir):
        return err("некорректный запрос")
    errs = []
    copied = 0
    for path in paths:
        if not fm_allowed(path):
            errs.append("%s: путь недоступен" % path)
            continue
        okc, e = files_mod.copy(path, dest_dir)
        if okc:
            copied += 1
        else:
            errs.append("%s: %s" % (os.path.basename(path), e))
    if errs:
        return err("; ".join(errs[:5]), 500)
    return done("скопировано объектов: %d" % copied)


@post("/api/files/chmod")
def files_chmod(handler, body):
    path = body.get("path", "")
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    octal = str(body.get("octal", "644"))
    if len(octal) > 4 or not all(c in "01234567" for c in octal):
        return err("некорректные права")
    okc, e = files_mod.chmod(path, octal)
    if okc:
        return done("права изменены")
    return err(e, 500)


@post("/api/files/extract")
def files_extract(handler, body):
    path = body.get("path", "")
    if not fm_allowed(path):
        return err("путь недоступен", 403)
    okc, res = files_mod.extract(path)
    if okc:
        return done("распаковано в %s" % res, {"dest": res})
    return err(res, 500)


@post("/api/files/zip")
def files_zip(handler, body):
    paths = body.get("paths", [])
    if not isinstance(paths, list):
        return err("некорректный список путей")
    for p in paths:
        if not fm_allowed(p):
            return err("путь недоступен: %s" % p, 403)
    dest = body.get("dest", "archive.zip")
    if not fm_allowed(dest):
        return err("путь недоступен", 403)
    okc, res = files_mod.zip_paths(paths, dest)
    if okc:
        return done("архив создан: %s" % res, {"dest": res})
    return err(res, 500)


@post("/api/files/upload")
def files_upload(handler, body):
    if getattr(handler, "_oversized", False):
        return err("файл слишком большой", 413)
    ctype = handler.headers.get("Content-Type", "")
    parts = utils.parse_multipart(handler.read_body(), ctype)
    dest_dir = urllib.parse.parse_qs(
        urllib.parse.urlparse(handler.path).query).get("dest", [""])[0]
    if not dest_dir or not fm_allowed(dest_dir):
        return err("путь недоступен", 403)
    saved = 0
    for part in parts:
        if part["name"] != "file" or not part["filename"]:
            continue
        okc, e = files_mod.upload(dest_dir, part["filename"], part["data"])
        if okc:
            saved += 1
        else:
            return err("загрузка %s: %s" % (part["filename"], e), 500)
    if saved:
        return done("загружено файлов: %d" % saved)
    return err("файл не найден в запросе", 400)


# ------------------------------------------------- заглушка IP-адреса ---
@get("/api/default-site")
def default_site_get(handler, qs):
    """Содержимое заглушки для IP-адреса сервера (редактируется в панели)."""
    path = os.path.join(config.DEFAULT_SITE_DIR, "placeholder.html")
    if CTX.demo:
        return ok(content=config.DEFAULT_PLACEHOLDER_HTML, path=path,
                  demo=True)
    content = ""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        content = config.DEFAULT_PLACEHOLDER_HTML
    return ok(content=content, path=path)


@post("/api/default-site")
def default_site_save(handler, body):
    content = str(body.get("content") or "")
    if len(content) > 300_000:
        return err("страница слишком большая (>300 КБ)")
    if CTX.demo:
        return done("демо: заглушка сохранена (на диске ничего не менялось)")
    d = config.DEFAULT_SITE_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "placeholder.html")
    tmp = path + ".hp-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)
    return done("заглушка для IP-адреса сохранена — перезагрузка nginx "
                "не нужна, страница статическая")


# ------------------------------------------------------------ настройки ---
@get("/api/settings")
def settings_get(handler, qs):
    st = CTX.store.data
    disk_total = sum(utils.dir_size(site_docroot_abs(s) if not CTX.demo
                                    else os.path.join(CTX.home, s["docroot"]))
                     for s in st["sites"])
    return ok(settings=st["settings"], disk_total_sites=disk_total)


@get("/api/settings/export")
def settings_export(handler, qs):
    """Слепок настроек для переноса на другой сервер."""
    from ..core import migrate
    return ok(data=migrate.export_data())


@post("/api/settings/import")
def settings_import(handler, body):
    """Применение слепка настроек (создаёт отсутствующие сайты)."""
    from ..core import migrate
    data = body.get("data")
    okc, summary, report = migrate.import_data(data)
    if not okc:
        return err("; ".join(report), 400)
    CTX.store.log_action("Импорт настроек: %s" % summary)
    return ok(summary=summary, report=report)


@post("/api/settings/save")
def settings_save(handler, body):
    sset = CTX.store.data["settings"]
    if "theme" in body and body["theme"] in ("dark", "light"):
        sset["theme"] = body["theme"]
    if "backup_retention" in body:
        try:
            v = int(body["backup_retention"])
            if not (1 <= v <= 365):
                return err("хранение копий: 1–365")
            sset["backup_retention"] = v
        except (TypeError, ValueError):
            return err("хранение копий должно быть числом")
    if "panel_port" in body:
        try:
            v = int(body["panel_port"])
            if not (1024 <= v <= 65535):
                return err("порт: 1024–65535")
            sset["panel_port"] = v
        except (TypeError, ValueError):
            return err("порт должен быть числом")
    if "health_interval" in body:
        try:
            v = int(body["health_interval"])
            if not (15 <= v <= 3600):
                return err("интервал проверок: 15–3600 сек")
            sset["health_interval"] = v
        except (TypeError, ValueError):
            return err("интервал проверок должен быть числом")
    if "fm_restricted" in body:
        sset["fm_restricted"] = bool(body["fm_restricted"])
    if "expert_mode" in body:
        sset["expert_mode"] = bool(body["expert_mode"])
    if isinstance(body.get("notify"), dict):
        src = body["notify"]
        cur = sset.setdefault("notify", {})
        cur.setdefault("email", {})
        cur.setdefault("tg", {})
        for k in ("enabled", "host", "port", "user", "pass", "from", "to"):
            if k in (src.get("email") or {}):
                v = src["email"][k]
                if k == "enabled":
                    cur["email"][k] = bool(v)
                elif k == "port":
                    cur["email"][k] = int(v) if str(v).isdigit() else 587
                else:
                    cur["email"][k] = str(v or "")
        for k in ("enabled", "token", "chat"):
            if k in (src.get("tg") or {}):
                v = src["tg"][k]
                cur["tg"][k] = bool(v) if k == "enabled" else str(v or "")
        if "security" in src:
            cur["security"] = {"enabled": bool(
                (src.get("security") or {}).get("enabled"))}
        CTX.store.save()
    return done("настройки сохранены")


@post("/api/notify/test")
def notify_test(handler, body):
    """Тестовая отправка во включённые каналы — проверка настройки."""
    from ..core import notify
    errors = notify.send("HostPanel: тест уведомлений",
                         "Это тестовое сообщение из панели. "
                         "Если оно пришло — уведомления работают.")
    if errors:
        return err("не ушло: " + "; ".join(errors), 400)
    return done("тестовое уведомление отправлено")


@post("/api/password/change")
def password_change(handler, body):
    store = CTX.store
    from ..api import auth
    if not auth.verify(body.get("old", ""), store.creds):
        return err("текущий пароль указан неверно", 400)
    new_pw = body.get("new", "")
    if len(new_pw) < 8:
        return err("пароль слишком короткий — минимум 8 символов", 400)
    if new_pw == "admin":
        return err("пароль «admin» запрещён — придумайте надёжный", 400)
    from ..state import pbkdf2
    import secrets as _secrets
    store.creds["salt"] = _secrets.token_hex(16)
    store.creds["hash"] = pbkdf2(new_pw, store.creds["salt"])
    store.creds.pop("must_change_password", None)
    store.creds.pop("is_default", None)
    pw_file = os.path.join(store.home, "admin.txt")
    if os.path.exists(pw_file):
        try:
            os.remove(pw_file)
        except OSError:
            pass
    import json as _json
    with open(store.cred_path, "w", encoding="utf-8") as f:
        _json.dump(store.creds, f, ensure_ascii=False, indent=2)
    return done("пароль изменён")
