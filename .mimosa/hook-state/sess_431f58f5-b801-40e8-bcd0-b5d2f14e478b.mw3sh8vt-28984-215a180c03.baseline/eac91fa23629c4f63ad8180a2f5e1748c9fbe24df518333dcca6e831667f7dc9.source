# -*- coding: utf-8 -*-
"""Живучесть сайтов: фоновые HTTP-проверки, uptime %, инциденты,
история занятого места (для графика роста)."""
import datetime as dt
import os
import secrets
import threading
import urllib.error
import urllib.request

from ..context import CTX, STATE_LOCK, run
from .. import utils

# замер места не чаще, чем раз в 6 часов; храним 90 точек (~3 недели)
DISK_PERIOD = 6 * 3600
DISK_KEEP = 90


def _health_data(domain):
    return CTX.store.data.setdefault("health", {}).setdefault(
        domain, {"checks": [], "incidents": []})


def snapshot_disk(site):
    """Записывает точку размера папки сайта в историю (если пора)."""
    h = _health_data(site["domain"])
    hist = h.setdefault("disk", [])
    now = utils.now_str()          # "2026-11-03 12:00:00"
    if hist:
        try:
            last = dt.datetime.strptime(hist[-1]["t"], "%Y-%m-%d %H:%M:%S")
            if (dt.datetime.now() - last).total_seconds() < DISK_PERIOD:
                return
        except ValueError:
            pass
    docroot = site.get("docroot") or ""
    if not os.path.isabs(docroot):
        docroot = os.path.join(CTX.home, docroot)
    size = utils.dir_size(docroot)
    hist.append({"t": now, "mb": round(size / 1024 / 1024, 1)})
    del hist[:-DISK_KEEP]
    CTX.store.save()


def _server_public_ip():
    """Первый публичный IPv4 сервера (для проверки через внешний адрес)."""
    code, out, _ = run(["hostname", "-I"], timeout=10)
    for ip in (out or "").split():
        if ":" not in ip and not ip.startswith(("127.", "10.", "192.168.")):
            return ip
    return ""


def _check_via_ip(site, ip):
    """Проверка через публичный IP сервера с Host-заголовком: ловит
    «nginx не слушает / файрвол закрыл порт 80», что не видно при
    проверке через 127.0.0.1."""
    import time as _t
    import urllib.error
    import urllib.request
    url = "http://%s/" % ip
    req = urllib.request.Request(
        url, headers={"Host": site["domain"],
                      "User-Agent": "HostPanel/health-external"})
    t0 = _t.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code, ok = resp.status, resp.status < 400
    except urllib.error.HTTPError as e:
        code, ok = e.code, False
    except Exception:  # noqa: BLE001
        code, ok = 0, False
    return {"ok": ok, "code": code,
            "ms": max(1, int((_t.time() - t0) * 1000))}


def check_site(site):
    """Одна проверка сайта. Считает код ответа и время.
    Отключённый сайт = не работает."""
    h = _health_data(site["domain"])
    entry = {"t": utils.now_str(), "ok": False, "ms": 0, "code": 0}
    if not site.get("enabled"):
        entry["code"] = 0
        _record(h, entry, site)
        return entry
    if CTX.demo:
        import random
        from .demo_reliability import DEMO_RELIABILITY
        rel = DEMO_RELIABILITY.get(site["domain"], 0.99)
        ok = random.random() < rel
        entry.update({"ok": ok, "ms": random.randint(12, 240) if ok else 0,
                      "code": 200 if ok else 502})
        _record(h, entry, site)
        return entry
    url = "http://127.0.0.1/"
    req = urllib.request.Request(
        url, headers={"Host": site["domain"], "User-Agent": "HostPanel/health"})
    import time
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            entry["code"] = resp.status
            entry["ok"] = resp.status < 400
    except urllib.error.HTTPError as e:
        entry["code"] = e.code
        entry["ok"] = False  # даже 503 maintenance = недоступен
    except Exception:  # noqa: BLE001 — любая сетевая ошибка
        entry["code"] = 0
        entry["ok"] = False
    entry["ms"] = max(1, int((time.time() - t0) * 1000))
    # параллельная проверка через публичный IP (не в демо)
    if not CTX.demo:
        ip = _server_public_ip()
        if ip:
            try:
                entry["ext"] = _check_via_ip(site, ip)
            except Exception:  # noqa: BLE001
                entry["ext"] = None
    _record(h, entry, site)
    return entry


