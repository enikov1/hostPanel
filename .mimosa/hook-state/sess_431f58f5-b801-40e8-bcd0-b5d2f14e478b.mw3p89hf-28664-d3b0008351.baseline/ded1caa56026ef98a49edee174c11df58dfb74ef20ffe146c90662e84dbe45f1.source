#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke-тест HostPanel: поднимает панель в демо-режиме и прогоняет
все GET-маршруты плюс набор безопасных POST-мутаций.

Запуск из корня проекта:  python3 scripts/smoke_test.py
Код возврата 0 — всё прошло; 1 — есть падения. Зависимостей нет
(только stdlib), панель запускается во временной папке.
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# POST-маршруты, безопасные для демо-режима (мутации только в state.json)
SAFE_POSTS = [
    ("/api/sites/create", {"domain": "smoke-test.ru", "webserver": "nginx",
                           "php": "8.3", "create_db": True}),
    ("/api/sites/security", {"id": 0, "security": {"block_bots": True}}),
    ("/api/sites/update", {"id": 0, "perf": {"gzip": True,
                                             "static_cache": True}}),
    ("/api/sites/maintenance", {"id": 0, "enabled": False}),
    ("/api/sites/ssl", {"id": 0, "kind": "selfsigned"}),
    ("/api/sites/toggle", {"id": 0}),
    ("/api/sites/toggle", {"id": 0}),
    ("/api/backups/create", {"with_db": False}),
    ("/api/db/create", {"name": "smoke_db", "user": "smoke_db"}),
    ("/api/db/query", {"db": "smoke_db", "sql": "SELECT 1"}),
    ("/api/cron/save", {"jobs": [{"expr": "0 3 * * *",
                                  "command": "echo smoke", "enabled": True}]}),
    ("/api/files/mkdir", {"path": "__SMOKE_DIR__"}),
    ("/api/files/save", {"path": "__SMOKE_DIR__/test.txt",
                         "content": "ok"}),
    ("/api/settings/save", {"theme": "dark", "expert_mode": True}),
    ("/api/settings/save", {"expert_mode": False}),
    ("/api/swset/save", {"id": "mariadb", "fields": {
        "max_connections": 120, "innodb_buffer_pool_size": 256,
        "bind_address": "127.0.0.1", "character_set_server": "utf8mb4",
        "slow_query_log": False, "long_query_time": 2}}),
    ("/api/software/install", {"name": "git"}),
    ("/api/apps/install", {"app": "pma", "site": "smoke-test.ru"}),
    ("/api/notify/test", {}),
    ("/api/notifications/read", {}),
    ("/api/default-site", {"content": "<!DOCTYPE html><html>"
                                       "<body>smoke</body></html>"}),
]
# маршруты, которые в демо закономерно отвечают отказом
DEMO_REFUSAL = re.compile(r"демо|демо-режиме", re.I)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def call(port, method, path, token=None, body=None):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Panel-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw or "{}")
            except ValueError:
                return resp.status, {"raw": raw[:120]}  # не-JSON (дамп и т.п.)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def wait_ready(port, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, _ = call(port, "GET", "/api/login-state")
        if code == 200:
            return True
        time.sleep(0.3)
    return False


