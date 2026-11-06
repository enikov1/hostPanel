# -*- coding: utf-8 -*-
"""API: обзор, метрики, сессия, уведомления, журнал."""
import datetime as dt
import os
import time

from ..context import CTX
from .. import utils
from ..config import SESSION_TTL
from .router import get, post, ok, err, done

_METRICS = {"cpu": 12.0, "prev_net": None, "prev_t": 0.0, "prev_stat": None,
            "net_in": 0.0, "net_out": 0.0, "hist": []}


def _read_cpu_total():
    with open("/proc/stat") as f:
        parts = f.readline().split()[1:]
    vals = [int(x) for x in parts]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def metrics():
    """Текущие метрики сервера: CPU, память, диск, сеть, load, аптайм."""
    m = _METRICS
    while len(m["hist"]) < 12:
        m["hist"].insert(0, m["cpu"])
    if CTX.demo:
        import random
        m["cpu"] = min(96.0, max(3.0, m["cpu"] + random.uniform(-6, 5.5)))
        ram_used = 6_100_000_000 + random.randint(-400_000_000, 400_000_000)
        load = [round(m["cpu"] / 100 * 8 * random.uniform(0.7, 1.1), 2),
                round(m["cpu"] / 100 * 8 * 0.8, 2),
                round(m["cpu"] / 100 * 8 * 0.6, 2)]
        m["net_in"] = max(0.05, m["net_in"] + random.uniform(-8, 8.5))
        m["net_out"] = max(0.05, m["net_out"] + random.uniform(-6, 6.5))
        data = {"cpu": round(m["cpu"], 1), "cores": 8, "load": load,
                "uptime_sec": 4_063_000,
                "ram": {"total": 16_000_000_000, "used": ram_used,
                        "percent": round(ram_used / 16_000_000_000 * 100, 1)},
                "disk": {"total": 480 * 1024 ** 3, "used": 298 * 1024 ** 3,
                         "percent": 62.1},
                "net": {"in_mbit": round(m["net_in"], 1),
                        "out_mbit": round(m["net_out"], 1)},
                "hist": m["hist"][-60:]}
        m["hist"].append(data["cpu"])
        m["hist"] = m["hist"][-60:]
        return data
    try:
        idle, total = _read_cpu_total()
        if m.get("prev_stat"):
            pidle, ptot = m["prev_stat"]
            m["cpu"] = round(max(0.0, min(
                100.0, (1 - (idle - pidle) / max(1, total - ptot)) * 100)), 1)
        m["prev_stat"] = (idle, total)
    except OSError:
        pass
    ram = {"total": 0, "used": 0, "percent": 0}
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
        ram["total"] = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        ram["used"] = max(0, ram["total"] - available)
        ram["percent"] = round(ram["used"] / ram["total"] * 100, 1) \
            if ram["total"] else 0
    except (OSError, ValueError):
        pass
    try:
        st = os.statvfs("/")
        disk = {"total": st.f_blocks * st.f_frsize,
                "used": (st.f_blocks - st.f_bfree) * st.f_frsize}
        disk["percent"] = round(disk["used"] / disk["total"] * 100, 1) \
            if disk["total"] else 0
    except OSError:
        disk = {"total": 0, "used": 0, "percent": 0}
    net = {"in_mbit": 0.0, "out_mbit": 0.0}
    try:
        rx = tx = 0
        with open("/proc/net/dev") as f:
            for line in f.readlines()[2:]:
                parts = line.split(":")
                if parts[0].strip() == "lo":
                    continue
                vals = parts[1].split()
                rx += int(vals[0])
                tx += int(vals[8])
        t = time.time()
        if m["prev_net"] and t - m["prev_t"] > 0.5:
            dt_ = t - m["prev_t"]
            net["in_mbit"] = round((rx - m["prev_net"][0]) * 8 / dt_ / 1e6, 1)
            net["out_mbit"] = round((tx - m["prev_net"][1]) * 8 / dt_ / 1e6, 1)
        m["prev_net"] = (rx, tx)
        m["prev_t"] = t
    except (OSError, IndexError):
        pass
    load = [0, 0, 0]
    try:
        with open("/proc/loadavg") as f:
            load = [float(x) for x in f.read().split()[:3]]
    except (OSError, ValueError):
        pass
    uptime = 0
    try:
        with open("/proc/uptime") as f:
            uptime = float(f.read().split()[0])
    except (OSError, ValueError):
        pass
    cores = os.cpu_count() or 1
    m["hist"].append(m["cpu"])
    m["hist"] = m["hist"][-60:]
    return {"cpu": m["cpu"], "cores": cores, "load": load,
            "uptime_sec": uptime, "ram": ram, "disk": disk, "net": net,
            "hist": list(m["hist"])}


