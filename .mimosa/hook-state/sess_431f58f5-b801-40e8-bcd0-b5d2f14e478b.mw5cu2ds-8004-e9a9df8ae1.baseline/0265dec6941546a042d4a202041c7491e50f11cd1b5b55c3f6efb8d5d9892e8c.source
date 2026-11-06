# -*- coding: utf-8 -*-
"""Статистика сайтов (инкрементальный парсинг access-логов),
фильтрация логов и оценка нагрузки сайта на систему."""
import datetime as dt
import os
import re
import subprocess

from .. import config
from ..context import CTX
from .. import utils

ACCESS_RE = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "([A-Z]+) ([^"]*?) [^"]*" (\d{3}) (\d+|-) '
    r'"([^"]*)" "([^"]*)"')


def _parse_access_lines(lines, filtr=None):
    """Разбирает строки combined-лога -> агрегаты (с необязательным фильтром)."""
    st = {"requests": 0, "bytes": 0, "codes": {}, "urls": {}, "ips": {},
          "daily": {}, "bots": 0, "methods": {}, "refs": {}, "hours": {},
          "uas": {}}
    for line in lines:
        m = ACCESS_RE.match(line)
        if not m:
            continue
        ip, tstr, meth, url, code, size, ref, ua = m.groups()
        if filtr and not _match_filter(filtr, ip, code, url, tstr, ua):
            continue
        st["requests"] += 1
        st["bytes"] += int(size) if size.isdigit() else 0
        st["codes"][code] = st["codes"].get(code, 0) + 1
        st["urls"][url] = st["urls"].get(url, 0) + 1
        st["ips"][ip] = st["ips"].get(ip, 0) + 1
        is_bot = bool(re.search(r"bot|crawler|spider|slurp", ua, re.I))
        if is_bot:
            st["bots"] += 1
        if meth:
            st["methods"][meth] = st["methods"].get(meth, 0) + 1
        if ref and ref != "-":
            # схема и www не интересны: остаётся домен-источник
            host = re.sub(r"^https?://(www\.)?", "", ref, flags=re.I)
            host = host.split("/")[0].split("?")[0]
            if host:
                st["refs"][host] = st["refs"].get(host, 0) + 1
        try:
            ts = dt.datetime.strptime(tstr.split(" ")[0],
                                      "%d/%b/%Y:%H:%M:%S")
            hh = "%02d" % ts.hour
            st["hours"][hh] = st["hours"].get(hh, 0) + 1
            day = ts.strftime("%Y-%m-%d")
        except ValueError:
            try:
                day = dt.datetime.strptime(tstr.split(":")[0],
                                           "%d/%b/%Y").strftime("%Y-%m-%d")
            except ValueError:
                day = "unknown"
            hh = None
        d = st["daily"].setdefault(day, {"requests": 0, "bytes": 0})
        d["requests"] += 1
        d["bytes"] += int(size) if size.isdigit() else 0
        # топ User-Agent: только семья (первый «товарный» токен)
        ua_family = ua.split(" ")[0][:60] if ua and ua != "-" else ""
        if ua_family:
            st["uas"][ua_family] = st["uas"].get(ua_family, 0) + 1
    return st


def _match_filter(f, ip, code, url, tstr, ua):
    """Логика фильтра логов: код, IP, подстрока URL, период, только ошибки."""
    if f.get("errors_only") and code[:1] not in "45":
        return False
    if f.get("code") and code != str(f["code"]):
        return False
    if f.get("ip") and ip != f["ip"]:
        return False
    if f.get("url") and f["url"].lower() not in url.lower():
        return False
    if f.get("since"):
        try:
            ts = dt.datetime.strptime(tstr.split(":")[0], "%d/%b/%Y")
            if ts < dt.datetime.strptime(f["since"], "%Y-%m-%d"):
                return False
        except ValueError:
            pass
    if f.get("until"):
        try:
            ts = dt.datetime.strptime(tstr.split(":")[0], "%d/%b/%Y")
            if ts > dt.datetime.strptime(f["until"], "%Y-%m-%d"):
                return False
        except ValueError:
            pass
    if f.get("bots_only") and not re.search(r"bot|crawler|spider", ua, re.I):
        return False
    return True


def _merge_stats(dst, src):
    for key in ("requests", "bytes", "bots"):
        dst[key] = dst.get(key, 0) + src.get(key, 0)
    for key in ("codes", "urls", "ips", "daily", "methods", "refs",
                "hours", "uas"):
        for k, v in src.get(key, {}).items():
            if isinstance(v, dict):
                cur = dst.setdefault(key, {}).setdefault(
                    k, {"requests": 0, "bytes": 0})
                cur["requests"] += v["requests"]
                cur["bytes"] += v["bytes"]
            else:
                dst.setdefault(key, {})[k] = \
                    dst[key].get(k, 0) + v


