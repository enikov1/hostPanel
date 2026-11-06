# -*- coding: utf-8 -*-
"""Экспорт и импорт настроек панели (перенос на новый VPS).

Экспорт: настройки, задачи планировщика, метаданные сайтов (без файлов),
почтовые домены и адреса ящиков. Пароли баз и ящиков не хранятся
панелью и в файл не попадают; SMTP-пароль и TOTP-ключ входят —
файл предназначен только администратору.

Импорт: применяет настройки, задачи и настройки безопасности сайтов;
отсутствующие сайты пересоздаёт (конфиги + папки), SSL и базы
выпускаются/создаются заново на новом сервере.
"""
import time

from .. import config, utils

# генератор id при массовом импорте: время в мс внутри одной итерации
# одинаково → дубликаты id; гарантируем уникальность приращением
_next_id = int(time.time() * 1000) % 1_000_000_000


def _gen_id():
    global _next_id
    _next_id = (_next_id + 1) % 1_000_000_000
    return _next_id
from ..context import CTX
from ..state import default_security

# ключи настроек, разрешённые к переносу
SETTINGS_KEYS = ("theme", "backup_retention", "auto_backup_cron",
                "auto_backup_enabled", "health_interval", "fm_restricted",
                "notify")
# поля сайта, переносимые при экспорте
SITE_KEYS = ("domain", "parent", "enabled", "maintenance", "webserver",
             "php", "php_modules", "docroot", "security", "node", "fpm")


def export_data():
    """Слепок настроек для скачивания администратором."""
    st = CTX.store.data
    sites = []
    for s in st.get("sites", []):
        row = {}
        for k in SITE_KEYS:
            v = s.get(k)
            if k == "security":
                v = dict(v or {})
            elif k in ("node", "fpm"):
                v = dict(v or {})
            row[k] = v
        sites.append(row)
    mail = st.get("mail", {})
    return {
        "panel": config.PANEL_NAME,
        "format": 1,
        "exported": utils.now_str(),
        "version": config.VERSION,
        "settings": {k: st["settings"][k] for k in SETTINGS_KEYS
                     if k in st["settings"]},
        "cron": [dict(j) for j in st.get("cron", [])],
        "sites": sites,
        "mail": {
            "domains": [d.get("domain") for d in mail.get("domains", [])],
            "mailboxes": [m.get("email")
                          for m in mail.get("mailboxes", [])],
        },
    }


def _site_exists(domain):
    return any(s["domain"] == domain
               for s in CTX.store.data.get("sites", []))


def _create_site(row, report):
    """Воссоздание сайта из слепка (без SSL и базы — их делают заново)."""
    from ..core import templates
    from ..context import have
    global _next_id
    domain = (row.get("domain") or "").strip().lower()
    if not utils.valid_domain(domain):
        report.append("сайт %s пропущен: некорректный домен" % domain)
        return
    ws = row.get("webserver") or "nginx"
    if ws not in ("nginx", "nginx+apache", "apache", "nginx+node", "static"):
        ws = "nginx"
    php = row.get("php") or ""
    if ws == "static":
        php = ""
    if php and not have("php" + php):
        report.append("сайт %s: PHP %s не установлен — сайт создан без "
                      "PHP, версию переключите в настройках сайта"
                      % (domain, php))
        php = ""
    docroot = row.get("docroot") or ""
    if docroot and not docroot.startswith(CTX.www_root + "/"):
        docroot = ""
    site = {
        "id": _gen_id(),
        "domain": domain, "enabled": True,
        "parent": 0, "maintenance": False,
        "webserver": ws, "php": php, "php_modules": [],
        "docroot": docroot or (CTX.www_root + "/" + domain
                               + "/public_html"),
        "ssl": {"kind": "none", "domains": [], "expires": ""},
        "fpm": row.get("fpm") or {"pm": "dynamic", "max_children": 10,
                                  "start_servers": 3, "min_spare": 2,
                                  "max_spare": 5},
        "node": row.get("node") or {"enabled": ws == "nginx+node",
                                    "version": "20", "port": 3000,
                                    "script": "app.js"},
        "security": default_security(),
        "created": utils.now_str(), "db_id": 0}
    sec = row.get("security") or {}
    for k, v in default_security().items():
        if k in sec:
            site["security"][k] = sec[k]
    e = templates.provision_site_files(site)
    if e:
        report.append("сайт %s: %s" % (domain, e))
        return
    okc, errc = templates.write_site_configs(site)
    if not okc:
        report.append("сайт %s: конфиги не применены: %s" % (domain, errc))
        return
    CTX.store.data["sites"].append(site)
    report.append("сайт %s создан" % domain)


