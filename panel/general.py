# -*- coding: utf-8 -*-
"""API: обзор, метрики, сессия, уведомления, журнал."""
import datetime as dt
import os
import time

from ..context import CTX
from .. import utils
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
              home=CTX.home, www_root=CTX.www_root)


@get("/api/overview")
def overview(handler, qs):
    from ..core import services, stats, health
    st = CTX.store.data
    return ok(metrics=metrics(),
              services=services.detect_services(),
              notifications=st.get("notifications", [])[:12],
              sites_count=len(st["sites"]),
              sites_enabled=len([s for s in st["sites"] if s["enabled"]]),
              sites_maintenance=len([s for s in st["sites"]
                                     if s.get("maintenance")]),
              backups_count=len(st.get("backups", [])),
              dbs_count=len(st.get("dbs", [])),
              sites_load=stats.totals_all_sites(),
              worst_uptime=min(
                  [h for h in (health.uptime_pct(s["domain"], 24)
                               for s in st["sites"]) if h is not None],
                  default=None))


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