def _empty_agg():
    return {"requests": 0, "bytes": 0, "bots": 0, "codes": {}, "urls": {},
            "ips": {}, "daily": {}, "methods": {}, "refs": {}, "hours": {},
            "uas": {}}


def _stats_payload(agg, days, filtered=False):
    """Единый вид ответа из агрегата (+ срез по дням за период)."""
    today = dt.date.today()
    day_keys = [(today - dt.timedelta(days=i)).isoformat()
                for i in range(days - 1, -1, -1)]
    series = [{"day": d,
               "requests": agg["daily"].get(d, {}).get("requests", 0),
               "bytes": agg["daily"].get(d, {}).get("bytes", 0)}
              for d in day_keys]
    return {
        "requests": agg["requests"],
        "bytes": agg["bytes"],
        "bots": agg.get("bots", 0),
        "unique_ips": len(agg.get("ips", {})),
        "codes": sorted(agg["codes"].items(), key=lambda x: -x[1]),
        "top_urls": sorted(agg["urls"].items(), key=lambda x: -x[1])[:12],
        "top_ips": sorted(agg["ips"].items(), key=lambda x: -x[1])[:10],
        "methods": sorted(agg.get("methods", {}).items(),
                          key=lambda x: -x[1]),
        "top_refs": sorted(agg.get("refs", {}).items(),
                           key=lambda x: -x[1])[:8],
        "hours": [("%02d:00" % int(h), agg["hours"][h])
                  for h in sorted(agg.get("hours", {}).keys())
                  if h.isdigit()],
        "top_uas": sorted(agg.get("uas", {}).items(),
                          key=lambda x: -x[1])[:6],
        "series": series,
        "filtered": filtered,
    }


STATS_FILTER_VERSION = 2   # смена схемы агрегата -> пересчёт лога
STATS_FILTER_MAX_BYTES = 20_000_000   # потолок разового парса с фильтром


def _filtered_stats(site, days, filtr):
    """Статистика с фильтрами: разовый парс хвоста лога (без кеша)."""
    from .templates import site_log_paths
    path = site_log_paths(site)["access"]
    try:
        size = os.path.getsize(path)
    except OSError:
        return _stats_payload(_empty_agg(), days, filtered=True)
    with open(path, "rb") as f:
        if size > STATS_FILTER_MAX_BYTES:
            f.seek(size - STATS_FILTER_MAX_BYTES)
        data = f.read(STATS_FILTER_MAX_BYTES)
    lines = data.decode("utf-8", "replace").splitlines()
    if size > STATS_FILTER_MAX_BYTES and lines:
        lines = lines[1:]
    agg = _parse_access_lines(lines, filtr=filtr)
    return _stats_payload(agg, days, filtered=True)


def site_stats(site, days=14, filtr=None):
    """Статистика сайта: инкрементальный парсинг access-лога.

    filtr (code/ip/url/since/until/errors_only/bots_only) — считается
    заново по хвосту лога без кеша; без фильтра — инкрементальный агрегат.
    """
    if filtr:
        return _filtered_stats(site, days, filtr)
    from .templates import site_log_paths
    paths = site_log_paths(site)
    cache = CTX.store.data.setdefault("stats", {}).setdefault(
        site["domain"], {})
    path = paths["access"]
    offset = cache.get("offset", 0)
    agg = cache.get("agg") or _empty_agg()
    if cache.get("v") != STATS_FILTER_VERSION:
        # старая схема агрегата — пересчитываем с нуля
        offset, agg = 0, _empty_agg()
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if offset > size:  # лог ротирован — читаем заново
        offset, agg = 0, _empty_agg()
    if size > offset:
        with open(path, "rb") as f:
            f.seek(offset)
            raw = f.read(8_000_000)
        # последняя строка может быть обрезана — не сдвигаемся дальше неё
        nl = raw.rfind(b"\n")
        if nl > 0:
            raw = raw[:nl + 1]
            offset += nl + 1
            text = raw.decode("utf-8", "replace")
            _merge_stats(agg, _parse_access_lines(text.splitlines()))
            cache["offset"] = offset
            cache["agg"] = agg
            cache["v"] = STATS_FILTER_VERSION
            CTX.store.save()
    return _stats_payload(agg, days)


