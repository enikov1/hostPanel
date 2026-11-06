# -*- coding: utf-8 -*-
"""Еженедельный отчёт администратору: аптайм, диск, обновления, безопасность.

Всё собирается из уже накопленных данных (state, apt, fail2ban) —
никаких тяжёлых проверок. Отправка через notify (e-mail/Telegram,
включённые каналы). Вызывается из cron: python3 -m panel --weekly-report.
"""
import datetime as dt

from ..context import CTX, run, have
from .. import utils


def _disk_line():
    try:
        st = __import__("os").statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        pct = round((total - free) * 100.0 / total, 1) if total else 0
        return "Диск: занято %s из %s (%s%%)" % (
            utils.human_size(total - free), utils.human_size(total), pct)
    except OSError:
        return "Диск: неизвестно"


def _sites_lines():
    lines = []
    worst = 100.0
    for site in CTX.store.data.get("sites", []):
        from . import health
        up = health.uptime_pct(site["domain"], 24 * 7)
        state = "работает" if site.get("enabled") else "отключён"
        if up is None:
            lines.append("  • %s — %s (проверок ещё нет)"
                         % (site["domain"], state))
            continue
        worst = min(worst, up) if site.get("enabled") else worst
        lines.append("  • %s — %s, доступность за 7 дней: %s%%"
                     % (site["domain"], state, up))
    if lines:
        lines.insert(0, "Сайты (%d):" % len(lines))
        if worst < 99.0:
            lines.insert(1, "  ⚠ худшая доступность за неделю: %s%%"
                         % worst)
    return lines


def _updates_line():
    from . import packages
    up = packages.upgradable()
    return ("Обновления пакетов: доступно %d (посмотрите в разделе "
            "«Пакеты и обновления»)" % len(up)) if up else \
        "Обновления пакетов: всё актуально"


def _security_lines():
    lines = []
    if have("fail2ban-client"):
        code, out, _ = run(["fail2ban-client", "status", "hostpanel"],
                           timeout=10, as_root=True)
        banned = 0
        for ln in (out or "").splitlines():
            if "Banned IP" in ln or "забан" in ln.lower():
                ips = ln.split(":", 1)[-1].strip()
                banned = len([x for x in ips.split() if x])
        lines.append("Fail2ban (панель): заблокировано сейчас: %d" % banned)
    fails = [e for e in CTX.store.data.get("panel_log", [])
             if "Неудачный вход" in e.get("text", "")
             and e.get("ts", "") >= (dt.datetime.now() -
                                     dt.timedelta(days=7)).strftime(
                                         "%Y-%m-%d %H:%M:%S")]
    lines.append("Неудачных попыток входа в панель за 7 дней: %d"
                 % len(fails))
    return lines


def build_text():
    st = CTX.store.data
    parts = ["HostPanel — отчёт за неделю (%s)"
             % dt.date.today().strftime("%d.%m.%Y"), ""]
    parts += _sites_lines() or ["Сайтов пока нет."]
    parts.append(_disk_line())
    parts.append(_updates_line())
    sec = _security_lines()
    if sec:
        parts.append("Безопасность:")
        parts += ["  • " + x for x in sec]
    parts.append("")
    parts.append("Резервных копий: %d (последняя: %s)" % (
        len(st.get("backups", [])),
        (st.get("backups") or [{}])[0].get("created", "нет")))
    return "\n".join(parts)


def weekly_report():
    """Собирает и отправляет отчёт во включённые каналы."""
    text = build_text()
    utils.log("Еженедельный отчёт:\n%s" % text)
    from . import notify
    errors = notify.send("HostPanel: еженедельный отчёт", text)
    if errors:
        utils.log("Отчёт не ушёл: %s" % "; ".join(errors))
        return False
    return True