@get("/api/me")
def me(handler, qs):
    from .. import config
    return ok(login=CTX.store.creds["login"],
              version=config.VERSION, demo=CTX.demo,
              home=CTX.home, www_root=CTX.www_root,
              expert=bool(CTX.store.data["settings"].get("expert_mode")),
              must_change_password=bool(
                  CTX.store.creds.get("must_change_password")))


@get("/api/overview")
def overview(handler, qs):
    from ..core import services, stats, health
    from ..core import db as db_mod
    st = CTX.store.data
    # в рабочем режиме считаем базы по MySQL, а не по legacy-записям state
    if CTX.demo:
        dbs_count = len(st.get("dbs", []))
    else:
        try:
            dbs_count = (len(db_mod.list_dbs("mysql")) +
                         len(db_mod.list_dbs("pg")))
        except Exception:  # noqa: BLE001
            dbs_count = len(st.get("dbs", []))
    return ok(metrics=metrics(),
              services=services.detect_services(),
              notifications=st.get("notifications", [])[:12],
              sites_count=len(st["sites"]),
              sites_enabled=len([s for s in st["sites"] if s["enabled"]]),
              sites_maintenance=len([s for s in st["sites"]
                                     if s.get("maintenance")]),
              backups_count=len(st.get("backups", [])),
              dbs_count=dbs_count,
              sites_load=stats.totals_all_sites(),
              worst_uptime=min(
                  [h for h in (health.uptime_pct(s["domain"], 24)
                               for s in st["sites"]) if h is not None],
                  default=None))


@get("/api/notifications")
def notifications_list(handler, qs):
    """Список уведомлений для колокольчика (лёгкий эндпоинт)."""
    return ok(notifications=CTX.store.data.get("notifications", [])[:20])


@get("/api/panellog")
def panellog(handler, qs):
    return ok(log=CTX.store.data.get("panel_log", [])[:200])


@post("/api/notifications/read")
def notifications_read(handler, body):
    CTX.store.data["notifications"] = []
    return done("уведомления очищены")


@post("/api/logout")
def logout(handler, body):
    from . import auth
    token = handler.headers.get("X-Panel-Token", "")
    if token:
        auth.drop_session(token)
    # если заголовка нет, но сессия живёт в cookie — тоже гасим
    for part in handler.headers.get("Cookie", "").split(";"):
        part = part.strip()
        if part.startswith("hp_token="):
            auth.drop_session(part[9:])
    return {"ok": True}, 200


# --------------------------------------------------- 2FA и сессии --------
@get("/api/sessions")
def sessions_list(handler, qs):
    from . import auth
    token = auth.check_session(handler) or ""
    return ok(sessions=auth.list_sessions(),
              current=auth.session_sid(token),
              ttl=SESSION_TTL)


@post("/api/sessions/drop")
def sessions_drop(handler, body):
    from . import auth
    sid = str(body.get("sid") or "")
    if not sid:
        return err("не указана сессия")
    if auth.drop_session_sid(sid):
        CTX.store.log_action("Завершена сессия %s" % sid)
        return done("сессия завершена")
    return err("сессия не найдена", 404)


@get("/api/totp/setup")
def totp_setup(handler, qs):
    """Новый (ещё не включённый) секрет для приложения-аутентификатора."""
    from . import auth
    if CTX.store.creds.get("totp_enabled"):
        return err("двухфакторная аутентификация уже включена")
    secret = auth.totp_secret_new()
    from ..context import have
    return ok(secret=secret, uri=auth.totp_uri(secret),
              qr=bool(have("qrencode")))


