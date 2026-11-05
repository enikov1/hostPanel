# -*- coding: utf-8 -*-
"""Точка входа: python3 -m panel [--demo] [--port N] [--home DIR].

Запуск от root — рабочий режим (Debian/Ubuntu). Без root автоматически
включается безопасный демо-режим. Также поддерживается служебный вызов
--cron-backup для автобэкапа по расписанию.
"""
import argparse
import os
import sys

from . import config, utils
from .context import CTX, set_context
from .state import Store


def main():
    ap = argparse.ArgumentParser(
        prog="python3 -m panel",
        description="HostPanel — панель управления хостингом")
    ap.add_argument("--port", type=int, default=None,
                    help="порт панели (по умолчанию 8080)")
    ap.add_argument("--demo", action="store_true",
                    help="демо-режим: без root, конфиги сервера "
                         "не изменяются")
    ap.add_argument("--home", default=None,
                    help="домашняя папка панели (по умолчанию /opt/hostpanel)")
    ap.add_argument("--cron-backup", action="store_true",
                    help="служебный режим для cron: сделать бэкап и выйти")
    ap.add_argument("--ssl-renew", action="store_true",
                    help="служебный режим для cron: продлить SSL-сертификаты "
                         "и проверить сроки")
    ap.add_argument("--weekly-report", action="store_true",
                    help="служебный режим для cron: еженедельный отчёт "
                         "администратору (e-mail/Telegram)")
    args = ap.parse_args()

    if args.ssl_renew:
        home = args.home or config.DEFAULT_HOME
        # flock на весь цикл «прочитал state — изменил — записал»:
        # без него cron-процесс затирает изменения работающей панели
        from .state import _Flock
        with _Flock(home):
            set_context(False, home, Store(home, demo=False))
            from .core import ssl as ssl_mod
            try:
                ssl_mod.renew_all()
            except Exception as e:  # noqa: BLE001
                utils.log("Проверка SSL провалилась: %s" % e)
                raise SystemExit(1)
            utils.log("Проверка/продление SSL-сертификатов завершено")
        return

    if args.weekly_report:
        home = args.home or config.DEFAULT_HOME
        from .state import _Flock
        with _Flock(home):
            set_context(False, home, Store(home, demo=False))
            from .core.report import weekly_report
            try:
                weekly_report()
            except Exception as e:  # noqa: BLE001
                utils.log("Еженедельный отчёт провалился: %s" % e)
                raise SystemExit(1)
            utils.log("Еженедельный отчёт отправлен")
        return

    if args.cron_backup:
        home = args.home or config.DEFAULT_HOME
        from .state import _Flock
        with _Flock(home):
            set_context(False, home, Store(home, demo=False))
            from .core import backup
            try:
                meta = backup.create(None, True)
            except Exception as e:  # noqa: BLE001 — сообщаем и выходим
                utils.log("Автобэкап провалился: %s" % e)
                _notify_backup(None, str(e))
                raise SystemExit(1)
            utils.log("Автобэкап завершён: %s (%s)"
                      % (meta["file"], utils.human_size(meta["size"])))
            _notify_backup(meta, "")
        return

    demo = args.demo or not CTX.is_root
    if demo and not args.demo:
        utils.log("Запуск без root: включён демо-режим. Для управления "
                  "сервером: sudo python3 -m panel")
    if demo and not args.home:
        home = os.path.join(os.getcwd(), "hostpanel-data")
    else:
        home = args.home or config.DEFAULT_HOME
    store = Store(home, demo)
    set_context(demo, home, store)

    from .server import Handler
    from http.server import ThreadingHTTPServer
    from .api import router as _router
    utils.log("маршруты: GET=%d POST=%d"
              % (len(_router.ROUTES_GET), len(_router.ROUTES_POST)))

    port = args.port or int(store.data["settings"].get("panel_port", 8080)
                            or 8080)
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        server.daemon_threads = True
    except OSError as e:
        utils.log("Не удалось занять порт %d: %s" % (port, e))
        sys.exit(1)

    # фоновые проверки живучести (в демо тоже работают — показывают графики)
    from .core.health import HealthThread
    health_thread = HealthThread()
    health_thread.start()

    pw_file = os.path.join(home, "admin.txt")
    print("=" * 62, flush=True)
    print("  HostPanel %s — панель управления хостингом" % config.VERSION)
    print("  Адрес:      http://0.0.0.0:%d  (локально: http://127.0.0.1:%d)"
          % (port, port))
    print("  Логин:      admin")
    print("  Пароль:     см. %s%s" % (pw_file, " (демо)" if demo else ""))
    print("  Режим:      %s" % ("ДЕМО — конфиги сервера не изменяются"
                               if demo else "РАБОЧИЙ — управление сервером"))
    print("=" * 62, flush=True)
    store.log_action("Панель запущена (порт %d, %s)"
                     % (port, "демо" if demo else "рабочий режим"))
    store.save()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        utils.log("Остановка панели")
    finally:
        health_thread.stop()


def _notify_backup(meta, error):
    """Результат автобэкапа — во внешние каналы (e-mail/Telegram)."""
    try:
        from .core import notify
        if not notify.configured():
            return
        if error:
            notify.send_event("backup", "HostPanel: автобэкап провалился",
                        "Резервная копия не создалась:\n%s" % error)
        else:
            notify.send_event("backup", "HostPanel: автобэкап готов",
                        "Файл: %s\nРазмер: %s"
                        % (meta["file"], utils.human_size(meta["size"])))
    except Exception as e:  # noqa: BLE001
        utils.log("Notify backup: %s" % e)


if __name__ == "__main__":
    main()
