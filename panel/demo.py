# -*- coding: utf-8 -*-
"""Демо-режим: фиктивные сайты, файлы, логи и история проверок живучести.

Всё создаётся внутри домашней папки панели на реальных файлах — статистика,
логи и редакторы конфигов работают тем же кодом, что и в рабочем режиме.
"""
import datetime as dt
import os
import secrets

from .state import default_security


def seed_demo(data, home):
    demo_www = os.path.join(home, "demo_www")
    os.makedirs(demo_www, exist_ok=True)
    today = dt.date.today()

    def mk_security(geo_mode="off", countries=None, rate=0, waf=False,
                    bots=False):
        sec = default_security()
        sec.update({"geo_mode": geo_mode,
                    "geo_countries": countries or [],
                    "rate_limit": rate, "waf": waf, "block_bots": bots})
        return sec

    sites = [
        {"id": 1, "domain": "example.ru", "enabled": True, "parent": 0,
         "maintenance": False, "webserver": "nginx", "php": "8.2",
         "php_modules": ["curl", "gd", "mbstring", "mysqli", "xml", "zip"],
         "docroot": "demo_www/example.ru/public_html",
         "ssl": {"kind": "letsencrypt",
                 "domains": ["example.ru", "www.example.ru"],
                 "expires": (today + dt.timedelta(days=68)).isoformat()},
         "fpm": {"pm": "dynamic", "max_children": 10, "start_servers": 3,
                 "min_spare": 2, "max_spare": 5},
         "node": {"enabled": False, "version": "20", "port": 3000,
                  "script": "app.js"},
         "security": mk_security(rate=10, waf=True, bots=True),
         "created": "2025-11-14 10:22:00", "db_id": 1},
        {"id": 2, "domain": "shop.example.ru", "enabled": True, "parent": 1,
         "maintenance": False, "webserver": "nginx+apache", "php": "8.1",
         "php_modules": ["curl", "mbstring", "openssl", "zip"],
         "docroot": "demo_www/example.ru/subdomains/shop/public_html",
         "ssl": {"kind": "letsencrypt", "domains": ["shop.example.ru"],
                 "expires": (today + dt.timedelta(days=21)).isoformat()},
         "fpm": {"pm": "dynamic", "max_children": 20, "start_servers": 5,
                 "min_spare": 3, "max_spare": 10},
         "node": {"enabled": False, "version": "20", "port": 3001,
                  "script": "app.js"},
         "security": mk_security(geo_mode="deny", countries=["CN", "IR"],
                                 rate=30),
         "created": "2025-12-02 15:40:00", "db_id": 2},
        {"id": 3, "domain": "api.example.ru", "enabled": True, "parent": 0,
         "maintenance": False, "webserver": "nginx+node", "php": "",
         "php_modules": [],
         "docroot": "demo_www/api.example.ru",
         "ssl": {"kind": "selfsigned", "domains": ["api.example.ru"],
                 "expires": (today + dt.timedelta(days=360)).isoformat()},
         "fpm": None,
         "node": {"enabled": True, "version": "20", "port": 3100,
                  "script": "server.js"},
         "security": default_security(),
         "created": "2026-01-20 09:05:00", "db_id": 0},
        {"id": 4, "domain": "old-site.ru", "enabled": False, "parent": 0,
         "maintenance": False, "webserver": "apache", "php": "7.4",
         "php_modules": ["curl", "mysqli"],
         "docroot": "demo_www/old-site.ru/public_html",
         "ssl": {"kind": "none", "domains": [], "expires": ""},
         "fpm": None,
         "node": {"enabled": False, "version": "18", "port": 3002,
                  "script": "index.js"},
         "security": default_security(),
         "created": "2024-06-11 12:00:00", "db_id": 3},
    ]
    data["sites"] = sites
    data["dbs"] = [
        {"id": 1, "name": "wp_example", "user": "wp_example",
         "size_bytes": 412_600_000, "tables": 68},
        {"id": 2, "name": "shop_db", "user": "shop_user",
         "size_bytes": 1_284_000_000, "tables": 214},
        {"id": 3, "name": "oldsite_db", "user": "old_user",
         "size_bytes": 96_400_000, "tables": 31},
    ]
    data["cron"] = [
        {"id": 1, "expr": "0 3 * * *", "command": "/usr/local/bin/backup-all.sh",
         "comment": "Ежедневное резервное копирование", "enabled": True},
        {"id": 2, "expr": "*/5 * * * *",
         "command": "/usr/local/bin/check-services.sh",
         "comment": "Мониторинг служб", "enabled": True},
        {"id": 3, "expr": "0 4 * * 0",
         "command": "find /var/log/hostpanel -name '*.gz' -mtime +30 -delete",
         "comment": "Очистка старых логов", "enabled": False},
    ]
    data["packages"]["demo_upgradable"] = [
        {"pkg": "nginx-common", "cur": "1.24.0-1", "new": "1.24.0-2ubuntu1",
         "kind": "веб-сервер"},
        {"pkg": "php8.2-fpm", "cur": "8.2.18-1", "new": "8.2.24-1",
         "kind": "PHP"},
        {"pkg": "php8.2-curl", "cur": "8.2.18-1", "new": "8.2.24-1",
         "kind": "PHP"},
        {"pkg": "openssl", "cur": "3.0.13-1", "new": "3.0.15-1",
         "kind": "система"},
        {"pkg": "mariadb-server", "cur": "1:10.11.7", "new": "1:10.11.9",
         "kind": "БД"},
        {"pkg": "libnginx-mod-http-geoip2", "cur": "1.24.0-1",
         "new": "1.24.0-2ubuntu1", "kind": "гео-фильтры"},
    ]

    # -- файлы сайтов -------------------------------------------------------
    index_php = ("<?php\n// Демонстрационный сайт\n"
                 "printf('Сайт %s работает, PHP %s', '{dom}', PHP_VERSION);\n")
    for s in sites:
        base = os.path.join(demo_www, s["domain"])
        public = s["docroot"].replace("demo_www/", "")
        public = os.path.join(demo_www, public)
        os.makedirs(public, exist_ok=True)
        if s["webserver"] == "nginx+node":
            with open(os.path.join(base, "server.js"), "w",
                      encoding="utf-8") as f:
                f.write("const http = require('http');\n"
                        "http.createServer((req,res)=>{res.end('API ok');})"
                        ".listen(%d);\n" % s["node"]["port"])
            with open(os.path.join(base, "package.json"), "w",
                      encoding="utf-8") as f:
                f.write('{"name":"api","version":"1.0.0",'
                        '"main":"server.js"}\n')
        else:
            with open(os.path.join(public, "index.php"), "w",
                      encoding="utf-8") as f:
                f.write(index_php.replace("{dom}", s["domain"]))
            with open(os.path.join(public, ".htaccess"), "w",
                      encoding="utf-8") as f:
                f.write("RewriteEngine On\nRewriteCond %{HTTPS} off\n"
                        "RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI}"
                        " [L,R=301]\n")
            with open(os.path.join(public, "robots.txt"), "w",
                      encoding="utf-8") as f:
                f.write("User-agent: *\nAllow: /\n")

    # -- логи ----------------------------------------------------------------
    _generate_demo_logs(os.path.join(home, "logs"), sites)
    # -- история проверок живучести за сутки ---------------------------------
    _seed_health(data, sites)


