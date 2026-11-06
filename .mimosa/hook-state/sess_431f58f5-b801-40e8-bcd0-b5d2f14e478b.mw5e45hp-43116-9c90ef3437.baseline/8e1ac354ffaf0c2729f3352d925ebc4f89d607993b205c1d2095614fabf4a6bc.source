# -*- coding: utf-8 -*-
"""Уведомления администратору: e-mail (SMTP) и Telegram.

Отправка никогда не бросает исключений наружу: любой сбой канала
логируется и возвращается текстом ошибки (панель продолжает работу).
"""
import json
import smtplib
import threading
import urllib.request
from email.message import EmailMessage

from ..context import CTX
from .. import config, utils


def _capped(fn, seconds):
    """Жёсткий лимит времени на канал: DNS/TCP могут висеть дольше,
    чем socket-timeout — гасим поток по таймауту."""
    result = ["истекло время ожидания (%d сек)" % seconds]

    def target():
        try:
            result[0] = fn()
        except Exception as e:  # noqa: BLE001
            result[0] = str(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    return result[0]


def _cfg():
    return (CTX.store.data["settings"].get("notify")
            or {"email": {}, "tg": {}})


def configured():
    """Включён ли хотя бы один канал."""
    c = _cfg()
    return bool(c.get("email", {}).get("enabled")) or \
        bool(c.get("tg", {}).get("enabled"))


def send(subject, text):
    """Отправка во все включённые каналы. Возвращает список ошибок."""
    errors = []
    c = _cfg()
    if c.get("email", {}).get("enabled"):
        e = _capped(lambda: _send_email(c["email"], subject, text),
                    config.NOTIFY_TIMEOUT + 5)
        if e:
            errors.append("e-mail: %s" % e)
    if c.get("tg", {}).get("enabled"):
        e = _capped(lambda: _send_tg(c["tg"], "%s\n\n%s" % (subject, text)),
                    config.NOTIFY_TIMEOUT + 5)
        if e:
            errors.append("telegram: %s" % e)
    for e in errors:
        utils.log("Уведомление не ушло — %s" % e)
    return errors


def _send_email(cfg, subject, text):
    host = (cfg.get("host") or "").strip()
    to = (cfg.get("to") or "").strip()
    if not host or not to:
        return "не заданы SMTP-сервер или получатель"
    try:
        port = int(cfg.get("port") or 587)
    except (TypeError, ValueError):
        port = 587
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (cfg.get("from") or cfg.get("user") or "hostpanel@localhost")
    msg["To"] = to
    msg.set_content(text)
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port,
                                    timeout=config.NOTIFY_TIMEOUT)
        else:
            smtp = smtplib.SMTP(host, port, timeout=config.NOTIFY_TIMEOUT)
        try:
            if port != 25:
                smtp.starttls()
            if cfg.get("user"):
                smtp.login(cfg["user"], cfg.get("pass") or "")
            smtp.send_message(msg)
        finally:
            smtp.quit()
    except Exception as e:  # noqa: BLE001 — любой сбой доставки
        return str(e)
    return ""


def _send_tg(cfg, text):
    token = (cfg.get("token") or "").strip()
    chat = (cfg.get("chat") or "").strip()
    if not token or not chat:
        return "не заданы токен бота или chat id"
    try:
        req = urllib.request.Request(
            "https://api.telegram.org/bot%s/sendMessage" % token,
            data=json.dumps({"chat_id": chat, "text": text[:4000]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=config.NOTIFY_TIMEOUT) as r:
            resp = json.loads(r.read().decode() or "{}")
        if not resp.get("ok"):
            return resp.get("description") or "Telegram отклонил запрос"
    except Exception as e:  # noqa: BLE001
        return str(e)
    return ""
