# -*- coding: utf-8 -*-
"""API: сайты — создание (включая поддомены), отключение, обслуживание,
фильтры безопасности, статистика, логи, нагрузка, конфиги."""
import io
import os
import shutil
import time

from .. import config, utils
from ..context import CTX, site_docroot_abs
from ..core import templates, ssl as ssl_mod, nodejs, stats, security, \
    health, confeditor, packages
from .router import get, post, ok, err, done, site_or_404


@get("/api/sites")
def list_sites(handler, qs):
    st = CTX.store.data
    out = []
    for s in st["sites"]:
        d = dict(s)
        d["docroot"] = site_docroot_abs(s) if not CTX.demo \
            else os.path.join(CTX.home, s["docroot"])
        lp = templates.site_log_paths(s)
        d["log_size"] = 0
        for p in (lp["access"], lp["error"]):
            try:
                d["log_size"] += os.path.getsize(p)
            except OSError:
                pass
        d["disk"] = utils.dir_size(d["docroot"])
        h = (st.get("health", {}).get(s["domain"]) or {}).get("disk") or []
        d["disk_hist"] = h[-90:]
        d["security_status"] = security.security_status(
            s.get("security") or {})
        out.append(d)
    return ok(sites=out)


@post("/api/sites/create")
def create_site(handler, body):
    from ..core import db as db_mod
    st = CTX.store.data
    domain = (body.get("domain") or "").strip().lower()
    parent_id = int(body.get("parent") or 0)
    parent = None
    if parent_id:
        parent = CTX.store.find_site(parent_id)
        if not parent:
            return err("родительский сайт не найден", 404)
        # поддомен: проверяем, что domain = label.parent
        if not domain.endswith("." + parent["domain"]):
            return err("поддомен должен заканчиваться на .%s"
                       % parent["domain"])
        label = domain[: -(len(parent["domain"]) + 1)]
        if not utils.valid_subdomain(label):
            return err("некорректное имя поддомена")
    elif not utils.valid_domain(domain):
        return err("некорректное имя домена")
    if any(s["domain"] == domain for s in st["sites"]):
        return err("такой сайт уже есть")
    # -- предпроверки: не установленные службы сообщаем сразу и понятно ----
    if not CTX.demo:
        from ..context import have
        ws = body.get("webserver", "nginx")
        missing = []
        if ws != "apache" and not have("nginx"):
            missing.append(("nginx", "nginx"))
        if "apache" in ws and not have("apache2ctl"):
            missing.append(("apache", "Apache"))
        php_sel = body.get("php", "") if ws in ("nginx", "nginx+apache",
                                                "apache") else ""
        if php_sel and not have("php" + php_sel):
            missing.append(("php" + php_sel, "PHP " + php_sel))
        if ws == "nginx+node" and not have("node"):
            missing.append(("nodejs", "Node.js"))
        if missing:
            names = ", ".join(h[1] for h in missing)
            ids = " ".join('{"name":"%s"}' % h[0] for h in missing)
            return err(
                "на сервере не установлено: %s. Откройте раздел «Установка "
                "ПО» и установите там (запрос API: /api/software/install %s)"
                % (names, ids), 400)
        db_engine = body.get("db_engine") if \
            body.get("db_engine") in ("mysql", "pg") else "mysql"
        if body.get("create_db") and not parent_id:
            if db_engine == "mysql" and not have("mysql"):
                return err("MariaDB не установлена — установите её в разделе "
                           "«Установка ПО» (элемент «MariaDB»), выберите "
                           "PostgreSQL или снимите галочку «Создать базу "
                           "данных»", 400)
            if db_engine == "pg" and not have("psql"):
                return err("PostgreSQL не установлен — установите его в "
                           "разделе «Установка ПО» (элемент «PostgreSQL») "
                           "или выберите MariaDB", 400)
    if parent:
        docroot = os.path.join(os.path.dirname(parent["docroot"]),
                               "subdomains", domain.split(".")[0],
                               "public_html")
    elif CTX.demo:
        docroot = "demo_www/%s/public_html" % domain
    else:
        docroot = body.get("docroot") or os.path.join(
            CTX.www_root, domain, "public_html")
    site = {
        "id": int(time.time() * 1000) % 1_000_000_000,
        "domain": domain, "enabled": True, "parent": parent_id,
        "maintenance": False,
        "webserver": body.get("webserver", "nginx"),
        "www": bool(body.get("www")),
        "php": (body.get("php", "") if body.get("webserver") in
                ("nginx", "nginx+apache", "apache") else ""),
        "php_modules": [], "docroot": docroot,
        "ssl": {"kind": "none", "domains": [], "expires": ""},
        "fpm": {"pm": "dynamic", "max_children": 10, "start_servers": 3,
                "min_spare": 2, "max_spare": 5},
        "node": {"enabled": body.get("webserver") == "nginx+node",
                 "version": body.get("node_version", "20"),
                 "port": int(body.get("node_port") or 3000),
                 "script": body.get("node_script", "app.js")},
        "security": {}, "created": utils.now_str(), "db_id": 0}
    from ..state import default_security
    site["security"] = default_security()
    if site["webserver"] == "static":
        site["php"] = ""
    e = templates.provision_site_files(site)
    if e:
        return err(e, 500)
    okc, errc = templates.write_site_configs(site)
    if not okc:
        return err("конфиги не применены: %s" % errc, 500)
    if body.get("ssl_kind") and body["ssl_kind"] != "none":
        okc, errc = ssl_mod.issue(site, body["ssl_kind"],
                                  body.get("email", ""))
        if not okc:
            CTX.store.notify("SSL для %s: %s" % (domain, errc), "warn")
        else:
            # в конфиге сайта появился listen 443 ssl — перегенерируем
            templates.write_site_configs(site)
    db_info = None
    if body.get("create_db") and not parent_id:
        import re as _re
        db_engine = body.get("db_engine") if \
            body.get("db_engine") in ("mysql", "pg") else "mysql"
        dbname = _re.sub(r"[^a-z0-9]", "_", domain.split(".")[0])[:20] + "_db"
        user = dbname[:16]
        password = utils.gen_password()
        okc, errc = db_mod.create(dbname, user, password, db_engine)
        if okc:
            db_info = {"name": dbname, "user": user, "password": password,
                       "engine": db_engine}
            st.setdefault("dbs", []).append(
                {"id": len(st["dbs"]) + 1, "name": dbname, "user": user,
                 "size_bytes": 0, "tables": 0, "engine": db_engine})
            site["db_id"] = len(st["dbs"])
        else:
            CTX.store.notify("БД не создана: %s" % errc, "warn")
    st["sites"].append(site)
    CTX.store.notify("Создан сайт %s (%s)%s"
                     % (domain, site["webserver"],
                        " · поддомен" if parent_id else ""))
    return done("сайт %s создан" % domain,
                {"site_id": site["id"], "db": db_info})