def read_log(site, kind="access", max_bytes=None, filtr=None, limit=300):
    """Читает журнал сайта; с фильтром — перебирает строки с конца."""
    from .templates import site_log_paths
    max_bytes = max_bytes or config.MAX_LOG_READ
    path = site_log_paths(site)["error" if kind == "error" else "access"]
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], 0
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read(max_bytes)
    lines = data.decode("utf-8", "replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    total = len(lines)
    if filtr:
        lines = [ln for ln in lines if _line_matches(ln, kind, filtr)]
    return lines[-limit:], total


def _line_matches(line, kind, f):
    """Фильтр по строке лога (access — по regex, error — по подстрокам)."""
    if f.get("q"):
        if f["q"].lower() not in line.lower():
            return False
    if f.get("since") or f.get("until"):
        m = re.match(r"\[(\d{2}/[A-Za-z]{3}/\d{4})", line) or \
            re.match(r"(\d{4}/\d{2}/\d{2})", line)
        if m:
            try:
                raw = m.group(1)
                ts = dt.datetime.strptime(raw, "%d/%b/%Y") if "/" in raw \
                    else dt.datetime.strptime(raw, "%Y/%m/%d")
            except ValueError:
                ts = None
            if ts:
                if f.get("since") and ts < dt.datetime.strptime(
                        f["since"], "%Y-%m-%d"):
                    return False
                if f.get("until") and ts > dt.datetime.strptime(
                        f["until"], "%Y-%m-%d"):
                    return False
    if kind == "access":
        m = ACCESS_RE.match(line)
        if not m:
            return True
        ip, tstr, _meth, url, code, _size, _ref, ua = m.groups()
        return _match_filter(f, ip, code, url, tstr, ua)
    if f.get("errors_only") and "[error]" not in line and "error" not in line:
        return False
    return True


# ------------------------------------------------- нагрузка на систему ---

def site_load(site):
    """Нагрузка сайта на систему: процессы PHP-FPM пула / Node-юнита
    (CPU %, память, время работы) через ps."""
    from .templates import pool_name
    result = {"php": [], "node": None}
    pool = pool_name(site["domain"])
    if CTX.demo:
        import random
        n = random.randint(2, 6) if site.get("php") else 0
        result["php"] = [{"pid": 1000 + i * 7, "cpu": round(
            random.uniform(0.2, 14.5), 1),
            "mem_mb": round(random.uniform(18, 96), 1), "time": "1-03:14:07"}
            for i in range(n)]
        if site.get("node", {}).get("enabled"):
            result["node"] = {"pid": 2043, "cpu": 2.4, "mem_mb": 143.8,
                              "time": "12:20:33"}
        _totals(result)
        return result
    try:
        out = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,rss,etimes,"
                             "comm,args", "--no-headers"],
                             capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return result
    for line in out.splitlines():
        parts = line.split(None, 6)
        if len(parts) < 6:
            continue
        pid, pcpu, _pmem, rss, etimes, comm = parts[:6]
        args = parts[6] if len(parts) > 6 else ""
        entry = {"pid": int(pid), "cpu": float(pcpu),
                 "mem_mb": round(int(rss) / 1024, 1),
                 "time": _fmt_elapsed(int(etimes))}
        if "php-fpm" in comm and ("pool %s" % pool) in args:
            result["php"].append(entry)
        elif comm == "node" and site.get("node", {}).get("enabled"):
            # cmdline node-приложения не содержит имени юнита/домена —
            # процесс сопоставляем по рабочей папке (docroot сайта)
            try:
                cwd = os.path.realpath("/proc/%s/cwd" % pid)
            except OSError:
                cwd = ""
            if cwd and cwd == os.path.realpath(
                    os.path.normpath(site["docroot"] if
                                     os.path.isabs(site["docroot"]) else
                                     os.path.join(CTX.home,
                                                  site["docroot"]))):
                result["node"] = entry
    _totals(result)
    return result


def _fmt_elapsed(sec):
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return "%d-%02d:%02d:%02d" % (days, hours, minutes, rem % 60)
    return "%02d:%02d:%02d" % (hours, minutes, rem % 60)


def _totals(result):
    php_cpu = sum(p["cpu"] for p in result["php"])
    php_mem = sum(p["mem_mb"] for p in result["php"])
    node = result["node"] or {"cpu": 0.0, "mem_mb": 0.0}
    result["total"] = {"cpu": round(php_cpu + node["cpu"], 1),
                       "mem_mb": round(php_mem + node["mem_mb"], 1),
                       "php_workers": len(result["php"])}


def totals_all_sites():
    """Суммарная нагрузка всех сайтов (для дашборда)."""
    store = CTX.store
    total = {"cpu": 0.0, "mem_mb": 0.0, "php_workers": 0}
    for site in store.data.get("sites", []):
        load = site_load(site)
        t = load.get("total") or {}
        total["cpu"] += t.get("cpu", 0.0)
        total["mem_mb"] += t.get("mem_mb", 0.0)
        total["php_workers"] += t.get("php_workers", 0)
    total["cpu"] = round(total["cpu"], 1)
    total["mem_mb"] = round(total["mem_mb"], 1)
    return total