def _generate_demo_logs(logs_dir, sites, days=14, per_day=220):
    """Access-логи в формате combined за 14 дней — статистика считается
    тем же кодом, что и в рабочем режиме."""
    rnd = secrets.SystemRandom()
    paths = ["/", "/wp-json/wp/v2/posts", "/catalog/item/42", "/catalog",
             "/static/app.js", "/static/style.css", "/favicon.ico",
             "/api/v1/status", "/cart", "/checkout", "/login",
             "/img/banner.webp", "/contacts", "/about", "/wp-admin/setup.php",
             "/.env", "/wp-content/debug.log"]
    uas = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
           "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Safari/605.1.15",
           "Mozilla/5.0 (Linux; Android 14) Chrome/125.0",
           "Mozilla/5.0 (X11; Linux x86_64) Firefox/127.0",
           "YandexBot/3.0", "Googlebot/2.1", "sqlmap/1.7"]
    codes = [200, 200, 200, 200, 200, 200, 200, 304, 301, 404, 403, 500]
    refs = ["https://yandex.ru/", "https://google.com/", "-", "-",
            "https://t.me/", "https://example.ru/"]
    ip_pool = ["%d.%d.%d.%d" % (rnd.randint(31, 217), rnd.randint(0, 255),
                                rnd.randint(0, 255), rnd.randint(1, 254))
               for _ in range(60)] + ["45.155.205.11", "185.222.57.90"]
    base_time = dt.datetime.now() - dt.timedelta(days=days)
    for s in sites:
        dom = s["domain"]
        acc = os.path.join(logs_dir, dom + ".access.log")
        err = os.path.join(logs_dir, dom + ".error.log")
        with open(acc, "w", encoding="utf-8") as fa, \
                open(err, "w", encoding="utf-8") as fe:
            for d in range(days):
                day_start = base_time + dt.timedelta(days=d)
                n = per_day + rnd.randint(-80, 120)
                if dom == "shop.example.ru":
                    n = int(n * 1.6)
                if dom == "old-site.ru":
                    n = int(n * 0.3)
                for _i in range(n):
                    ts = day_start + dt.timedelta(
                        seconds=rnd.randint(0, 86399))
                    ip = rnd.choice(ip_pool)
                    path = rnd.choice(paths)
                    code = rnd.choice(codes)
                    size = rnd.randint(300, 90_000)
                    ua = rnd.choice(uas)
                    ref = rnd.choice(refs)
                    fa.write('%s - - [%s] "GET %s HTTP/1.1" %d %d "%s" "%s"\n'
                             % (ip, ts.strftime("%d/%b/%Y:%H:%M:%S +0300"),
                                path, code, size, ref, ua))
                    if code >= 500 and rnd.random() < 0.5:
                        fe.write("%s [%s] [error] FastCGI sent in stderr: "
                                 "\"PHP message: PHP Fatal error: Uncaught "
                                 "TypeError in /var/www/%s/index.php:12\" "
                                 "while reading response header\n"
                                 % (ts.strftime("%Y/%m/%d %H:%M:%S"),
                                    ts.strftime("%Y/%m/%d %H:%M:%S"), dom))
                    elif code == 403 and rnd.random() < 0.3:
                        fe.write("%s [%s] [warn] client %s denied by "
                                 "server configuration\n"
                                 % (ts.strftime("%Y/%m/%d %H:%M:%S"),
                                    ts.strftime("%Y/%m/%d %H:%M:%S"), ip))


