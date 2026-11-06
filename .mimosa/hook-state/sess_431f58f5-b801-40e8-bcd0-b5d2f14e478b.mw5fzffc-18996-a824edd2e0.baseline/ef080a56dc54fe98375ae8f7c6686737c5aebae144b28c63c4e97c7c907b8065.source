# -*- coding: utf-8 -*-
"""Базы данных: MySQL/MariaDB и PostgreSQL — единый набор операций.

СУБД выбирается параметром engine: "mysql" (по умолчанию) или "pg".
MySQL работает через клиент mysql от root (unix-socket), PostgreSQL —
через psql от системного пользователя postgres (peer-аутентификация).
"""
import gzip
import io
import os
import re
import tempfile
import zipfile

from ..context import CTX, run, have
from .. import utils

ENGINE_META = {
    "mysql": {"id": "mysql", "name": "MariaDB / MySQL", "bin": "mysql"},
    "pg": {"id": "pg", "name": "PostgreSQL", "bin": "psql"},
}
PG_SYSTEM_DBS = ("postgres", "template0", "template1")
MYSQL_SYSTEM_DBS = ("mysql", "information_schema", "performance_schema",
                    "sys")


def engines():
    """Список СУБД с признаком «установлена» — для выбора при создании."""
    out = []
    for eid, meta in ENGINE_META.items():
        out.append(dict(meta, available=bool(CTX.demo or have(meta["bin"]))))
    return out


def available():
    """Совместимость со старым кодом: есть ли хотя бы одна СУБД."""
    return CTX.demo or have("mysql") or have("psql")


def engine_ok(engine):
    engine = engine or "mysql"
    return engine in ENGINE_META and (CTX.demo or
                                      have(ENGINE_META[engine]["bin"]))


def engine_name(engine):
    return ENGINE_META.get(engine or "mysql", {}).get("name", "MariaDB")


def valid_name(name, engine="mysql"):
    """Имя базы/пользователя: латиница, цифры, _; у PG лимит 63."""
    limit = 63 if (engine or "mysql") == "pg" else 64
    return bool(re.match(r"^[a-z0-9_]{1,%d}$" % limit, name or ""))


def _pg_psql(sql_text, db="", timeout=60, csv_mode=False):
    """Выполняет SQL от имени postgres (peer-аутентификация по сокету).

    Служебные запросы: -tA -F '|' — без заголовков и хвостов «(N rows)»,
    значения разделены «|» (имена валидированы и «|» не содержат).
    Для SQL-консоли: --csv — корректное экранирование значений.
    """
    cmd = ("psql -X --csv -v ON_ERROR_STOP=1" if csv_mode
           else "psql -X -tA -F '|' -v ON_ERROR_STOP=1")
    if db:
        cmd += " -d " + db
    return run(["su", "-", "postgres", "-c", cmd], timeout=timeout,
               input_text=sql_text)


# ------------------------------------------------------------ список баз ---
def list_dbs(engine="mysql"):
    out = []
    engine = engine or "mysql"
    if CTX.demo:
        for d in CTX.store.data.get("dbs", []):
            if d.get("engine", "mysql") != engine:
                continue
            out.append(dict(d, engine=engine))
        return out
    if not engine_ok(engine):
        return out
    if engine == "mysql":
        # SHOW всех баз (включая пустые — без таблиц они не попадают в
        # information_schema.tables и база «пропадала» из списка)
        code, stdout, _ = run(
            ["mysql", "-N", "-B", "-e",
             "SELECT schema_name FROM information_schema.schemata "
             "WHERE schema_name NOT IN %s ORDER BY schema_name;"
             % (repr(MYSQL_SYSTEM_DBS),)], as_root=True)
        sizes = {}
        code2, out2, _ = run(
            ["mysql", "-N", "-B", "-e",
             "SELECT table_schema, ROUND(SUM(data_length+index_length)), "
             "COUNT(*) FROM information_schema.tables WHERE table_schema "
             "NOT IN %s GROUP BY table_schema;" % (repr(MYSQL_SYSTEM_DBS),)],
            as_root=True)
        if code2 == 0:
            for line in out2.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    sizes[parts[0]] = (int(parts[1] or 0) * 1024,
                                       int(parts[2] or 0))
        for name in stdout.splitlines():
            name = name.strip()
            if not name:
                continue
            size, tables = sizes.get(name, (0, 0))
            out.append({"name": name, "size_bytes": size, "tables": tables,
                        "user": "", "id": 0, "engine": "mysql"})
        return out
    # PostgreSQL: имя, владелец, размер одним запросом (вывод: a|b|c)
    code, stdout, err = _pg_psql(
        "SELECT datname || '|' || pg_get_userbyid(datdba) || '|' || "
        "pg_database_size(datname) FROM pg_database WHERE NOT datistemplate "
        "AND datname NOT IN %s ORDER BY 1;" % (repr(PG_SYSTEM_DBS),))
    if code != 0:
        return out
    for line in stdout.splitlines():
        parts = line.strip().split("|")
        if not parts or not parts[0]:
            continue
        try:
            size = int(parts[2] or 0)
        except (ValueError, IndexError):
            size = 0
        out.append({"name": parts[0], "user": parts[1] if len(parts) > 1
                    else "", "size_bytes": size, "tables": 0, "id": 0,
                    "engine": "pg"})
    # число таблиц считаем по каждой базе
    for row in out:
        c2, o2, _e = _pg_psql(
            "SELECT count(*) FROM information_schema.tables WHERE "
            "table_schema NOT IN ('pg_catalog','information_schema');",
            db=row["name"], timeout=30)
        if c2 == 0:
            try:
                row["tables"] = int(o2.strip().splitlines()[0])
            except (ValueError, IndexError):
                row["tables"] = 0
    return out


