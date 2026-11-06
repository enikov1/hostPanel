# -*- coding: utf-8 -*-
"""API: почтовый сервер — статус, домены, ящики, тест доставки."""
import os
import re

from .. import config, utils
from ..context import CTX
from ..core import mail as mail_core
from .router import get, post, ok, err, done


@get("/api/mail")
def mail_status(handler, qs):
    st = mail_core.status()
    data = mail_core.list_all()
    return ok(status=st, domains=data["domains"],
              mailboxes=data["mailboxes"])


@post("/api/mail/domains/add")
def mail_domain_add(handler, body):
    okc, msg = mail_core.add_domain(str(body.get("domain") or ""))
    if not okc:
        return err(msg)
    return done(msg)


@post("/api/mail/domains/remove")
def mail_domain_remove(handler, body):
    okc, msg = mail_core.remove_domain(str(body.get("domain") or ""))
    if not okc:
        return err(msg)
    return done(msg)


@post("/api/mail/boxes/add")
def mail_box_add(handler, body):
    import secrets
    email = str(body.get("email") or "")
    password = str(body.get("password") or "").strip()
    if not password:
        password = secrets.token_urlsafe(12)
    okc, msg, password = mail_core.add_mailbox(email, password)
    if not okc:
        return err(msg)
    return done(msg, {"data": {"password": password}})


@post("/api/mail/boxes/password")
def mail_box_password(handler, body):
    okc, msg = mail_core.set_password(str(body.get("email") or ""),
                                      str(body.get("password") or ""))
    if not okc:
        return err(msg)
    return done(msg)


@post("/api/mail/boxes/remove")
def mail_box_remove(handler, body):
    okc, msg = mail_core.remove_mailbox(str(body.get("email") or ""))
    if not okc:
        return err(msg)
    return done(msg)


@post("/api/mail/boxes/test")
def mail_box_test(handler, body):
    okc, msg = mail_core.test_delivery(str(body.get("email") or ""))
    if not okc:
        return err(msg, 500)
    return done(msg)


# -------------------------------------------------- DNS-записи почты -------

def _dig_txt(name):
    from ..context import run as _run, have as _have
    if not _have("dig"):
        return []
    code, out, _ = _run(["dig", "+short", name, "TXT"], timeout=15)
    return ['"%s"' % x if not x.startswith('"') else x
            for x in (out or "").splitlines() if x.strip()]


@get("/api/mail/dns")
def mail_dns(handler, qs):
    """Готовые DNS-записи (SPF/DMARC/DKIM) + текущие значения домена."""
    domain = (qs.get("domain", [""])[0] or "").strip().lower()
    from ..context import run as _run
    code, out, _ = _run(["hostname", "-I"], timeout=10)
    server_ip = next((x for x in (out or "").split() if ":" not in x), "")
    spf = "v=spf1 a mx ip4:%s -all" % (server_ip or "СЕРВЕР_IP")
    dmarc = "v=DMARC1; p=quarantine; rua=mailto:postmaster@%s" % domain
    dkim_path = os.path.join(config.DEFAULT_HOME, "mail", "dkim",
                             "%s.default.key" % domain)
    dkim_txt = ""
    if os.path.exists(dkim_path + ".txt"):
        try:
            with open(dkim_path + ".txt", encoding="utf-8") as f:
                dkim_txt = f.read().strip().replace("\n", "")
        except OSError:
            pass
    if CTX.demo:
        return ok(demo=True, domain=domain, server_ip=server_ip,
                  records={
                      "spf": {"name": domain, "type": "TXT", "value": spf,
                              "current": ["\"v=spf1 a mx -all\""], "ok": True},
                      "dmarc": {"name": "_dmarc." + domain, "type": "TXT",
                                "value": dmarc, "current": [], "ok": False},
                      "dkim": {"name": "default._domainkey." + domain,
                               "type": "TXT",
                               "value": dkim_txt or "(сгенерируйте ключ)",
                               "current": [], "ok": False}},
                  dkim_generated=bool(dkim_txt))
    return ok(domain=domain, server_ip=server_ip,
              records={
                  "spf": {"name": domain, "type": "TXT", "value": spf,
                          "current": [t for t in _dig_txt(domain)
                                      if "v=spf1" in t],
                          "ok": any("v=spf1" in t for t in
                                    _dig_txt(domain))},
                  "dmarc": {"name": "_dmarc." + domain, "type": "TXT",
                            "value": dmarc,
                            "current": _dig_txt("_dmarc." + domain),
                            "ok": bool(_dig_txt("_dmarc." + domain))},
                  "dkim": {"name": "default._domainkey." + domain,
                           "type": "TXT",
                           "value": dkim_txt or "(сгенерируйте ключ)",
                           "current": _dig_txt("default._domainkey." +
                                               domain),
                           "ok": bool(dkim_txt) and
                           bool(_dig_txt("default._domainkey." + domain))}},
              dkim_generated=bool(dkim_txt))


@post("/api/mail/dkim/generate")
def mail_dkim_generate(handler, body):
    """Генерация DKIM-ключей: opendkim-genkey, при его отсутствии —
    openssl (RSA 1024 + вычисление публичной части для TXT)."""
    domain = (body.get("domain") or "").strip().lower()
    if not re.match(r"^[a-z0-9.\-]{3,255}$", domain) or ".." in domain \
            or not utils.valid_domain(domain):
        return err("некорректный домен")
    if CTX.demo:
        return done("демо: DKIM-ключ сгенерирован")
    d = os.path.join(config.DEFAULT_HOME, "mail", "dkim")
    os.makedirs(d, exist_ok=True)
    key = os.path.join(d, "%s.default.key" % domain)
    txt = os.path.join(d, "%s.default.txt" % domain)
    if have("opendkim-genkey"):
        code, _o, err = run(["opendkim-genkey", "-b", "1024", "-d", domain,
                             "-s", "default", "-D", d], timeout=60,
                            as_root=True)
        if code == 0 and os.path.exists(os.path.join(d, "default.private")):
            os.replace(os.path.join(d, "default.private"), key)
            os.replace(os.path.join(d, "default.txt"), txt)
    if not os.path.exists(key):
        # fallback: openssl
        code, _o, err = run(["openssl", "genrsa", "-out", key, "1024"],
                            timeout=60, as_root=True)
        if code != 0:
            return err("не удалось сгенерировать ключ: %s" % (err or "")[:150])
    if not os.path.exists(txt):
        code, pub, err = run(["/bin/sh", "-c",
                              "openssl rsa -in '%s' -pubout -outform DER "
                              "2>/dev/null | base64 -w0" % key],
                             timeout=30)
        if code != 0 or not (pub or "").strip():
            return err("не удалось вычислить публичную часть: %s"
                       % (err or "")[:150])
        value = "v=DKIM1; k=rsa; p=%s" % pub.strip()
        with open(txt, "w", encoding="utf-8") as f:
            f.write(value)
    return done("DKIM-ключ для %s сгенерирован — добавьте TXT-запись "
                "default._domainkey.%s у регистратора" % (domain, domain))