# вероятность успешной проверки для демо-сайтов (живучесть)
DEMO_RELIABILITY = {"example.ru": 0.995, "shop.example.ru": 0.985,
                    "api.example.ru": 0.998, "old-site.ru": 0.75}


def _seed_health(data, sites, hours=24, step_min=5):
    """История проверок за последние сутки, чтобы график живучести
    был наполнен сразу после установки."""
    rnd = secrets.SystemRandom()
    now = dt.datetime.now()
    health = data.setdefault("health", {})
    for s in sites:
        rel = DEMO_RELIABILITY.get(s["domain"], 0.99)
        if not s["enabled"]:
            rel = 0.0
        checks = []
        n = int(hours * 60 / step_min)
        for i in range(n, 0, -1):
            ts = now - dt.timedelta(minutes=i * step_min)
            ok = (rnd.random() < rel) if s["enabled"] else False
            checks.append({"t": ts.strftime("%Y-%m-%d %H:%M:%S"),
                           "ok": ok, "ms": rnd.randint(12, 240) if ok else 0,
                           "code": (200 if ok else (0 if not s["enabled"]
                                                    else 502))})
        health[s["domain"]] = {"checks": checks[-600:], "incidents": []}
        # восстановим инциденты из истории
        inc_open = None
        for ch in checks:
            if not ch["ok"] and inc_open is None:
                inc_open = ch["t"]
            elif ch["ok"] and inc_open is not None:
                health[s["domain"]]["incidents"].insert(
                    0, {"start": inc_open, "end": ch["t"]})
                inc_open = None
        if inc_open is not None and s["enabled"]:
            health[s["domain"]]["incidents"].insert(
                0, {"start": inc_open, "end": ""})