# ------------------------------------------------------------- создание ---
def create(name, user, password, engine="mysql"):
    engine = engine or "mysql"
    if CTX.demo:
        CTX.store.data.setdefault("dbs", []).append(
            {"id": int(utils.now_str().replace("-", "").replace(" ", "")
                       .replace(":", "")[-9:]), "name": name, "user": user,
             "size_bytes": 0, "tables": 0, "engine": engine})
        CTX.store.save()
        return True, "демо: база создана"
    if not engine_ok(engine):
        return False, ("СУБД %s не установлена — установите её в разделе "
                       "«Установка ПО»" % engine_name(engine))
    # имена уже валидированы (только [a-z0-9_]); пароль экранируем
    if engine == "mysql":
        safe_pw = password.replace("\\", "\\\\").replace("'", "\\'")
        sql = ("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 "
               "COLLATE utf8mb4_unicode_ci;\n"
               "CREATE USER IF NOT EXISTS '%s'@'localhost' IDENTIFIED BY "
               "'%s';\n"
               "ALTER USER '%s'@'localhost' IDENTIFIED BY '%s';\n"
               "GRANT ALL PRIVILEGES ON `%s`.* TO '%s'@'localhost';\n"
               "FLUSH PRIVILEGES;" % (name, user, safe_pw, user, safe_pw,
                                      name, user))
        code, _, err = run(["mysql"], timeout=60, input_text=sql,
                           as_root=True)
        ok = code == 0
        if ok:
            CTX.store.notify("Создана база данных %s" % name)
        return ok, ("" if ok else err)
    # PostgreSQL: роль и база создаются раздельно (без IF NOT EXISTS)
    safe_pw = password.replace("'", "''")
    exists_sql = ("SELECT EXISTS (SELECT 1 FROM pg_database WHERE "
                  "datname='%s')::int || '|' || EXISTS (SELECT 1 FROM "
                  "pg_roles WHERE rolname='%s')::int;" % (name, user))
    code, out, err = _pg_psql(exists_sql, timeout=30)
    if code != 0:
        return False, (err or "не удалось подключиться к PostgreSQL")
    db_exists, user_exists = "1", "1"
    try:
        db_exists, user_exists = out.strip().split("|")
    except ValueError:
        pass
    stmts = []
    if user_exists != "1":
        stmts.append("CREATE ROLE \"%s\" LOGIN;" % user)
    if db_exists != "1":
        stmts.append("CREATE DATABASE \"%s\" OWNER \"%s\";" % (name, user))
    elif user_exists != "1":
        stmts.append("ALTER DATABASE \"%s\" OWNER TO \"%s\";" % (name, user))
    if not stmts:
        return False, ("база %s уже существует (PostgreSQL)" % name)
    stmts.append("ALTER ROLE \"%s\" LOGIN PASSWORD '%s';" % (user, safe_pw))
    code, _, err = _pg_psql(";\n".join(stmts), timeout=60)
    ok = code == 0
    if ok:
        CTX.store.notify("Создана база данных %s (PostgreSQL)" % name)
    return ok, ("" if ok else (err or "").strip() or
                "не удалось создать базу")