@get("/api/totp/qr")
def totp_qr(handler, qs):
    """QR-код otpauth-ссылки в SVG (нужен пакет qrencode)."""
    from . import auth
    from ..context import run, have
    if not have("qrencode"):
        return err("qrencode не установлен", 400)
    uri = qs.get("uri", [""])[0]
    if not uri.startswith("otpauth://"):
        return err("некорректная ссылка", 400)
    code, out, _ = run(["qrencode", "-t", "SVG", "-o", "-", uri],
                       timeout=15)
    if code != 0 or "<svg" not in (out or ""):
        return err("не удалось создать QR-код", 500)
    return ok(svg=out)


@post("/api/totp/enable")
def totp_enable(handler, body):
    """Включение 2FA: секрет + подтверждающий код из приложения."""
    from . import auth
    if CTX.store.creds.get("totp_enabled"):
        return err("двухфакторная аутентификация уже включена")
    secret = str(body.get("secret") or "").strip().upper()
    code = str(body.get("code") or "").strip()
    if len(secret) != 32 or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
                                    for c in secret):
        return err("некорректный секрет")
    if not auth.totp_valid(secret, code):
        return err("код неверен — проверьте время в приложении")
    CTX.store.creds["totp_secret"] = secret
    CTX.store.creds["totp_enabled"] = True
    CTX.store.save()
    CTX.store.log_action("Включена двухфакторная аутентификация (TOTP)")
    return done("двухфакторная аутентификация включена")


@post("/api/totp/disable")
def totp_disable(handler, body):
    """Выключение 2FA — требует текущий пароль администратора."""
    from . import auth
    if not auth.verify(body.get("password", ""), CTX.store.creds):
        return err("пароль указан неверно", 400)
    CTX.store.creds["totp_enabled"] = False
    CTX.store.creds.pop("totp_secret", None)
    CTX.store.save()
    CTX.store.log_action("Выключена двухфакторная аутентификация")
    return done("двухфакторная аутентификация выключена")


@get("/api/totp/status")
def totp_status(handler, qs):
    return ok(enabled=bool(CTX.store.creds.get("totp_enabled")))


# ------------------------------------------------- диск и поиск ------------

@get("/api/disk")
def disk_usage(handler, qs):
    """Куда уходит диск: крупные каталоги панели/системы + сайты."""
    import os
    from .. import config
    from ..context import run, have
    if CTX.demo:
        return ok(demo=True, used_gb=9.8, total_gb=14.7, percent=67,
                  top=[{"path": "/var/www", "gb": 4.2, "label": "Файлы сайтов"},
                       {"path": "/var/log", "gb": 1.8, "label": "Журналы"},
                       {"path": "/opt/hostpanel/backups", "gb": 2.1,
                        "label": "Резервные копии"},
                       {"path": "/var/lib/mysql", "gb": 1.1, "label": "Базы данных"},
                       {"path": "/var/cache/apt", "gb": 0.4,
                        "label": "Кэш apt"}],
                  cleanable={"apt": True, "journal": True, "tmp": True,
                             "backups": True})
    st = __import__("os").statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bfree * st.f_frsize
    targets = [
        (config.WWW_ROOT, "Файлы сайтов"),
        ("/var/log", "Журналы системы"),
        (os.path.join(CTX.home, "backups"), "Резервные копии"),
        ("/var/lib/mysql", "Базы данных (MariaDB)"),
        ("/var/lib/postgresql", "Базы данных (PostgreSQL)"),
        ("/var/cache/apt", "Кэш apt"),
        (os.path.join(CTX.home, "logs"), "Журналы сайтов"),
    ]
    top = []
    for path, label in targets:
        if not os.path.isdir(path):
            continue
        code, out, _ = run(["du", "-sB1", path], timeout=120, as_root=True)
        if code == 0 and (out or "").strip():
            try:
                size = int(out.split()[0])
            except (ValueError, IndexError):
                continue
            top.append({"path": path, "label": label,
                        "gb": round(size / 1024 ** 3, 2)})
    top.sort(key=lambda x: x["gb"], reverse=True)
    from ..core import services
    return ok(used_gb=round((total - free) / 1024 ** 3, 1),
              total_gb=round(total / 1024 ** 3, 1),
              percent=round((total - free) * 100.0 / total, 1) if total else 0,
              top=top[:8],
              cleanable={"apt": have("apt-get"),
                         "journal": have("journalctl"),
                         "tmp": True,
                         "backups": bool(CTX.store.data.get("backups"))})