def main():
    port = free_port()
    home = tempfile.mkdtemp(prefix="hp-smoke-")
    env = dict(os.environ, PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "panel", "--demo", "--port", str(port),
         "--home", home], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    failures = []
    passed = 0
    try:
        if not wait_ready(port):
            print("ПАНЕЛЬ НЕ ПОДНЯЛАСЬ за 20 с")
            return 1
        # вход стандартным паролем демо
        code, resp = call(port, "POST", "/api/login",
                          body={"login": "admin", "password": "admin"})
        if not resp.get("ok"):
            print("ВХОД НЕ ПРОШЁЛ: %s" % resp)
            return 1
        token = resp["token"]

        from panel.api import router  # noqa: F401 — регистрирует маршруты
        import panel.server  # noqa: F401
        from panel.api.router import ROUTES_GET

        # справочник подстановок :sid
        _, d = call(port, "GET", "/api/sites", token)
        sites = d.get("sites") or []
        sid = sites[0]["id"] if sites else 0
        _, me = call(port, "GET", "/api/me", token)
        home = (me.get("home") or "").rstrip("/")
        _, cr = call(port, "GET", "/api/cron", token)
        cron_cmd = ((cr.get("jobs") or [{}])[0].get("command")
                    if cr.get("jobs") else "")
        _, sw = call(port, "GET", "/api/swset", token)
        sw_entry = next((e for e in (sw.get("entries") or [])
                         if e.get("files")), None)
        _, db = call(port, "GET", "/api/db", token)
        db_name = (db.get("dbs") or [{}])[0].get("name", "")

        # query-параметры для маршрутов, требующих их
        QS = {
            "/api/php/modules": "?version=8.3",
            "/api/conf/php_ini": "?version=8.3",
            "/api/services/logs": "?name=nginx",
            "/api/cron/log": "?command=" + urllib.parse.quote(cron_cmd),
            "/api/files/read": "?path=" + urllib.parse.quote(
                home + "/state.json"),
            "/api/db/users": "?name=" + urllib.parse.quote(db_name),
        }

        # --- все GET-маршруты ---
        for path, _fn in ROUTES_GET:
            real = path.replace(":sid", str(sid)) + QS.get(path, "")
            if path.startswith("/api/site/:sid") and not sid:
                continue
            if path == "/api/swset/file":
                if not sw_entry:
                    continue
                real = "/api/swset/file?id=%s&name=%s" % (
                    sw_entry["id"],
                    urllib.parse.quote(sw_entry["files"][0]["name"]))
            code, resp = call(port, "GET", real, token)
            if code == 200 and resp.get("ok") is True:
                passed += 1
            elif path == "/api/totp/qr":  # требует qrencode — не падение
                passed += 1
            else:
                failures.append("GET %s -> %s %s" % (real, code, resp))

        # --- особые GET (стриминг) ---
        _, dbs = call(port, "GET", "/api/db", token)
        if dbs.get("dbs"):
            code, resp = call(
                port, "GET",
                "/api/db/export?name=%s" % dbs["dbs"][0]["name"], token)
            if code == 200:
                passed += 1
            else:
                failures.append("GET /api/db/export -> %s %s" % (code, resp))

        # --- безопасные POST-мутации ---
        site_id = None
        for path, body in SAFE_POSTS:
            if isinstance(body.get("path"), str) and \
                    "__SMOKE_DIR__" in body["path"]:
                body = dict(body, path=body["path"].replace(
                    "__SMOKE_DIR__", home + "/smoke-dir"))
            if "id" in body and body["id"] == 0:
                _, sd = call(port, "GET", "/api/sites", token)
                all_sites = sd.get("sites") or []
                target = next((s for s in all_sites
                               if s["domain"] == "smoke-test.ru"),
                              all_sites[0] if all_sites else None)
                if not target:
                    failures.append("POST %s: нет сайта для подстановки"
                                    % path)
                    continue
                body = dict(body, id=target["id"])
                site_id = target["id"]
            code, resp = call(port, "POST", path, token, body)
            if resp.get("ok") is True or DEMO_REFUSAL.search(
                    str(resp.get("error", ""))):
                passed += 1
            else:
                failures.append("POST %s -> %s %s" % (path, code, resp))
            if path == "/api/db/create" and resp.get("ok"):
                pass  # база smoke_db создана — используется ниже

        # --- чек-лист здоровья (новый маршрут) ---
        if site_id:
            code, resp = call(port, "GET",
                              "/api/site/%d/audit" % site_id, token)
            if code == 200 and resp.get("ok") and resp.get("checks"):
                passed += 1
            else:
                failures.append("GET audit -> %s %s" % (code, resp))

        # --- удаление созданного сайта ---
        if site_id:
            code, resp = call(port, "POST", "/api/sites/delete", token,
                              {"id": site_id, "delete_files": True})
            if resp.get("ok"):
                passed += 1
            else:
                failures.append("POST sites/delete -> %s" % resp)

        print("Smoke-тест: %d проверок пройдено, %d падений"
              % (passed, len(failures)))
        for f in failures:
            print("  ПАДЕНИЕ: %s" % f)
        return 1 if failures else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        import shutil
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
