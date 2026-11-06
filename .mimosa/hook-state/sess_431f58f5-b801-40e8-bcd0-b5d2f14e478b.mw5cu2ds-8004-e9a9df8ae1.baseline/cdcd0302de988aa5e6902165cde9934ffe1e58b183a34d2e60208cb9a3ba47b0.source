# -*- coding: utf-8 -*-
"""Фильтры доступа в духе Cloudflare: гео-страны, IP-списки,
блокировка ботов, базовый WAF, ограничение частоты запросов.

Генерирует секции для nginx (основной путь) и Apache (по возможностям).
"""
import os

from .. import config
from ..context import CTX, have
from .. import utils

GEO_CONF_PATH = "/etc/nginx/conf.d/hostpanel-geo.conf"
RATELIMIT_CONF_PATH = "/etc/nginx/conf.d/hostpanel-ratelimit.conf"


def geoip2_ready():
    """Гео-фильтр требует модуля geoip2 и базы GeoLite2-Country."""
    return os.path.exists(
        "/usr/lib/nginx/modules/ngx_http_geoip2_module.so") and \
        os.path.exists("/usr/share/GeoIP/GeoLite2-Country.mmdb")


def geo_wanted_countries():
    """[(domain, mode, [страны])] для всех сайтов с активным гео-фильтром."""
    out = []
    for site in CTX.store.data.get("sites", []):
        sec = site.get("security") or {}
        mode = sec.get("geo_mode", "off")
        countries = [c.upper() for c in (sec.get("geo_countries") or [])
                     if utils.valid_country(c)]
        if mode in ("allow", "deny") and countries:
            out.append((site["domain"], mode, countries))
    return out