@post("/api/disk/clean")
def disk_clean(handler, body):
    """Безопасная очистка: кэш apt, журнал systemd, tmp панели, бэкапы
    сверх последних трёх."""
    what = str(body.get("what") or "")
    if CTX.demo:
        return done("демо: очистка «%s» выполнена" % what)
    import glob as _glob
    import shutil as _shutil
    freed = ""
    if what == "apt":
        if not have("apt-get"):
            return err("apt-get недоступен")
        run(["apt-get", "clean"], timeout=300, as_root=True)
        freed = "кэш apt очищен"
    elif what == "journal":
        if not have("journalctl"):
            return err("journalctl недоступен")
        run(["journalctl", "--vacuum-time=7d"], timeout=120, as_root=True)
        freed = "журнал systemd урезан до 7 дней"
    elif what == "tmp":
        d = os.path.join(CTX.home, "tmp")
        for p in _glob.glob(os.path.join(d, "*")):
            try:
                if os.path.isdir(p):
                    _shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
            except OSError:
                pass
        freed = "временные файлы панели удалены"
    elif what == "backups":
        keep = max(3, int(CTX.store.data["settings"].get(
            "backup_retention", 7) or 7))
        bdir = os.path.join(CTX.home, "backups")
        files = sorted(_glob.glob(os.path.join(bdir, "backup-*.tar.gz")))
        removed = 0
        for p in files[:-keep]:
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
        CTX.store.data["backups"] = CTX.store.data.get("backups", [])[:keep]
        freed = "удалено копий сверх последних %d: %d" % (keep, removed)
    else:
        return err("неизвестная цель очистки")
    return done("Готово: %s" % freed)


@get("/api/search")
def search(handler, qs):
    """Поиск по панели: сайты, базы, ящики, задачи, разделы."""
    q = (qs.get("q", [""])[0] or "").strip().lower()
    if len(q) < 2:
        return ok(results=[])
    results = []
    st = CTX.store.data
    for s in st.get("sites", []):
        if q in s["domain"].lower():
            results.append({"type": "site", "title": s["domain"],
                            "page": "sites", "site_id": s["id"],
                            "hint": "сайт"})
    for d in st.get("dbs", []):
        if q in (d.get("name") or "").lower():
            results.append({"type": "db", "title": d["name"],
                            "page": "dbs", "hint": "база данных"})
    for m in st.get("mail", {}).get("mailboxes", []):
        if q in m.get("email", "").lower():
            results.append({"type": "mail", "title": m["email"],
                            "page": "mail", "hint": "почтовый ящик"})
    for j in st.get("cron", []):
        if q in (j.get("command") or "").lower() or \
                q in (j.get("comment") or "").lower():
            results.append({"type": "cron", "title": j.get("comment") or
                            (j.get("command") or "")[:60], "page": "cron",
                            "hint": "задача планировщика"})
    for b in st.get("backups", [])[:10]:
        if q in str(b.get("created", "")):
            results.append({"type": "backup", "title": "копия от %s" %
                            b.get("created", "?"), "page": "backups",
                            "hint": "резервная копия"})
    # разделы по названию/описанию
    for pg, title, desc in (
            ("sites", "Сайты", "создание и настройка сайтов"),
            ("dbs", "Базы данных", "mariadb postgresql базы"),
            ("mail", "Почта", "ящики домены письма"),
            ("files", "Файловый менеджер", "файлы загрузка правка"),
            ("backups", "Резервные копии", "бэкапы восстановление"),
            ("cron", "Планировщик", "расписание задачи cron"),
            ("software", "Установка ПО", "php nginx apache redis"),
            ("packages", "Пакеты и обновления", "apt обновления модули"),
            ("firewall", "Брандмауэр", "порты ufw файрвол"),
            ("settings", "Настройки", "пароль тема уведомления 2fa"),
            ("term", "Командная строка", "терминал shell")):
        if q in title.lower() or q in desc:
            results.append({"type": "page", "title": title, "page": pg,
                            "hint": "раздел"})
    return ok(results=results[:12])
