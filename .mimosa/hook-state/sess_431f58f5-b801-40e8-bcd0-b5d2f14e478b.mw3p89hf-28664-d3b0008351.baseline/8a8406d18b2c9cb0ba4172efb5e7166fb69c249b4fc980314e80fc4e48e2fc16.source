# -*- coding: utf-8 -*-
"""Службы systemd, планировщик cron и брандмауэр ufw."""
import os
import re

from .. import config
from ..context import CTX, run, have
from .. import utils

SERVICE_LIST = ["nginx", "apache2", "mariadb", "mysql", "php8.3-fpm",
                "php8.2-fpm", "php8.1-fpm", "php8.0-fpm", "php7.4-fpm",
                "redis-server", "memcached", "fail2ban", "postfix",
                "dovecot", "cron", "certbot.timer"]

DEMO_SERVICE_STATES = {
    "nginx": "active", "apache2": "active", "mariadb": "active",
    "php8.2-fpm": "active", "php8.1-fpm": "active", "fail2ban": "active",
    "cron": "active", "php7.4-fpm": "inactive", "postfix": "inactive",
    "dovecot": "inactive", "redis-server": "active", "memcached": "inactive",
    "certbot.timer": "active",
}


def _human_uptime(sec):
    """Секунды -> «3 дн. 02:15» / «02:15:40»."""
    if sec <= 0:
        return "—"
    days, rem = divmod(int(sec), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return "%d дн. %02d:%02d" % (days, hours, minutes)
    return "%02d:%02d:%02d" % (hours, minutes, rem % 60)


def detect_services():
    """Список служб + состояние + как долго работает + когда перезапускалась.

    Время работы считаем по ActiveEnterTimestampMonotonic (микросекунды от
    загрузки) относительно /proc/uptime — не зависит от локали и часового
    пояса, в отличие от ActiveEnterTimestamp.
    """
    import datetime as dt
    result = []
    if CTX.demo:
        import random
        for name, state in DEMO_SERVICE_STATES.items():
            up = random.randint(3600, 600000)
            result.append({
                "name": name, "state": state, "exists": True,
                "uptime_sec": up, "uptime_h": _human_uptime(up),
                "since": (dt.datetime.now() -
                          dt.timedelta(seconds=up)).strftime("%Y-%m-%d %H:%M:%S")})
        return result
    try:
        with open("/proc/uptime") as f:
            sys_uptime = float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        sys_uptime = 0.0
    for name in SERVICE_LIST:
        code, out, _ = run(["systemctl", "show", name, "-p", "ActiveState",
                            "-p", "ActiveEnterTimestampMonotonic",
                            "-p", "LoadState"], timeout=10)
        state = ""
        mono = 0
        load = ""
        for line in out.splitlines():
            if line.startswith("ActiveState="):
                state = line.split("=", 1)[1].strip()
            elif line.startswith("ActiveEnterTimestampMonotonic="):
                try:
                    mono = int(line.split("=", 1)[1])
                except ValueError:
                    mono = 0
            elif line.startswith("LoadState="):
                load = line.split("=", 1)[1].strip()
        # not-found — systemctl show создаёт заглушку несуществующего юнита
        if load == "not-found" or (code == 4 and not state and not mono):
            continue  # юнит не существует — не показываем
        uptime_sec = 0
        since = ""
        if state == "active" and mono > 0 and sys_uptime > 0:
            uptime_sec = max(0, int(sys_uptime - mono / 1_000_000))
            since = (dt.datetime.now() -
                     dt.timedelta(seconds=uptime_sec)).strftime(
                         "%Y-%m-%d %H:%M:%S")
        result.append({"name": name, "state": state or "unknown",
                       "exists": True, "uptime_sec": uptime_sec,
                       "uptime_h": _human_uptime(uptime_sec), "since": since})
    return result


def restart(name):
    if not re.match(r"^[a-zA-Z0-9@._\-]+$", name or ""):
        return False, "некорректное имя службы"
    if CTX.demo:
        return True, "демо: служба %s перезапущена" % name
    code, out, err = run(["systemctl", "restart", name], timeout=60,
                         as_root=True)
    ok = code == 0
    if ok:
        CTX.store.notify("Служба %s перезапущена" % name)
    return ok, (err.strip() or out.strip() or ("готово" if ok else "ошибка"))


# ---------------------------------------------------------------- cron ---
CRON_BEGIN = "# --- HOSTPANEL BEGIN ---"
CRON_END = "# --- HOSTPANEL END ---"


def cron_read_system():
    if CTX.demo:
        return []
    code, out, _ = run(["crontab", "-l"], as_root=True)
    if code != 0:
        return []
    inside = False
    jobs = []
    wrap = os.path.join(CTX.home, "cronwrap.sh")
    for line in out.splitlines():
        if CRON_BEGIN in line:
            inside = True
            continue
        if CRON_END in line:
            inside = False
            continue
        if inside and line.strip() and not line.strip().startswith("#"):
            # строки-обёртки показываем в исходном виде «расписание команда»
            if "HP_CMD='" in line and wrap in line:
                head, _, rest = line.partition(" HP_CMD='")
                cmd, _, _ = rest.rpartition("' " + wrap)
                if cmd:
                    line = head + " " + cmd.replace("'\\''", "'")
            jobs.append(line)
    return jobs


def cron_log_slot(command):
    """Путь к журналу задачи с данной командой (или None)."""
    for slot, j in enumerate(_cron_system_jobs(CTX.store.data)):
        if j["command"] == command:
            return cron_log_path(slot)
    return None


CRON_WRAP = """#!/bin/sh
# HostPanel: обёртка cron-задачи — пишет журнал запуска в LOG.
# Команда приходит в переменной HP_CMD (панель экранирует её сама).
LOG="$1"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') запускаю: $HP_CMD"
  out=$(eval "$HP_CMD" 2>&1); code=$?
  [ -n "$out" ] && echo "$out" | tail -n 25
  echo "[код завершения: $code]"
} >> "$LOG" 2>&1
# ротация: держим последние 400 строк
if [ "$(wc -l < "$LOG")" -gt 500 ]; then
  tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
"""


def cron_log_path(slot):
    """Файл журнала для слота задачи (слоты нумеруются по порядку)."""
    return os.path.join(config.CRON_LOG_DIR, "%d.log" % slot)


def _cronwrap_ensure():
    """Создаёт/обновляет обёртку cronwrap.sh в домашней папке панели."""
    path = os.path.join(CTX.home, "cronwrap.sh")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(CRON_WRAP)
        os.chmod(path, 0o755)
        os.makedirs(config.CRON_LOG_DIR, exist_ok=True)
    except OSError:
        return ""
    return path


def _cron_system_jobs(st):
    """Итоговый список задач, попадающих в crontab: включённые +
    служебные панели (автобэкап, автопродление SSL). Порядок задаёт
    номера слотов журналов."""
    jobs = [j for j in st.get("cron", []) if j.get("enabled", True)]
    if st["settings"].get("auto_backup_enabled"):
        jobs.append({"expr": st["settings"].get("auto_backup_cron",
                                                "0 3 * * *"),
                     "command": "python3 -m panel --cron-backup",
                     "comment": "автобэкап"})
    if st["settings"].get("ssl_autorenew_enabled", True):
        jobs.append({"expr": st["settings"].get("ssl_renew_cron",
                                                "30 3,15 * * *"),
                     "command": "python3 -m panel --ssl-renew",
                     "comment": "автопродление SSL"})
    if st["settings"].get("weekly_report_enabled"):
        jobs.append({"expr": "0 9 * * 1",
                     "command": "python3 -m panel --weekly-report",
                     "comment": "еженедельный отчёт"})
    return jobs


def cron_read_log(command):
    """Журнал запусков задачи с данной командой (последние 60 строк)."""
    for slot, j in enumerate(_cron_system_jobs(CTX.store.data)):
        if j["command"] == command:
            path = cron_log_path(slot)
            try:
                with open(path, encoding="utf-8",
                          errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                return []
            return lines[-60:]
    return []


def cron_write_system(jobs):
    if CTX.demo:
        return
    wrap = _cronwrap_ensure()
    code, out, _ = run(["crontab", "-l"], as_root=True)
    current = out if code == 0 else ""
    lines, inside = [], False
    for line in current.splitlines():
        if CRON_BEGIN in line:
            inside = True
            continue
        if CRON_END in line:
            inside = False
            continue
        if not inside:
            lines.append(line)
    block = [CRON_BEGIN]
    for slot, j in enumerate(jobs):
        if not j.get("enabled", True):
            continue
        if wrap:
            # команду передаём через переменную окружения — кавычки
            # внутри команды не ломают строку crontab; % в crontab
            # означает перевод строки — экранируем как \%
            esc = j["command"].replace("'", "'\\''").replace("%", "\\%")
            block.append("%s HP_CMD='%s' %s %s"
                         % (j["expr"], esc, wrap,
                            cron_log_path(slot)))
        else:
            block.append("%s %s" % (j["expr"], j["command"]))
    block.append(CRON_END)
    lines += block
    code, _out, err = run(["crontab", "-"],
                          input_text="\n".join(lines) + "\n", as_root=True)
    if code != 0:
        CTX.store.notify("Не удалось записать crontab: %s"
                         % (err or "код %s" % code)[:150], "error")


VALID_CRON_EXPR = re.compile(
    r"^(\S+\s+){4}\S+$")

# (имя, минимум, максимум) полей crontab: мин час день месяц день_недели
_CRON_FIELD_RANGES = (
    ("минуты", 0, 59), ("часы", 0, 23), ("день месяца", 1, 31),
    ("месяц", 1, 12), ("день недели", 0, 7),
)


def valid_cron_expr(expr):
    """Проверяет выражение cron целиком: 5 полей, каждое — *, число,
    диапазон a-b, список через запятую, с опциональным шагом /n.
    Значения вне допустимых диапазонов (например, 99 минут) отвергаются:
    иначе crontab целиком отклоняется демоном cron."""
    if not VALID_CRON_EXPR.match(expr or ""):
        return False
    parts = expr.split()
    if len(parts) != 5:
        return False
    for field, (_name, lo, hi) in zip(parts, _CRON_FIELD_RANGES):
        if not re.match(r"^[0-9*/,\-]+$", field):
            return False
        for piece in field.split(","):
            if not piece:
                return False
            base, _sep, step = piece.partition("/")
            if "/" in piece and (not step.isdigit() or int(step) == 0):
                return False
            if base == "*":
                continue
            m = re.match(r"^(\d+)(?:-(\d+))?$", base)
            if not m:
                return False
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            if a < lo or b > hi or a > b:
                return False
    return True


# ----------------------------------------------------------- брандмауэр ---
def firewall_status():
    if CTX.demo:
        return {"active": True, "backend": "ufw (демо)",
                "rules": [
                    {"port": "22", "proto": "tcp", "action": "allow",
                     "from": "любой", "comment": "SSH"},
                    {"port": "80", "proto": "tcp", "action": "allow",
                     "from": "любой", "comment": "HTTP"},
                    {"port": "443", "proto": "tcp", "action": "allow",
                     "from": "любой", "comment": "HTTPS"},
                    {"port": "3306", "proto": "tcp", "action": "deny",
                     "from": "любой", "comment": "MySQL только локально"},
                ],
                "banned": ["45.155.205.11", "185.222.57.90"]}
    if have("ufw"):
        code, out, _ = run(["ufw", "status", "numbered"], as_root=True)
        rules = []
        active = out.startswith("Status: active")
        for line in out.splitlines()[3:]:
            # формат: "[ 1] 22/tcp  ALLOW IN  Anywhere (v6)"
            m = re.match(r"\[\s*\d+\]\s+(\S+)\s+(ALLOW|DENY|REJECT|LIMIT)"
                         r"(?:\s+\S+)?\s+(.*)", line)
            if m:
                frm = m.group(3).strip()
                comment = ""
                mc = re.search(r"\(comment '([^']*)'\)", frm)
                if mc:
                    comment = mc.group(1)
                    frm = frm.replace(mc.group(0), "").strip()
                # человекочитаемый источник вместо ufw-жаргона
                if frm in ("Anywhere", "Anywhere (v6)"):
                    frm = "из любой сети"
                elif "(v6)" in frm:
                    frm = frm.replace("(v6)", "").strip() + " (IPv6)"
                rules.append({"port": m.group(1).split("/")[0],
                              "proto": (m.group(1).split("/") + ["tcp"])[1],
                              "action": m.group(2).lower(),
                              "from": frm, "comment": comment})
        return {"active": active, "backend": "ufw", "rules": rules,
                "banned": []}
    return {"active": False, "backend": "не найден (ufw не установлен)",
            "rules": [], "banned": []}


def firewall_add(port, action="allow", proto="tcp", comment=""):
    import re
    if not re.match(r"^\d{1,5}(/\d{1,5})?(:\d{1,5})?$", str(port)):
        return False, "некорректный порт"
    if action not in ("allow", "deny"):
        return False, "некорректное действие"
    if not (1 <= int(str(port).split("/")[0].split(":")[0]) <= 65535):
        return False, "порт вне диапазона 1–65535"
    if CTX.demo:
        return True, "демо: правило добавлено"
    if not have("ufw"):
        return False, "ufw не установлен"
    # proto может быть пустым ('both') — тогда не указываем его вовсе
    cmd = ["ufw", action]
    if proto:
        cmd += ["proto", proto]
    cmd += ["to", "any", "port", str(port).split("/")[0]]
    # ufw поддерживает комментарий к правилу (виден в status numbered)
    bad = chr(39) + chr(34) + chr(13) + chr(10)
    comment = str(comment or '')
    for ch in bad:
        comment = comment.replace(ch, '')
    comment = comment.strip()[:100]
    if comment:
        cmd += ["comment", comment]
    code, _, err = run(cmd, as_root=True)
    return code == 0, err


def journal(name, lines=200):
    """Последние строки journalctl службы — просмотр логов из панели."""
    if not re.match(r"^[a-zA-Z0-9@._\-]+$", name or ""):
        return None, "некорректное имя службы"
    try:
        n = max(10, min(int(lines or 200), 1000))
    except (TypeError, ValueError):
        n = 200
    code, out, err = run(["journalctl", "-u", name, "-n", str(n),
                          "--no-pager", "-o", "short-iso"], timeout=30)
    if code != 0 and not out:
        return None, (err or "журнал недоступен").strip()
    return (out or "").splitlines(), ""