# -------------------------------------------------------------- удаление ---
def delete(name, engine="mysql"):
    engine = engine or "mysql"
    if CTX.demo:
        CTX.store.data["dbs"] = [d for d in CTX.store.data.get("dbs", [])
                                 if not (d["name"] == name and
                                         d.get("engine", "mysql") == engine)]
        CTX.store.save()
        return True, "демо: база %s удалена" % name
    if not engine_ok(engine):
        return False, "СУБД %s не установлена" % engine_name(engine)
    if engine == "mysql":
        sql = "DROP DATABASE IF EXISTS `%s`;" % name
        code, _out, err = run(["mysql"], input_text=sql, as_root=True,
                              timeout=60)
        if code != 0:
            return False, (err or "код %s" % code)[:200]
        return True, ""
    code, _, err = _pg_psql("DROP DATABASE \"%s\" WITH (FORCE);" % name,
                            timeout=120)
    if code != 0 and "syntax" in (err or "").lower():
        # старые версии PostgreSQL без WITH (FORCE)
        code, _, err = _pg_psql("DROP DATABASE \"%s\";" % name, timeout=120)
    if code != 0 and "does not exist" in (err or "").lower():
        return True, ""
    if code != 0:
        return False, (err or "не удалось удалить базу").strip()
    return True, ""


# ---------------------------------------------------------- пользователи ---
def users(name, engine="mysql"):
    """Пользователи с правами на базу (для показа/смены пароля)."""
    engine = engine or "mysql"
    if CTX.demo:
        return ["demo_user"]
    if not engine_ok(engine) or not valid_name(name, engine):
        return []
    if engine == "mysql":
        code, out, _ = run(["mysql", "-N", "-B", "-e",
                            "SELECT DISTINCT User FROM mysql.db WHERE "
                            "Db='%s';" % name], as_root=True)
        if code != 0:
            return []
        return [u.strip() for u in out.splitlines() if u.strip()]
    # PostgreSQL: роли с правом CONNECT к базе (владелец тоже с CONNECT),
    # системного postgres исключаем — панель ходит через peer без пароля
    code, out, _e = _pg_psql(
        "SELECT rolname FROM pg_roles WHERE rolcanlogin AND "
        "has_database_privilege(rolname, '%s', 'CONNECT') AND rolname <> "
        "'postgres' ORDER BY 1;" % name, timeout=30)
    if code != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def change_password(name, user, password, engine="mysql"):
    """Меняет пароль пользователя базы."""
    engine = engine or "mysql"
    if CTX.demo:
        return True, "демо: пароль изменён"
    if not engine_ok(engine):
        return False, "СУБД %s не установлена" % engine_name(engine)
    if not valid_name(name, engine) or not valid_name(user, engine):
        return False, "некорректное имя базы или пользователя"
    if len(password or "") < 8:
        return False, "пароль короче 8 символов"
    if engine == "mysql":
        if user not in users(name):
            return False, ("у базы нет пользователя %s — создайте базу "
                           "заново или выберите существующего пользователя"
                           % user)
        safe_pw = password.replace("\\", "\\\\").replace("'", "\\'")
        sql = ("ALTER USER '%s'@'localhost' IDENTIFIED BY '%s'; "
               "FLUSH PRIVILEGES;" % (user, safe_pw))
        code, _, err = run(["mysql"], timeout=60, input_text=sql,
                           as_root=True)
        ok = code == 0
        if ok:
            CTX.store.notify("Изменён пароль пользователя MySQL %s" % user)
        return ok, ("" if ok else err)
    code, out, err = _pg_psql(
        "SELECT 1 FROM pg_roles WHERE rolname='%s';" % user, timeout=30)
    if code != 0 or not out.strip():
        return False, ("роль %s не найдена в PostgreSQL" % user)
    safe_pw = password.replace("'", "''")
    code, _, err = _pg_psql(
        "ALTER ROLE \"%s\" LOGIN PASSWORD '%s';" % (user, safe_pw),
        timeout=60)
    ok = code == 0
    if ok:
        CTX.store.notify("Изменён пароль роли PostgreSQL %s" % user)
    return ok, ("" if ok else (err or "").strip())


# ----------------------------------------------------------- дамп/импорт ---
def dump(name, engine="mysql"):
    """Дамп базы (SQL-текст) — для скачивания из панели."""
    engine = engine or "mysql"
    if CTX.demo:
        return True, ("-- демо: дамп базы %s (%s)\n"
                      "-- в рабочем режиме здесь будет содержимое базы\n"
                      % (name, engine_name(engine)))
    if not engine_ok(engine) or not valid_name(name, engine):
        return False, ""
    if engine == "mysql":
        code, out, err = run(["mysqldump", "--single-transaction", name],
                             timeout=600, as_root=True)
        return code == 0, (out or err or "")
    code, out, err = run(["su", "-", "postgres", "-c",
                          "pg_dump --no-owner --no-privileges '%s'" % name],
                         timeout=1800)
    if code != 0:
        return False, (err or out or "")
    return True, out