# -- импорт сайта архивом (переезд с другого хостинга) ------------------------

@post("/api/sites/import")
def sites_import_archive(handler, body):
    """Импорт сайта: zip с файлами (+ опционально дамп базы) в multipart.

    Поля: domain (существующий или новый сайт), clean (1 — очистить папку),
    file (zip), sql (файл дампа, необязательно), db_name (куда импортировать
    дамп, необязательно), engine (mysql|pg)."""
    import zipfile as _zipfile
    from .. import utils
    from ..core import db as db_mod

    ctype = handler.headers.get("Content-Type", "")
    parts = utils.parse_multipart(handler.read_body(), ctype)
    domain, clean, zip_data, zip_name = "", False, None, ""
    sql_data, sql_name, db_name, engine = None, "", "", "mysql"
    for part in parts:
        if part["name"] == "domain":
            domain = part["data"].decode("utf-8", "replace").strip().lower()
        elif part["name"] == "clean":
            clean = part["data"].strip() in (b"1", b"true", b"on")
        elif part["name"] == "db_name":
            db_name = part["data"].decode("utf-8", "replace").strip().lower()
        elif part["name"] == "engine":
            engine = (part["data"].decode("utf-8", "replace").strip()
                      or "mysql")
        elif part["name"] == "file" and part["filename"]:
            zip_data, zip_name = part["data"], part["filename"]
        elif part["name"] == "sql" and part["filename"]:
            sql_data, sql_name = part["data"], part["filename"]
    if not utils.valid_domain(domain):
        return err("укажите корректный домен")
    if not zip_data:
        return err("прикрепите zip-архив с файлами сайта")
    site = CTX.store.find_site_by_domain(domain)
    if not site:
        # создаём простой nginx-сайт (без PHP — тип меняется в настройках)
        from ..state import default_security
        st = CTX.store.data
        if any(s["domain"] == domain for s in st["sites"]):
            return err("сайт уже существует")
        docroot = os.path.join(CTX.www_root, domain, "public_html")
        site = {
            "id": int(time.time() * 1000) % 1_000_000_000,
            "domain": domain, "enabled": True, "parent": 0,
            "maintenance": False, "webserver": "nginx", "php": "",
            "php_modules": [], "docroot": docroot,
            "ssl": {"kind": "none", "domains": [], "expires": ""},
            "fpm": None,
            "node": {"enabled": False, "version": "20", "port": 3000,
                     "script": "app.js"},
            "security": default_security(), "created": utils.now_str(),
            "db_id": 0}
        from ..state import default_perf, default_snippets
        site["perf"] = default_perf()
        site["snippets"] = default_snippets()
        e = templates.provision_site_files(site)
        if e:
            return err(e, 500)
        okc, errc = templates.write_site_configs(site)
        if not okc:
            return err("конфиги не применены: %s" % errc, 500)
        st["sites"].append(site)
    docroot = site_docroot_abs(site)
    if not os.path.isdir(docroot):
        os.makedirs(docroot, exist_ok=True)
    report = []
    # 1. распаковка архива в docroot (анти path-traversal на каждом члене)
    staging = docroot + ".hp-import"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    try:
        try:
            with _zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                members = []
                for m in z.namelist():
                    norm = os.path.normpath(m)
                    if norm.startswith("..") or os.path.isabs(norm):
                        return err("небезопасное имя в архиве: %s" % m)
                    members.append(m)
                z.extractall(staging, members=members)
        except _zipfile.BadZipFile:
            shutil.rmtree(staging, ignore_errors=True)
            return err("файл не zip-архив (или повреждён)")
        # если архив с одним корневым каталогом — поднимаем содержимое
        entries = os.listdir(staging)
        if len(entries) == 1 and os.path.isdir(
                os.path.join(staging, entries[0])):
            inner = os.path.join(staging, entries[0])
            for name in os.listdir(inner):
                shutil.move(os.path.join(inner, name),
                            os.path.join(staging, name))
            os.rmdir(inner)
        if clean:
            for name in os.listdir(docroot):
                p = os.path.join(docroot, name)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        # перенос в docroot
        for name in os.listdir(staging):
            shutil.move(os.path.join(staging, name),
                        os.path.join(docroot, name))
        report.append("файлы распакованы в %s" % docroot)
        run(["chown", "-R", "www-data:www-data", docroot], as_root=True,
            timeout=120)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    # 2. импорт дампа базы
    if sql_data and db_name:
        okc, msg = db_mod.import_dump(db_name, sql_data, sql_name, engine)
        report.append("база %s: %s" % (db_name, msg))
        if not okc:
            CTX.store.save()
            return err("; ".join(report), 400)
    CTX.store.notify("Импорт сайта %s из архива: %s"
                     % (domain, "; ".join(report)))
    return done("импорт %s завершён: %s" % (domain, "; ".join(report)),
                {"site_id": site["id"]})