def _record(h, entry, site):
    # мутация state + save под общим STATE_LOCK: HealthThread — отдельный
    # поток, без лока json.dump в save() может увидеть мутируемый dict
    notify_msg = None
    with STATE_LOCK:
        h["checks"].append(entry)
        h["checks"] = h["checks"][-2016:]
        if not entry["ok"]:
            if not h["incidents"] or h["incidents"][0].get("end"):
                h["incidents"].insert(0, {"start": entry["t"], "end": "",
                                          "code": entry["code"]})
                notify_msg = ("Сайт %s недоступен (HTTP %s)"
                              % (site["domain"],
                                 entry["code"] or "нет связи"))
                CTX.store.notify(notify_msg, "error")
        else:
            if h["incidents"] and not h["incidents"][0].get("end"):
                h["incidents"][0]["end"] = entry["t"]
                notify_msg = "Сайт %s снова доступен" % site["domain"]
                CTX.store.notify(notify_msg, "ok")
        CTX.store.save()
    if not notify_msg:
        return
    if entry["ok"]:
        _external(notify_msg, "Сайт восстановился.")
    else:
        _external(notify_msg, "Сайт упал. Панель продолжит проверять его "
                              "каждые %d секунд." % int(
                                  CTX.store.data["settings"].get(
                                      "health_interval", 60) or 60))


def _external(title, text):
    """Дублирует инцидент во внешние каналы (e-mail/Telegram)."""
    try:
        from . import notify
        if notify.configured():
            notify.send("HostPanel: " + title, text)
    except Exception as e:  # noqa: BLE001 — доставка не должна ломать поток
        utils.log("Notify: %s" % e)


def uptime_pct(domain, hours=24):
    """Процент успешных проверок за период."""
    h = CTX.store.data.get("health", {}).get(domain)
    if not h or not h.get("checks"):
        return None
    since = dt.datetime.now() - dt.timedelta(hours=hours)
    total = ok = 0
    for ch in h["checks"]:
        try:
            t = dt.datetime.strptime(ch["t"][:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if t < since:
            continue
        total += 1
        if ch.get("ok"):
            ok += 1
    if not total:
        return None
    return round(ok * 100.0 / total, 2)


def site_report(site):
    """Сводка живучести для UI."""
    h = CTX.store.data.get("health", {}).get(site["domain"],
                                             {"checks": [], "incidents": []})
    checks = h.get("checks", [])[-288:]  # сутки при интервале 5 мин
    return {
        "uptime_24h": uptime_pct(site["domain"], 24),
        "uptime_7d": uptime_pct(site["domain"], 24 * 7),
        "last": checks[-1] if checks else None,
        "incidents": (h.get("incidents") or [])[:10],
        "series": [{"t": c["t"][11:16], "ok": 1 if c.get("ok") else 0,
                    "ms": c.get("ms", 0)} for c in checks[-120:]],
        "avg_ms": (sum(c.get("ms", 0) for c in checks) // len(checks))
        if checks else 0,
    }


def _watch_fail2ban():
    """Security-уведомления: новые баны fail2ban (jail панели) —
    сравниваем текущий список забаненных с прошлым в state."""
    if not CTX.store.data["settings"].get("notify", {}).get(
            "security", {}).get("enabled"):
        return
    if not have("fail2ban-client"):
        return
    code, out, _ = run(["fail2ban-client", "status", "hostpanel"],
                       timeout=10, as_root=True)
    if code != 0:
        return
    current = set()
    for ln in (out or "").splitlines():
        if "banned ip" in ln.lower() or "banned:" in ln.lower():
            current.update(x for x in ln.split(":", 1)[-1].split() if x)
    with STATE_LOCK:
        prev = set(CTX.store.data.setdefault("security_watch", {})
                   .get("banned", []))
        new = current - prev
        if current != prev:
            CTX.store.data.setdefault("security_watch", {})[
                "banned"] = sorted(current)
            CTX.store.save()
    if new:
        CTX.store.notify("Fail2ban: новые блокировки: %s"
                         % ", ".join(sorted(new)[:8]), "warn")
        try:
            from . import notify
            notify.send("HostPanel: fail2ban",
                        "Новые блокировки: %s" % ", ".join(sorted(new)[:8]))
        except Exception as e:  # noqa: BLE001
            utils.log("notify fail2ban: %s" % e)


class HealthThread(threading.Thread):
    """Фоновый поток: периодически проверяет все включённые сайты."""

    def __init__(self):
        super().__init__(daemon=True, name="hostpanel-health")
        self._stop = threading.Event()

    def run(self):
        import time
        while not self._stop.is_set():
            try:
                interval = int(CTX.store.data["settings"].get(
                    "health_interval", 60) or 60)
            except (TypeError, ValueError):
                interval = 60
            interval = max(15, min(3600, interval))
            try:
                for site in list(CTX.store.data.get("sites", [])):
                    if site.get("enabled"):
                        check_site(site)
                        snapshot_disk(site)
            except Exception as e:  # noqa: BLE001
                utils.log("Health-check: %s" % e)
            # security-уведомления: новые баны fail2ban
            try:
                _watch_fail2ban()
            except Exception as e:  # noqa: BLE001
                utils.log("fail2ban watch: %s" % e)
            self._stop.wait(interval)

    def stop(self):
        self._stop.set()