def import_data(data):
    """Применение слепка. Возвращает (ok, summary, report[])."""
    if not isinstance(data, dict) or data.get("panel") != config.PANEL_NAME \
            or not isinstance(data.get("format"), int):
        return False, "", ["файл не похож на экспорт HostPanel"]
    report = []

    # -- настройки ---------------------------------------------------------
    st = CTX.store.data
    sset = st["settings"]
    applied = []
    for k in SETTINGS_KEYS:
        if k in data.get("settings", {}):
            sset[k] = data["settings"][k]
            applied.append(k)
    if applied:
        report.append("настройки: %s" % ", ".join(applied))

    # -- планировщик -------------------------------------------------------
    from ..core import services
    jobs = data.get("cron")
    if isinstance(jobs, list):
        clean = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            if not services.valid_cron_expr(j.get("expr") or ""):
                report.append("задача пропущена (расписание): %s"
                              % (j.get("expr") or "?"))
                continue
            cmd = str(j.get("command") or "")
            if not cmd or len(cmd) > 500 or "\n" in cmd:
                report.append("задача пропущена (команда): %s" % cmd[:40])
                continue
            clean.append({"expr": j["expr"], "command": cmd,
                          "comment": str(j.get("comment") or "")[:120],
                          "enabled": bool(j.get("enabled", True))})
        if clean:
            st["cron"] = clean
            services.cron_write_system(services._cron_system_jobs(st))
            report.append("задач планировщика: %d" % len(clean))

    # -- сайты ---------------------------------------------------------------
    created = updated = 0
    for row in (data.get("sites") or []):
        if not isinstance(row, dict):
            continue
        domain = (row.get("domain") or "").strip().lower()
        if not domain:
            continue
        if _site_exists(domain):
            site = next(s for s in st["sites"] if s["domain"] == domain)
            sec = row.get("security")
            if isinstance(sec, dict):
                for k in default_security():
                    if k in sec:
                        site.setdefault("security",
                                        default_security())[k] = sec[k]
                from ..core import templates
                templates.write_site_configs(site)
                updated += 1
        else:
            _create_site(row, report)
            created += 1
    if updated:
        report.append("настройки безопасности обновлены у %d сайт(ов)"
                      % updated)

    # -- почта ---------------------------------------------------------------
    mail = data.get("mail") or {}
    st_mail = st.setdefault("mail", {"domains": [], "mailboxes": []})
    have_domains = [d["domain"] for d in st_mail.get("domains", [])]
    new_domains = [d for d in (mail.get("domains") or [])
                   if d and d not in have_domains]
    if new_domains:
        st_mail["domains"] = have_domains + [
            {"domain": d} for d in new_domains]
        report.append("почтовых доменов добавлено: %d (записи DNS "
                      "настройте вручную)" % len(new_domains))
    if mail.get("mailboxes"):
        report.append("ящики в файле: %d — пароли не переносятся, ящики "
                      "пересоздайте на странице «Почта»"
                      % len(mail["mailboxes"]))

    CTX.store.save()
    summary = ("Импорт завершён: сайтов создано %d, обновлено %d"
              % (created, updated))
    return True, summary, report