@post("/api/sites/update")
def update_site(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    for key in ("webserver", "php", "php_modules"):
        if key in body:
            site[key] = body[key]
    www_reissue = False
    if "www" in body:
        old_www = bool(site.get("www"))
        site["www"] = bool(body["www"])
        # включили www у сайта с сертификатом — перевыпускаем его c www-именем
        www_reissue = (site["www"] and not old_www and
                       not site.get("parent") and
                       (site.get("ssl") or {}).get("kind") == "letsencrypt")
    if "fpm" in body and site["fpm"]:
        site["fpm"].update(body["fpm"])
    if isinstance(body.get("perf"), dict):
        from ..state import default_perf
        perf = site.setdefault("perf", default_perf())
        for key in default_perf():
            if key in body["perf"]:
                perf[key] = bool(body["perf"][key])
    if isinstance(body.get("snippets"), dict):
        from ..state import default_snippets
        snip = site.setdefault("snippets", default_snippets())
        if "www_redirect" in body["snippets"]:
            snip["www_redirect"] = bool(body["snippets"]["www_redirect"])
        if "admin_ip" in body["snippets"]:
            ips = [ip.strip() for ip in
                   str(body["snippets"]["admin_ip"]).replace(",", " ").split()
                   if ip.strip()]
            bad = [ip for ip in ips if not utils.valid_ip(ip)]
            if bad:
                return err("некорректный IP: %s" % ", ".join(bad))
            snip["admin_ip"] = " ".join(ips[:20])
        if "admin_path" in body["snippets"]:
            import re as _re
            ap = _re.sub(r"[^a-zA-Z0-9_\-/]", "",
                         str(body["snippets"]["admin_path"] or "")
                         ).strip("/")
            snip["admin_path"] = ap[:100] or "admin"
        if "upload_size" in body["snippets"]:
            v = str(body["snippets"]["upload_size"] or "").strip()
            snip["upload_size"] = v if v in ("64m", "128m", "256m", "512m",
                                             "1g", "2g") else ""
    if "node" in body:
        site.setdefault("node", {}).update(body["node"])
    if "enabled" in body:
        site["enabled"] = bool(body["enabled"])
    okc, errc = templates.write_site_configs(site)
    if not okc:
        return err("конфиги не применены: %s" % errc, 500)
    if site.get("node", {}).get("enabled"):
        nodejs.apply(site, "restart")
    msg = "настройки сайта %s сохранены" % site["domain"]
    if www_reissue:
        # certbot --expand в фоне: конфиг менять не нужно, серт обновится
        # в панелиной папке и сайт продолжит работать со старым до готовности
        import threading as _th
        CTX.store.notify("Перевыпускаю сертификат %s с www-именем…"
                         % site["domain"])

        def _reissue():
            oki, erri = ssl_mod.issue(site, "letsencrypt")
            if oki:
                CTX.store.notify("Сертификат %s перевыпущен с www" %
                                 site["domain"])
            else:
                CTX.store.notify("Перевыпуск сертификата %s не удался: %s"
                                 % (site["domain"], (erri or "")[:150]), "err")
            CTX.store.save()
        _th.Thread(target=_reissue, daemon=True).start()
        msg += "; сертификат перевыпускается с www-именем (уведомление придёт)"
    return done(msg)


@post("/api/sites/toggle")
def toggle_site(handler, body):
    """Отключение сайта: вместо снятия конфига ставится заглушка
    «Сайт отключён» (HTTP 503), файлы и конфиги остаются на месте."""
    site, e = site_or_404(body)
    if e:
        return e
    site["enabled"] = not site["enabled"]
    if not CTX.demo:
        if site["enabled"]:
            templates.remove_site_disabled(site)
            okc, errc = templates.write_site_configs(site)
            if not okc:
                return err("конфиги не применены: %s" % errc, 500)
        else:
            okc, errc = templates.write_site_disabled(site)
            if not okc:
                return err("заглушка не применена: %s" % errc, 500)
    return done("сайт %s %s" % (site["domain"],
                                "включён" if site["enabled"]
                                else "отключён — показывает заглушку "
                                     "«Сайт отключён» (HTTP 503)"))


@post("/api/sites/maintenance")
def maintenance(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    enabled = bool(body.get("enabled"))
    okc, errc = templates.set_maintenance(site, enabled)
    if not okc:
        return err("режим обслуживания не применён: %s" % errc, 500)
    return done("режим обслуживания %s: %s"
                % (site["domain"], "включён (HTTP 503)" if enabled
                   else "выключен"))


@post("/api/sites/delete")
def delete_site(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    domain = site["domain"]
    # поддомены родителя удаляются отдельно
    children = [s for s in CTX.store.data["sites"]
                if s.get("parent") == site["id"]]
    if children and not body.get("force_with_children"):
        return err("у сайта есть поддомены (%s); удалите их сначала или "
                   "передайте force_with_children"
                   % ", ".join(c["domain"] for c in children), 400)
    for child in children:
        _remove_site(child, body.get("delete_files"))
    _remove_site(site, body.get("delete_files"))
    return done("сайт %s удалён%s" % (domain,
                                      " с поддоменами" if children else ""))


def _remove_site(site, delete_files):
    templates.remove_site_configs(site)
    nodejs.remove_unit(site)
    if delete_files:
        try:
            root = site_docroot_abs(site) if not CTX.demo \
                else os.path.join(CTX.home, site["docroot"])
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)
        except OSError:
            pass
    CTX.store.data["sites"] = [s for s in CTX.store.data["sites"]
                               if s["id"] != site["id"]]
    CTX.store.notify("Сайт %s удалён" % site["domain"], "warn")


@post("/api/sites/ssl")
def issue_ssl(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    okc, errc = ssl_mod.issue(site, body.get("kind", "letsencrypt"),
                              body.get("email", ""))
    if okc:
        # применяем listen 443 ssl к конфигу веб-сервера
        templates.write_site_configs(site)
        return done("сертификат для %s выпущен" % site["domain"])
    return err(errc, 500)


@post("/api/sites/ssl_delete")
def delete_ssl(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    ssl_mod.delete(site)
    # убираем 443-блок, иначе nginx останется со ссылками на удалённые файлы
    templates.write_site_configs(site)
    return done("сертификат %s удалён" % site["domain"])


@post("/api/sites/node")
def node_action(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    action = body.get("action", "restart")
    if action not in ("restart", "stop", "enable", "disable"):
        return err("недопустимое действие")
    if action == "enable":
        site["node"]["enabled"] = True
    # apply вызываем ДО переключения флага: при выключенном enabled она
    # выходит сразу, и «disable» не останавливал процесс приложения
    okc, errc = nodejs.apply(site, action)
    if action in ("enable", "disable"):
        site["node"]["enabled"] = action == "enable"
        # конфиг nginx (proxy_pass на порт приложения) надо перегенерировать
        templates.write_site_configs(site)
    if okc:
        return done("Node.js: %s — %s" % (site["domain"], action))
    return err(errc, 500)


@post("/api/sites/npm")
def npm_install(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    from ..context import run
    if CTX.demo:
        return done("демо: npm install выполнен")
    code, out, errs = run(["npm", "install", "--prefix",
                           site_docroot_abs(site)], timeout=600)
    return done("npm install завершён" if code == 0
                else "npm: ошибка: %s" % errs[:300])


# -- данные сайта -----------------------------------------------------------

@get("/api/site/:sid/stats")
def site_stats_api(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    days = int(qs.get("days", ["14"])[0] or 14)
    days = max(1, min(90, days))
    filtr = {}
    for key in ("code", "ip", "url", "since", "until"):
        if qs.get(key, [""])[0]:
            filtr[key] = qs[key][0]
    if qs.get("errors_only", ["0"])[0] in ("1", "true"):
        filtr["errors_only"] = True
    if qs.get("bots_only", ["0"])[0] in ("1", "true"):
        filtr["bots_only"] = True
    if filtr.get("code") and not str(filtr["code"]).isdigit():
        return err("некорректный код статуса")
    return ok(stats=stats.site_stats(site, days,
                                     filtr or None))


@get("/api/site/:sid/logs")
def site_logs(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    kind = "error" if qs.get("type", ["access"])[0] == "error" else "access"
    filtr = {}
    for key in ("q", "code", "ip", "url", "since", "until"):
        if qs.get(key, [""])[0]:
            filtr[key] = qs[key][0]
    if qs.get("errors_only", ["0"])[0] in ("1", "true"):
        filtr["errors_only"] = True
    if qs.get("bots_only", ["0"])[0] in ("1", "true"):
        filtr["bots_only"] = True
    if filtr.get("code") and not str(filtr["code"]).isdigit():
        return err("некорректный код статуса")
    if filtr.get("ip") and not utils.valid_ip(filtr["ip"]):
        return err("некорректный IP")
    limit = min(int(qs.get("limit", ["300"])[0] or 300), 1000)
    lines, total = stats.read_log(site, kind, filtr=filtr, limit=limit)
    lp = templates.site_log_paths(site)
    return ok(lines=lines, total=total, filtered=len(lines),
              path=lp[kind])


@get("/api/site/:sid/node_logs")
def node_logs(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    return ok(lines=nodejs.logs(site))


@get("/api/site/:sid/health")
def site_health(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    return ok(report=health.site_report(site))


@get("/api/site/:sid/dns_check")
def site_dns_check(handler, qs, sid):
    """Проверка: указывает ли домен на этот сервер (перед выпуском SSL)."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    from ..context import run
    domain = site["domain"]
    code, out, _ = run(["getent", "ahosts", domain], timeout=15)
    resolved = set()
    if code == 0:
        for ln in out.splitlines():
            parts = ln.split()
            if parts:
                resolved.add(parts[0])
    resolved = sorted(resolved)
    ipv6 = [ip for ip in resolved if ":" in ip]
    ipv4 = [ip for ip in resolved if ":" not in ip]
    code2, out2, _ = run(["hostname", "-I"], timeout=10)
    server_ips = out2.split() if code2 == 0 else []
    dns_ok = bool(resolved) and any(ip in server_ips for ip in ipv4)
    return ok(domain=domain, ipv4=ipv4, ipv6=ipv6,
              server_ips=server_ips, dns_ok=dns_ok)


@get("/api/site/:sid/load")
def site_load_api(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    return ok(load=stats.site_load(site))


# -- чек-лист здоровья сайта -------------------------------------------------

# дата окончания поддержки PHP (EOL); истёкшие версии помечаются fail
PHP_EOL = {"7.4": "2022-11-28", "8.0": "2023-11-26", "8.1": "2025-12-31",
           "8.2": "2026-12-31", "8.3": "2027-12-31", "8.4": "2028-12-31",
           "8.5": "2029-12-31"}



def _audit_fetch(path, host, https=False, gzip=False, no_redirect=False):
    """GET на собственный веб-сервер по 127.0.0.1 с нужным Host —
    работает даже если DNS домена ещё не настроен."""
    import ssl as _ssl
    import urllib.error
    import urllib.request
    url = ("https://" if https else "http://") + "127.0.0.1" + path
    headers = {"Host": host, "User-Agent": "HostPanel/audit"}
    if gzip:
        headers["Accept-Encoding"] = "gzip"
    req = urllib.request.Request(url, headers=headers)
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    if no_redirect:
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        opener = urllib.request.build_opener(
            _NoRedirect, urllib.request.HTTPSHandler(context=ctx))
    else:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {})
    except Exception as e:  # noqa: BLE001 — сетевые ошибки
        return 0, {"error": str(e)}


@get("/api/site/:sid/audit")
def site_audit(handler, qs, sid):
    """Чек-лист здоровья сайта: HTTPS, редирект, сжатие, кэш статики,
    заголовки безопасности, версия PHP, доля ошибок 5xx."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    import datetime as _dt
    domain = site["domain"]
    checks = []

    def add(name, status, detail="", hint=""):
        checks.append({"name": name, "status": status,
                       "detail": detail, "hint": hint})

    if not site.get("enabled"):
        add("Сайт включён", "fail", "сайт отключён в панели",
            "Включите сайт кнопкой «Вкл/выкл» в списке сайтов.")
        return ok(checks=checks, score=0, demo=CTX.demo)

    perf = site.get("perf") or {}
    ssl_info = site.get("ssl") or {}
    has_ssl = ssl_info.get("kind") not in ("", "none")

    # в демо нет веб-сервера — синтезируем результаты из состояния
    if CTX.demo:
        add("DNS домена", "ok", "домен указывает на этот сервер")
        add("Сайт отвечает по HTTP", "ok", "HTTP 200")
        if has_ssl:
            add("Сайт отвечает по HTTPS", "ok", "HTTP 200")
            add("Срок сертификата", "ok", "67 дн. до истечения")
            add("Редирект HTTP → HTTPS", "ok", "HTTP 301")
        else:
            add("HTTPS (SSL)", "warn", "сертификат не выпущен",
                "Выпустите бесплатный Let's Encrypt во вкладке «SSL» — "
                "сайт откроется по https:// с замочком.")
        if perf.get("gzip"):
            add("Сжатие ответов (gzip)", "ok", "включено в профиле сайта")
        else:
            add("Сжатие ответов (gzip)", "warn", "не включено",
                "Включите галочку «Сжатие (gzip)» во вкладке «Основное» — "
                "страницы станут загружаться быстрее.")
        if perf.get("static_cache"):
            add("Кэш статики в браузере", "ok", "включено в профиле сайта")
        else:
            add("Кэш статики в браузере", "warn", "заголовки кэша не выдаются",
                "Включите «Кэш картинок и стилей (30 дней)» во вкладке "
                "«Основное» — повторные посещения станут заметно быстрее.")
        if has_ssl:
            if perf.get("hsts"):
                add("Заголовок HSTS", "ok", "включён в профиле сайта")
            else:
                add("Заголовок HSTS", "warn", "не установлен",
                    "Включите «HSTS» во вкладке «Основное» — браузер будет "
                    "ходить на сайт только по HTTPS.")
        if site.get("php"):
            add("Версия PHP", "ok", "PHP %s, поддержка актуальна"
                % site["php"])
        add("Ошибки 5xx", "ok", "ошибок сервера нет (0%)")
        score = round(100.0 * sum(1 for c in checks if c["status"] == "ok") /
                      max(1, len([c for c in checks if c["status"] != "skip"])))
        return ok(checks=checks, score=score, demo=True)

    # 1. DNS (реальный резолв домена)
    from ..context import run as _run
    code, out, _ = _run(["getent", "ahosts", domain], timeout=15)
    resolved = {ln.split()[0] for ln in (out or "").splitlines()
                if ln.split()}
    code2, out2, _ = _run(["hostname", "-I"], timeout=10)
    server_ips = out2.split() if code2 == 0 else []
    if resolved and any(ip in server_ips for ip in resolved
                        if ":" not in ip):
        add("DNS домена", "ok", "домен указывает на этот сервер")
    else:
        add("DNS домена", "fail", "домен не указывает на сервер",
            "Добавьте у регистратора A-запись: %s → %s. "
            "Изменения применяются до нескольких часов."
            % (domain, ", ".join(server_ips[:2]) or "IP сервера"))

    # 2. HTTP-ответ
    code, _h = _audit_fetch("/", domain)
    if 200 <= code < 400:
        add("Сайт отвечает по HTTP", "ok", "HTTP %d" % code)
    elif code == 503 and site.get("maintenance"):
        add("Сайт отвечает", "warn", "HTTP 503 — включён режим обслуживания")
    else:
        add("Сайт отвечает по HTTP", "fail", "код %s" % (code or "нет связи"),
            "Проверьте конфиг веб-сервера и журнал сайта (вкладка «Логи»).")

    # 3. HTTPS + сертификат + редирект
    if not has_ssl:
        add("HTTPS (SSL)", "warn", "сертификат не выпущен",
            "Выпустите бесплатный Let's Encrypt во вкладке «SSL» — "
            "сайт откроется по https:// с замочком.")
    else:
        hcode, _ = _audit_fetch("/", domain, https=True)
        if 200 <= hcode < 400:
            add("Сайт отвечает по HTTPS", "ok", "HTTP %d" % hcode)
        else:
            add("Сайт отвечает по HTTPS", "fail",
                "код %s" % (hcode or "нет связи"),
                "Проверьте, что сертификат выпущен и конфиг сайта применён.")
        try:
            days = (_dt.date.fromisoformat(ssl_info.get("expires", "")) -
                    _dt.date.today()).days
        except ValueError:
            days = 0
        if days > 20:
            add("Срок сертификата", "ok", "%d дн. до истечения" % days)
        else:
            add("Срок сертификата", "fail", "%d дн. до истечения" % max(days, 0),
                "Перевыпустите сертификат во вкладке «SSL» (Let's Encrypt "
                "продлевается автоматически, если включено «Автопродление» "
                "на странице «Планировщик»).")
        rcode, _ = _audit_fetch("/", domain, no_redirect=True)
        if rcode in (301, 302, 308):
            add("Редирект HTTP → HTTPS", "ok", "HTTP %d" % rcode)
        else:
            add("Редирект HTTP → HTTPS", "warn",
                "HTTP по-прежнему открывается без перенаправления",
                "Пересохраните настройки сайта — панель добавит редирект "
                "в конфиг nginx при действующем SSL.")

    base_https = has_ssl

    # 4. Сжатие (gzip)
    code, h = _audit_fetch("/", domain, https=base_https, gzip=True)
    enc = (h.get("Content-Encoding") or "").lower()
    if "gzip" in enc or "br" in enc:
        add("Сжатие ответов (gzip)", "ok", enc)
    elif perf.get("gzip"):
        add("Сжатие ответов (gzip)", "ok", "включено в профиле сайта")
    else:
        add("Сжатие ответов (gzip)", "warn", "не включено",
            "Включите галочку «Сжатие (gzip)» во вкладке «Основное» — "
            "страницы станут загружаться быстрее.")

    # 5. Кэш статики
    code, h = _audit_fetch("/hostpanel-audit-check.css", domain,
                           https=base_https, no_redirect=True)
    cc = h.get("Cache-Control") or h.get("Expires") or ""
    if "max-age" in cc or h.get("Expires"):
        add("Кэш статики в браузере", "ok", cc[:60])
    elif perf.get("static_cache"):
        add("Кэш статики в браузере", "ok", "включено в профиле сайта")
    else:
        add("Кэш статики в браузере", "warn", "заголовки кэша не выдаются",
            "Включите «Кэш картинок и стилей (30 дней)» во вкладке "
            "«Основное» — повторные посещения станут заметно быстрее.")

    # 6. Заголовки безопасности
    if has_ssl:
        code, h = _audit_fetch("/", domain, https=True)
        hsts = h.get("Strict-Transport-Security") or ""
        if hsts:
            add("Заголовок HSTS", "ok", hsts[:50])
        elif perf.get("hsts"):
            add("Заголовок HSTS", "ok", "включён в профиле сайта")
        else:
            add("Заголовок HSTS", "warn", "не установлен",
                "Включите «HSTS» во вкладке «Основное» — браузер будет "
                "ходить на сайт только по HTTPS.")

    # 7. Версия PHP (EOL)
    if site.get("php"):
        eol = PHP_EOL.get(site["php"])
        if not eol:
            add("Версия PHP", "warn", "PHP %s — срок поддержки неизвестен"
                % site["php"])
        else:
            try:
                days = (_dt.date.fromisoformat(eol) -
                        _dt.date.today()).days
            except ValueError:
                days = 9999
            if days < 0:
                add("Версия PHP", "fail",
                    "PHP %s больше не получает обновления безопасности"
                    % site["php"],
                    "Переключите сайт на новую версию PHP во вкладке "
                    "«PHP и FPM» (предварительно проверьте совместимость).")
            elif days < 180:
                add("Версия PHP", "warn",
                    "PHP %s: поддержка закончится %s" % (site["php"], eol),
                    "Запланируйте переход на более новую версию PHP.")
            else:
                add("Версия PHP", "ok", "PHP %s, поддержка до %s"
                    % (site["php"], eol))

    # 8. Доля ошибок 5xx в свежем журнале
    lp = templates.site_log_paths(site)
    err_rate = _recent_5xx(lp["access"])
    if err_rate is None:
        add("Ошибки 5xx", "skip", "журнал пуст или недоступен")
    elif err_rate > 5:
        add("Ошибки 5xx", "fail", "%.0f%% запросов в свежем журнале — "
            "ошибки сервера" % err_rate,
            "Посмотрите журнал во вкладке «Логи» с фильтром "
            "«только ошибки».")
    elif err_rate > 0.5:
        add("Ошибки 5xx", "warn", "%.1f%% запросов — ошибки сервера"
            % err_rate)
    else:
        add("Ошибки 5xx", "ok", "ошибок сервера почти нет (%.1f%%)"
            % err_rate)

    score = round(100.0 * sum(1 for c in checks if c["status"] == "ok") /
                  max(1, len([c for c in checks
                              if c["status"] != "skip"])))
    return ok(checks=checks, score=score, demo=CTX.demo)


def _recent_5xx(path, max_bytes=300_000):
    """Доля 5xx в хвосте access-лога или None, если данных нет."""
    import os
    import re
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    try:
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    lines = [ln for ln in data.splitlines() if '" ' in ln]
    if len(lines) < 20:
        return None
    total = err = 0
    for ln in lines:
        m = re.search(r'"\s+(\d{3})\s', ln)
        if not m:
            continue
        total += 1
        if m.group(1).startswith("5"):
            err += 1
    return round(100.0 * err / total, 1) if total else None


@get("/api/site/:sid/conf")
def site_conf(handler, qs, sid):
    """Чтение конфигов сайта для встроенного редактора."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    kind = qs.get("kind", ["nginx"])[0]
    domain = site["domain"]
    paths = {"nginx": lambda: confeditor.ensure_demo_nginx(site),
             "apache": lambda: confeditor.ensure_demo_apache(site),
             "fpm": lambda: confeditor.ensure_demo_fpm(site),
             "php": lambda: confeditor.php_ini_path(site.get("php") or "8.2",
                                                    site)}
    if kind not in paths or (kind == "apache" and
                             "apache" not in site["webserver"]):
        return err("конфиг недоступен для этого сайта")
    path = paths[kind]()
    if not os.path.exists(path) and kind in ("nginx", "apache"):
        okc, _ = templates.write_site_configs(site)
        if not okc or not os.path.exists(path):
            return err("конфиг ещё не сгенерирован")
    if not os.path.exists(path):
        return err("конфиг не найден", 404)
    from ..core import files as files_mod
    text, e = files_mod.read(path)
    if e:
        return err(e, 400)
    return ok(path=path, content=text, kind=kind)


@post("/api/site/:sid/conf")
def site_conf_save(handler, body, sid):
    """Сохранение конфига с валидацией и откатом при ошибке."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    kind = body.get("kind", "")
    content = body.get("content", "")
    if len(content) > 1_000_000:
        return err("конфиг слишком большой")
    domain = site["domain"]
    savers = {"nginx": (lambda: confeditor.ensure_demo_nginx(site),
                        confeditor.save_nginx),
              "apache": (lambda: confeditor.ensure_demo_apache(site),
                         confeditor.save_apache),
              "fpm": (lambda: confeditor.ensure_demo_fpm(site),
                      confeditor.save_fpm),
              "php": (lambda: confeditor.php_ini_path(
                  site.get("php") or "8.2", site),
                  confeditor.save_php_ini)}
    if kind not in savers:
        return err("неизвестный тип конфига")
    path_fn, saver = savers[kind]
    path = path_fn()
    okc, errc = saver(path, content)
    if not okc:
        return err("конфиг не сохранён: %s" % errc, 400)
    return done("конфиг %s (%s) сохранён и проверен" % (domain, kind))


# -- безопасность сайта (гео/IP/WAF/боты/rate) --------------------------------

@post("/api/sites/security")
def save_security(handler, body):
    site, e = site_or_404(body)
    if e:
        return e
    from ..state import default_security
    sec = site.setdefault("security", default_security())
    updates = body.get("security") or {}
    # валидация
    if updates.get("geo_mode") not in (None, "off", "allow", "deny"):
        return err("некорректный режим гео-фильтра")
    countries = [c.upper() for c in (updates.get("geo_countries") or [])]
    for c in countries:
        if not utils.valid_country(c) or c not in config.COUNTRIES:
            return err("неизвестная страна: %s" % c)
    ip_allow = [ip.strip() for ip in (updates.get("ip_allow") or [])
                if ip.strip()]
    ip_deny = [ip.strip() for ip in (updates.get("ip_deny") or [])
               if ip.strip()]
    for ip in ip_allow + ip_deny:
        if not utils.valid_ip(ip):
            return err("некорректный IP: %s" % ip)
    try:
        rate = int(updates.get("rate_limit") or 0)
        burst = int(updates.get("rate_burst") or 20)
    except (TypeError, ValueError):
        return err("лимит запросов должен быть числом")
    if not (0 <= rate <= 10000) or not (1 <= burst <= 10000):
        return err("лимит запросов вне допустимого диапазона")
    # --- WAF 2.0: комбинированные гео-списки ---
    geo_allow = [c.upper() for c in (updates.get("geo_allow") or [])]
    geo_deny = [c.upper() for c in (updates.get("geo_deny") or [])]
    for c in geo_allow + geo_deny:
        if not utils.valid_country(c) or c not in config.COUNTRIES:
            return err("неизвестная страна: %s" % c)
    if "geo_allow" in updates or "geo_deny" in updates:
        # новая схема: оба списка пусты = гео-фильтр выключен
        sec.pop("geo_mode", None)
        sec.pop("geo_countries", None)
    elif updates.get("geo_mode") in ("allow", "deny") and not countries:
        return err("выберите хотя бы одну страну")

    # --- WAF 2.0: категории ботов и UA-правила ---
    ua_categories = [str(c) for c in (updates.get("ua_categories") or [])]
    for c in ua_categories:
        if c not in config.BOT_CATEGORIES:
            return err("неизвестная категория ботов: %s" % c)
    import re as _re
    ua_rules = []
    for r in (updates.get("ua_rules") or [])[:100]:
        pat = str(r.get("pattern") or "").strip()
        if not pat:
            continue
        if len(pat) > 150 or '"' in pat or "\\" in pat or "{" in pat:
            return err("недопустимый шаблон User-Agent: %s" % pat[:60])
        try:
            _re.compile(pat)
        except _re.error:
            return err("некорректный regex в User-Agent: %s" % pat[:60])
        ua_rules.append({"pattern": pat,
                         "note": str(r.get("note") or "")[:200]})
    ref_block = [d.strip().lower() for d in
                 (updates.get("ref_block") or [])[:200] if d.strip()]
    ref_allow = [d.strip().lower() for d in
                 (updates.get("ref_allow") or [])[:200] if d.strip()]
    for d in ref_block + ref_allow:
        if not utils.valid_domain(d):
            return err("некорректный домен источника: %s" % d)
    block_empty_ua = bool(updates.get("block_empty_ua"))
    block_empty_ref = bool(updates.get("block_empty_ref"))

    # применение
    if "geo_mode" in updates:
        sec["geo_mode"] = updates["geo_mode"]
    if "geo_countries" in updates:
        sec["geo_countries"] = countries
    if "geo_allow" in updates:
        sec["geo_allow"] = geo_allow[:100]
        sec["geo_deny"] = geo_deny[:100]
    if "ip_allow" in updates:
        sec["ip_allow"] = ip_allow[:200]
    if "ip_deny" in updates:
        sec["ip_deny"] = ip_deny[:200]
    if "rate_limit" in updates:
        sec["rate_limit"] = rate
    if "rate_burst" in updates:
        sec["rate_burst"] = burst
    if "block_bots" in updates:
        sec["block_bots"] = bool(updates["block_bots"])
    if "waf" in updates:
        sec["waf"] = bool(updates["waf"])
    if "ua_categories" in updates:
        sec["ua_categories"] = ua_categories
        sec["ua_rules"] = ua_rules
        sec["block_empty_ua"] = block_empty_ua
    if "ref_block" in updates:
        sec["ref_block"] = ref_block
        sec["ref_allow"] = ref_allow
        sec["block_empty_ref"] = block_empty_ref
    okc, errc = security.apply_security(site)
    if not okc:
        return err("фильтры не применены: %s" % errc, 500)
    return done("фильтры доступа %s обновлены" % site["domain"])


@get("/api/site/:sid/security")
def get_security(handler, qs, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    from ..state import default_security
    sec = site.setdefault("security", default_security())
    return ok(security=sec, countries=config.COUNTRIES,
              bot_categories={cid: {"name": cat[1], "desc": cat[2]}
                              for cid, cat in config.BOT_CATEGORIES.items()},
              geo_available=security.geo_module_available())


@get("/api/countries")
def countries(handler, qs):
    return ok(countries=config.COUNTRIES)


# -- DNS-диагностика домена --------------------------------------------------

def _dig(name, rtype):
    """dig +short с fallback на getent (если утилиты нет — пусто)."""
    from ..context import run as _run, have as _have
    if _have("dig"):
        code, out, _ = _run(["dig", "+short", name, rtype], timeout=15)
        if code == 0:
            return [x.strip() for x in (out or "").splitlines() if x.strip()]
    if rtype == "A":
        code, out, _ = _run(["getent", "ahosts", name], timeout=15)
        return sorted({ln.split()[0] for ln in (out or "").splitlines()
                       if ln.split() and ":" not in ln.split()[0]})
    return []


@get("/api/site/:sid/dns_full")
def site_dns_full(handler, qs, sid):
    """Полная диагностика DNS: A/AAAA/MX/NS/TXT/SPF — «что есть» рядом
    с «что должно быть»."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    domain = site["domain"]
    if CTX.demo:
        return ok(demo=True, domain=domain, server_ips=["203.0.113.10"],
                  a={"current": ["203.0.113.10"], "ok": True},
                  aaaa={"current": []},
                  www={"current": ["203.0.113.10"], "ok": True},
                  mx={"current": ["10 mail.example.ru."]},
                  ns={"current": ["ns1.example.ru."]},
                  spf={"current": ["v=spf1 a mx -all"],
                       "ok": True,
                       "recommended": "v=spf1 a mx -all"})
    from ..context import run as _run
    code, out, _ = _run(["hostname", "-I"], timeout=10)
    server_ips = [x for x in (out or "").split() if ":" not in x]
    a = _dig(domain, "A")
    aaaa = _dig(domain, "AAAA")
    www = _dig("www." + domain, "A")
    mx = _dig(domain, "MX")
    ns = _dig(domain, "NS")
    txt = _dig(domain, "TXT")
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    a_match = bool(a) and any(ip in server_ips for ip in a)
    recommended_spf = "v=spf1 a mx -all"
    return ok(domain=domain, server_ips=server_ips,
              a={"current": a, "ok": a_match},
              aaaa={"current": aaaa},
              www={"current": www, "ok": bool(www) and
                   any(ip in server_ips for ip in www)},
              mx={"current": mx}, ns={"current": ns},
              spf={"current": spf, "ok": bool(spf),
                   "recommended": recommended_spf})


# -- подбор лимитов FPM ------------------------------------------------------

@get("/api/site/:sid/fpm_reco")
def site_fpm_reco(handler, qs, sid):
    """Рекомендация pm.max_children: свободная RAM × 25% ÷ средний вес
    воркера (реальный, из site_load)."""
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    if CTX.demo:
        return ok(demo=True, avail_mb=812, avg_mb=38,
                  max_children=20, start_servers=5, min_spare=3,
                  max_spare=9,
                  note="демо-расчёт: свободная RAM 812 МБ × 25% ÷ "
                       "средний воркер 38 МБ")
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
        avail_mb = info.get("MemAvailable", 0) // (1024 * 1024)
    except (OSError, ValueError):
        avail_mb = 0
    load = stats.site_load(site)
    workers = load.get("php") or []
    avg_mb = (round(sum(w["mem_mb"] for w in workers) / len(workers), 1)
              if workers else 0.0)
    if avg_mb < 16:
        avg_mb = 40.0  # типичный воркер WordPress-типа до «прогрева»
    budget = max(avail_mb * 0.25, 96)
    max_children = max(2, int(budget // avg_mb))
    return ok(avail_mb=avail_mb, avg_mb=avg_mb,
              max_children=max_children,
              start_servers=max(2, max_children // 4),
              min_spare=max(1, max_children // 10),
              max_spare=max(3, max_children // 10 * 2),
              note="свободная RAM %d МБ × 25%% ÷ средний воркер %s МБ "
                   "(замер живых процессов пула)" % (avail_mb, avg_mb))


# -- очистка журналов сайта --------------------------------------------------

@post("/api/site/:sid/logs_clear")
def site_logs_clear(handler, body, sid):
    site = CTX.store.find_site(sid)
    if not site:
        return err("сайт не найден", 404)
    kind = body.get("kind") or "access"
    if kind not in ("access", "error"):
        return err("некорректный тип журнала")
    if CTX.demo:
        return done("демо: журнал очищен")
    lp = templates.site_log_paths(site)
    path = lp[kind]
    try:
        with open(path, "w", encoding="utf-8"):
            pass
    except OSError as e:
        return err("не удалось очистить: %s" % e, 500)
    return done("журнал %s сайта %s очищен" % (kind, site["domain"]))