def _decode_import(data, filename):
    """Распознаёт .sql / .sql.gz / .zip (один .sql внутри) -> SQL-текст."""
    name = (filename or "").lower()
    if data[:2] == b"\x1f\x8b" or name.endswith(".gz"):
        try:
            return gzip.decompress(data).decode("utf-8", "replace"), ""
        except OSError as e:
            return None, "не удалось распаковать gzip: %s" % e
    if name.endswith(".zip") or data[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return None, "битый zip-архив"
        members = [m for m in zf.namelist()
                   if m.lower().endswith(".sql") and not m.startswith("__")]
        if not members:
            return None, "в архиве нет .sql-файла"
        if len(members) > 1:
            return None, ("в архиве несколько .sql (%s) — распакуйте и "
                          "загрузите нужный файл отдельно"
                          % ", ".join(members[:3]))
        return zf.read(members[0]).decode("utf-8", "replace"), ""
    return data.decode("utf-8", "replace"), ""


def import_dump(name, data, filename, engine="mysql"):
    """Импорт SQL-дампа в существующую базу. Возвращает (ok, сообщение)."""
    engine = engine or "mysql"
    if CTX.demo:
        return True, ("демо: импорт выполнен (%s, %s)"
                      % (filename or "без имени", utils.human_size(
                          len(data))))
    if not engine_ok(engine):
        return False, "СУБД %s не установлена" % engine_name(engine)
    if not valid_name(name, engine):
        return False, "некорректное имя базы"
    if name not in {d["name"] for d in list_dbs(engine)}:
        return False, "база %s не найдена — сначала создайте её" % name
    sql_text, e = _decode_import(data, filename)
    if e:
        return False, e
    if not sql_text.strip():
        return False, "файл пустой"
    fd, path = tempfile.mkstemp(prefix="hp-import-", suffix=".sql")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(sql_text)
        # 0600 от mkstemp сохраняем: дамп с данными, чтение идёт от root
        # (перенаправление < file выполняет root-шелл, postgres не читает)
        if engine == "mysql":
            code, out, err = run(["/bin/sh", "-c",
                                  "mysql '%s' < '%s'" % (name, path)],
                                 timeout=1800, as_root=True)
        else:
            code, out, err = run(["/bin/sh", "-c",
                                  "su - postgres -c \"psql -X -q -v "
                                  "ON_ERROR_STOP=1 -d '%s'\" < '%s'"
                                  % (name, path)], timeout=1800)
        if code != 0:
            tail = ((err or "") + "\n" + (out or "")).strip()
            tail = "\n".join(tail.splitlines()[-8:])
            return False, "ошибка импорта: %s" % (tail or
                                                  "невозможно выполнить")
        CTX.store.notify("Импорт дампа в базу %s (%s, %s)"
                         % (name, engine_name(engine),
                            utils.human_size(len(data))))
        return True, ("импорт выполнен (%s, %s)"
                      % (filename or "без имени",
                         utils.human_size(len(data))))
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ------------------------------------------------------------- SQL-консоль ---
def query(dbname, sql, engine="mysql"):
    """Произвольный SQL в выбранной базе — для консоли панели.

    Возвращает (ok, columns, rows, info); вывод читается через табуляцию
    (mysql --batch) или CSV (psql --csv).
    """
    engine = engine or "mysql"
    if CTX.demo:
        return True, ["demo"], [["демо-режим: SQL не выполняется"]], "демо"
    if not engine_ok(engine):
        return False, [], [], "СУБД %s не установлена" % engine_name(engine)
    if not valid_name(dbname, engine):
        return False, [], [], "некорректное имя базы"
    sql = (sql or "").strip()
    if not sql:
        return False, [], [], "пустой запрос"
    if engine == "mysql":
        code, out, err = run(["mysql", "--batch", "-D", dbname],
                             timeout=120, input_text=sql, as_root=True)
    else:
        code, out, err = _pg_psql(sql, db=dbname, timeout=120, csv_mode=True)
    if code != 0:
        tail_lines = ((err or "") + "\n" + (out or "")).strip().splitlines()
        tail = tail_lines[-1] if tail_lines else "ошибка выполнения запроса"
        return False, [], [], tail[:500]
    lines = out.splitlines()
    if not lines:
        return True, [], [], "выполнено, данных нет"
    if engine == "pg":
        # psql --csv: первая строка — заголовок, значения с экранированием
        import csv as _csv
        import io as _io
        parsed = list(_csv.reader(_io.StringIO(out)))
        if len(parsed) < 2:
            return True, parsed[0] if parsed else [], \
                [], "выполнено, данных нет"
        return True, parsed[0], parsed[1:], "%d строк(и)" % (len(parsed) - 1)
    # mysql --batch: первая строка — заголовок колонок, ячейки через \t
    columns = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:]]
    return True, columns, rows, "%d строк(и)" % len(rows)