def ensure_geo_map():
    """Пишет conf.d/hostpanel-geo.conf (внутри http{}) с map-директивами
    для всех сайтов с гео-фильтрами. Возвращает (ok, err)."""
    store = CTX.store
    allowed_all = [(d, c) for d, m, c in geo_wanted_countries()
                   if m == "allow"]
    denied_all = [(d, c) for d, m, c in geo_wanted_countries() if m == "deny"]
    if not geoip2_ready():
        # без модуля/базы map-директивы писать нельзя (nginx -t упадёт);
        # оставляем файл-комментарий, чтобы include оставался валидным
        content = ("# HostPanel: гео-фильтр отключён — требуется "
                   "libnginx-mod-http-geoip2 и GeoLite2-Country.mmdb\n")
    else:
        lines = ["# HostPanel: гео-карты стран (nginx map + GeoIP2)",
                 "geoip2 /usr/share/GeoIP/GeoLite2-Country.mmdb {"]
        lines.append("    auto_reload 5m;")
        lines.append("    $country_code country iso_code;")
        lines.append("}")
        for domain, countries in allowed_all:
            lines.append("map $country_code $allowed_%s {" % _key(domain))
            lines.append("    default no;")
            for c in countries:
                lines.append("    %s yes;" % c)
            lines.append("}")
        for domain, countries in denied_all:
            lines.append("map $country_code $denied_%s {" % _key(domain))
            lines.append("    default no;")
            for c in countries:
                lines.append("    %s yes;" % c)
            lines.append("}")
        content = "\n".join(lines) + "\n"
    if CTX.demo:
        return True, ""
    try:
        os.makedirs("/etc/nginx/conf.d", exist_ok=True)
        with open(GEO_CONF_PATH + ".hp-tmp", "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(GEO_CONF_PATH + ".hp-tmp", GEO_CONF_PATH)
    except OSError as e:
        return False, str(e)
    if (allowed_all or denied_all) and not geoip2_ready():
        return False, ("не установлен libnginx-mod-http-geoip2 "
                       "или база GeoLite2-Country.mmdb")
    return True, ""


def _key(domain):
    import re
    return re.sub(r"[^a-z0-9]", "", domain.lower())[:32]


def geo_config_for_site(site):
    """Точная секция для конкретного сайта (использует map по домену)."""
    sec = site.get("security") or {}
    mode = sec.get("geo_mode", "off")
    countries = [c.upper() for c in (sec.get("geo_countries") or [])
                 if utils.valid_country(c)]
    if mode == "off" or not countries:
        return ""
    if not geoip2_ready():
        return "    # гео-фильтр неактивен: нет модуля geoip2 или базы GeoLite2"
    key = _key(site["domain"])
    if mode == "allow":
        return ("    if ($allowed_%s = no) { return 403; }\n"
                "    # доступ только из: %s" % (key, ", ".join(countries)))
    return ("    if ($denied_%s = yes) { return 403; }\n"
            "    # запрещён доступ из: %s" % (key, ", ".join(countries)))


def ip_filters(sec):
    """Разрешённые/запрещённые IP: allow/deny для nginx."""
    allow = [ip for ip in (sec.get("ip_allow") or []) if utils.valid_ip(ip)]
    deny = [ip for ip in (sec.get("ip_deny") or []) if utils.valid_ip(ip)]
    if not allow and not deny:
        return ""
    lines = ["    # IP-фильтры HostPanel"]
    lines += ["    deny %s;" % ip for ip in deny]
    lines += ["    allow %s;" % ip for ip in allow]
    if allow:
        lines.append("    deny all;")
    return "\n".join(lines)


def bot_filter():
    # BAD_BOTS_RE уже содержит префикс-модификатор "~*" — не дублируем его
    pat = config.BAD_BOTS_RE
    if pat.startswith("~*"):
        pat = pat[2:]
    return ('    if ($http_user_agent ~* "%s") { return 403; }\n'
            '    # блокировка известных ботов/сканеров' % pat)


def waf_filter(sec):
    if not sec.get("waf"):
        return ""
    return ('    set $waf_hit 0;\n'
            '    if ($args ~* "%s") { set $waf_hit 1; }\n'
            '    if ($request_uri ~* "%s") { set $waf_hit 1; }\n'
            '    if ($waf_hit = 1) { return 403; }\n'
            '    # WAF: SQLi/XSS/скрытые файлы' %
            (config.WAF_ARGS_RE, config.WAF_PATHS_RE))


def rate_limit_zones(sites):
    """Секции limit_req_zone для http{} (conf.d-файл)."""
    zones = []
    seen = set()
    for site in sites:
        sec = site.get("security") or {}
        rps = int(sec.get("rate_limit") or 0)
        if rps <= 0:
            continue
        key = _key(site["domain"])
        if key in seen:
            continue
        seen.add(key)
        zones.append("limit_req_zone $binary_remote_addr zone=hp_rl_%s:"
                     "10m rate=%dr/s;" % (key, rps))
    return "\n".join(zones)


def ensure_rate_limit_conf():
    """Пишет conf.d/hostpanel-ratelimit.conf с зонами limit_req."""
    store = CTX.store
    zones = rate_limit_zones(store.data.get("sites", []))
    content = ("# HostPanel: зоны ограничения частоты запросов\n" +
               (zones + "\n" if zones else "# зон нет\n"))
    if CTX.demo:
        return True, ""
    try:
        with open(RATELIMIT_CONF_PATH + ".hp-tmp", "w",
                  encoding="utf-8") as f:
            f.write(content)
        os.replace(RATELIMIT_CONF_PATH + ".hp-tmp", RATELIMIT_CONF_PATH)
    except OSError as e:
        return False, str(e)
    return True, ""


def apply_security(site):
    """Применяет фильтры сайта: обновляет geo/ratelimit конфиги,
    перегенерирует конфиг сайта и проверяет синтаксис nginx."""
    from . import templates
    if CTX.demo:
        return True, "демо: фильтры сохранены"
    if any(m != "off" for _d, m, _c in geo_wanted_countries()):
        ok, err = ensure_geo_map()
        if not ok:
            return False, "гео-конфиг: %s" % err
    ok, err = ensure_rate_limit_conf()
    if not ok:
        return False, "rate-limit конфиг: %s" % err
    ok, err = templates.write_site_configs(site)
    if not ok:
        return False, err
    return True, ""


def site_section(site, sec=None):
    """Собирает секцию фильтров конкретного сайта (с map-ключом)."""
    sec = sec or site.get("security") or {}
    blocks = []
    geo = geo_config_for_site(site)
    if geo:
        blocks.append(geo)
    ips = ip_filters(sec)
    if ips:
        blocks.append(ips)
    if sec.get("block_bots"):
        blocks.append(bot_filter())
    waf = waf_filter(sec)
    if waf:
        blocks.append(waf)
    rps = int(sec.get("rate_limit") or 0)
    if rps > 0:
        burst = int(sec.get("rate_burst") or 20)
        blocks.append("    limit_req zone=hp_rl_%s burst=%d nodelay;\n"
                      "    # ограничение %d запросов/сек" %
                      (_key(site["domain"]), burst, rps))
    if not blocks:
        return "    # фильтры не настроены"
    return "\n".join(blocks)


def apache_filters(sec):
    """Фильтры для Apache (упрощённо: IP-списки и боты)."""
    allow = [ip for ip in (sec.get("ip_allow") or []) if utils.valid_ip(ip)]
    deny = [ip for ip in (sec.get("ip_deny") or []) if utils.valid_ip(ip)]
    lines = []
    for ip in deny:
        lines.append("    <Location />\n        Require not ip %s\n"
                     "    </Location>" % ip)
    if allow:
        lines.append("    <Location />\n        Require ip %s\n"
                     "    </Location>" % " ".join(allow))
    return "\n".join(lines)


def security_status(sec):
    """Краткое описание активных фильтров для UI."""
    parts = []
    if sec.get("geo_mode") == "allow":
        parts.append("только %s" % ", ".join(sec.get("geo_countries") or []))
    elif sec.get("geo_mode") == "deny":
        parts.append("кроме %s" % ", ".join(sec.get("geo_countries") or []))
    if sec.get("ip_deny"):
        parts.append("IP-блок: %d" % len(sec["ip_deny"]))
    if sec.get("ip_allow"):
        parts.append("IP-allow: %d" % len(sec["ip_allow"]))
    if sec.get("block_bots"):
        parts.append("боты блокируются")
    if sec.get("waf"):
        parts.append("WAF включён")
    if int(sec.get("rate_limit") or 0) > 0:
        parts.append("лимит %d р/с" % int(sec["rate_limit"]))
    return " · ".join(parts) or "нет"


def geo_module_available():
    """Установлен ли модуль geoip2 для nginx с базой (или демо)."""
    if CTX.demo:
        return True
    return have("nginx") and geoip2_ready()
