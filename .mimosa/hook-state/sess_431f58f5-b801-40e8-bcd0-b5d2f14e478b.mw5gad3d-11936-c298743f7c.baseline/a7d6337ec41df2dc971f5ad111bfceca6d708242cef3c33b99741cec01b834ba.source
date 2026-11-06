# -*- coding: utf-8 -*-
"""SSL-сертификаты: Let's Encrypt (certbot) и самоподписанные."""
import datetime as dt
import email.utils as _eu
import os
import re

from ..context import CTX, run, have
from .. import utils


def paths(domain):
    d = os.path.join(CTX.home, "certs", domain)
    os.makedirs(d, exist_ok=True)
    return {"cert": os.path.join(d, domain + ".crt"),
            "key": os.path.join(d, domain + ".key"),
            "dir": d}


def issue(site, kind, email=""):
    """Выпускает сертификат: letsencrypt (certbot) или selfsigned."""
    domain = site["domain"]
    if kind == "selfsigned" or CTX.demo:
        p = paths(domain)
        code, out, err = run(
            ["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
             "-keyout", p["key"], "-out", p["cert"], "-days", "3650",
             "-subj", "/CN=%s" % domain], timeout=60)
        ok = CTX.demo or code == 0
        if ok:
            site["ssl"] = {"kind": "selfsigned", "domains": [domain],
                           "expires": (dt.date.today() +
                                       dt.timedelta(days=3650)).isoformat()}
            CTX.store.notify("Выпущен самоподписанный сертификат для %s"
                             % domain)
        return ok, ("" if ok else (err or out or "openssl недоступен"))
    if not have("certbot"):
        return False, ("certbot не установлен — установите его в разделе "
                       "«Установка ПО» панели (элемент «Certbot»)")
    plugin = "--nginx" if site["webserver"].startswith("nginx") else "--apache"
    args = ["certbot", plugin, "-d", domain]
    # www добавляется в SAN только когда сайт действительно обслуживает
    # www (флаг www у сайта); поддомены никогда не имеют www-имени
    if site.get("www") and not site.get("parent"):
        args += ["-d", "www." + domain]
    # --expand: certbot обязан молча расширить существующий сертификат
    # (без него -non-interactive падает с вопросом «expand and replace?»)
    args += ["--expand", "--non-interactive", "--agree-tos",
             "--keep-until-expiring"]
    if email:
        args += ["-m", email]
    else:
        args += ["--register-unsafely-without-email"]
    code, out, err = run(args, timeout=180, as_root=True)
    ok = code == 0
    if ok:
        domains = [domain] + (["www." + domain]
                              if site.get("www") and not site.get("parent")
                              else [])
        site["ssl"] = {"kind": "letsencrypt", "domains": domains,
                       "expires": (dt.date.today() +
                                   dt.timedelta(days=90)).isoformat()}
        CTX.store.notify("Сертификат Let's Encrypt выпущен для %s" % domain)
    return ok, (err or out if not ok else "")


def delete(site):
    site["ssl"] = {"kind": "none", "domains": [], "expires": ""}
    if not CTX.demo and have("certbot"):
        run(["certbot", "delete", "--cert-name", site["domain"], "-n"],
            timeout=60, as_root=True)
    CTX.store.notify("Сертификат удалён: %s" % site["domain"])
    return True, ""


# --------------------------------------------------- автопродление --------
def cert_enddate(cert_path):
    """Дата окончания сертификата (YYYY-MM-DD) или '' — через openssl."""
    if not os.path.exists(cert_path):
        return ""
    code, out, _ = run(["openssl", "x509", "-enddate", "-noout",
                        "-in", cert_path], timeout=15)
    m = re.search(r"notAfter=(.+)", out or "")
    if code != 0 or not m:
        return ""
    try:
        parsed = _eu.parsedate_to_datetime(m.group(1).strip())
        return parsed.date().isoformat()
    except (TypeError, ValueError):
        return ""


def renew_all():
    """Продление Let's Encrypt и контроль сроков всех сертификатов.

    Вызывается из cron: `python3 -m panel --ssl-renew`. certbot renew
    продлевает только то, что истекает меньше чем через 30 дней; панель
    дополнительно сверяет фактические сроки с state.json и предупреждает,
    если какой-то сертификат истекает раньше чем через 14 дней."""
    store = CTX.store
    if CTX.demo or not have("certbot"):
        return
    le_sites = [s for s in store.data.get("sites", [])
                if (s.get("ssl") or {}).get("kind") == "letsencrypt"]
    if le_sites:
        code, out, err = run(["certbot", "renew", "--quiet"],
                             timeout=1800, as_root=True)
        if code != 0:
            store.notify("Автопродление SSL: ошибка certbot: %s"
                         % ((err or out or "неизвестная ошибка")[:200]),
                         "warn")
        else:
            from . import templates
            templates.webserver_reload()
    # фактические сроки сверяем для всех сертификатов (LE и самоподписанных)
    soon = []
    for site in store.data.get("sites", []):
        ssl = site.get("ssl") or {}
        if ssl.get("kind") in ("", "none"):
            continue
        exp = cert_enddate(paths(site["domain"])["cert"])
        if not exp:
            continue
        if exp != ssl.get("expires"):
            ssl["expires"] = exp
        try:
            days = (dt.date.fromisoformat(exp) - dt.date.today()).days
        except ValueError:
            continue
        if days <= 14:
            soon.append("%s (%s дн.)" % (site["domain"], max(days, 0)))
    store.save()
    if soon:
        store.notify("Сертификаты истекают менее чем через 14 дней: %s — "
                     "перевыпустите их в настройках сайта"
                     % ", ".join(soon), "warn")
