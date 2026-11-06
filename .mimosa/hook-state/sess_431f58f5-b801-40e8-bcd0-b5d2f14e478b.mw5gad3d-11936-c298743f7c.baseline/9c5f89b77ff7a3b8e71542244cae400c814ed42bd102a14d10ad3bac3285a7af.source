# -*- coding: utf-8 -*-
"""API: пакеты, PHP-модули, обновления, Node.js, службы, конфиги PHP,
каталог ПО (установка служб из панели), приложения (phpMyAdmin)."""
from .. import config
from ..context import CTX
from ..core import packages, services, confeditor, nodejs, software, ioncube
from ..core import pma as pma_mod
from .router import get, post, ok, err, done


@get("/api/apps")
def apps_status(handler, qs):
    """Приложения (phpMyAdmin): где установлено, защита, доступы."""
    return ok(apps=pma_mod.status(),
              running=packages.task_status()["running"])


@post("/api/apps/install")
def apps_install(handler, body):
    """Установка приложения в выбранный сайт (в фоне)."""
    if body.get("app") != "pma":
        return err("неизвестное приложение")
    domain = str(body.get("site") or "")
    if not any(s["domain"] == domain for s in CTX.store.data["sites"]):
        return err("сайт не найден")
    okc, errs = pma_mod.install(domain, bool(body.get("protect", True)),
                                str(body.get("password") or ""))
    if not okc:
        return err(errs)
    return done("установка phpMyAdmin запущена — прогресс: Система → "
                "Пакеты и обновления (и уведомления в колокольчике)")


@post("/api/apps/remove")
def apps_remove(handler, body):
    """Удаление приложения из сайта."""
    if body.get("app") != "pma":
        return err("неизвестное приложение")
    domain = str(body.get("site") or "")
    okc, errs = pma_mod.remove(domain)
    if not okc:
        return err(errs)
    return done("удаление phpMyAdmin запущено")


@get("/api/ioncube/status")
def ioncube_status(handler, qs):
    """ionCube Loader: состояние для каждой установленной версии PHP."""
    return ok(**ioncube.status())


@post("/api/ioncube/install")
def ioncube_install(handler, body):
    version = str(body.get("version") or "")
    okc, errs = ioncube.install(version)
    if not okc:
        return err(errs)
    return done("установка/обновление ionCube для PHP %s запущена — "
                "прогресс: Система → Пакеты и обновления" % version)


@post("/api/ioncube/remove")
def ioncube_remove(handler, body):
    version = str(body.get("version") or "")
    okc, errs = ioncube.remove(version)
    if not okc:
        return err(errs)
    return done("удаление ionCube для PHP %s запущено" % version)


@get("/api/software")
def software_catalog(handler, qs):
    """Каталог ПО со статусами (в духе ISPmanager)."""
    return ok(catalog=software.catalog(),
              running=packages.task_status()["running"])


@post("/api/software/install")
def software_install(handler, body):
    name = str(body.get("name") or "")
    if not software.valid_id(name):
        return err("некорректный идентификатор")
    okc, errs = software.install(name)
    if not okc:
        return err(errs)
    return done("установка «%s» запущена — прогресс: Система → Пакеты и "
                "обновления" % software.CATALOG_BY_ID[name]["name"])


@post("/api/software/remove")
def software_remove(handler, body):
    name = str(body.get("name") or "")
    if not software.valid_id(name):
        return err("некорректный идентификатор")
    okc, errs = software.remove(name)
    if not okc:
        return err(errs)
    return done("удаление «%s» запущено"
                % software.CATALOG_BY_ID[name]["name"])


@get("/api/php")
def php_info(handler, qs):
    return ok(versions=packages.php_versions(),
              module_names=config.PHP_MODULE_RU,
              apt_available=packages.apt_available())


@get("/api/php/modules")
def php_modules(handler, qs):
    """Модули, доступные для установки через apt, для версии PHP."""
    version = qs.get("version", [""])[0]
    import re
    if not re.match(r"^\d+\.\d+$", version or ""):
        return err("укажите версию PHP, например 8.2")
    installed = packages.php_versions().get(version, [])
    available = packages.php_module_packages(version)
    return ok(version=version, installed=installed,
              available=available,
              apt_available=packages.apt_available())


@post("/api/php/install_module")
def php_install_module(handler, body):
    version = str(body.get("version") or "")
    module = str(body.get("module") or "")
    okc, errs = packages.install_php_module(version, module)
    if not okc:
        return err(errs)
    return done("установка модуля php%s-%s запущена — прогресс: Система → "
                "Пакеты и обновления" % (version, module))


@get("/api/services/logs")
def service_logs(handler, qs):
    """Просмотр журнала systemd-службы прямо в панели."""
    name = qs.get("name", [""])[0]
    lines = qs.get("lines", ["200"])[0]
    data, errs = services.journal(name, lines)
    if data is None:
        return err(errs, 400)
    return ok(lines=data)


@post("/api/exec")
def exec_cmd(handler, body):
    """Веб-терминал: выполнение команды от root (замена SSH-клиенту)."""
    import os
    if CTX.demo:
        return err("в демо-режиме командная строка недоступна")
    cmd = str(body.get("cmd") or "").strip()
    cwd = str(body.get("cwd") or "/root").strip() or "/root"
    if not cmd:
        return err("пустая команда")
    if len(cmd) > 4000:
        return err("команда слишком длинная (>4 КБ)")
    if not os.path.isdir(cwd):
        cwd = "/root"
    from ..context import run
    code, out, errs = run(["bash", "-lc", cmd], timeout=90, cwd=cwd)
    text = out or ""
    if errs:
        text += ("\n" + errs) if text else errs
    return ok(code=code, output=text[:200_000], cwd=cwd)


@post("/api/system/reboot")
def system_reboot(handler, body):
    """Перезагрузка всего сервера из панели (с подтверждением)."""
    if CTX.demo:
        return err("в демо-режиме недоступно")
    if str(body.get("confirm") or "") != "reboot":
        return err("подтвердите действие: confirm=reboot")
    import threading
    from ..context import run
    CTX.store.log_action("Перезагрузка сервера запущена из панели")
    CTX.store.notify("Сервер перезагружается…", "warn")

    def delayed():
        import time as _t
        _t.sleep(1.5)
        run(["systemctl", "reboot"], as_root=True, timeout=15)

    threading.Thread(target=delayed, daemon=True).start()
    return done("перезагрузка запущена — панель будет доступна через 1–2 минуты")


@get("/api/nodejs")
def nodejs_info(handler, qs):
    import glob
    if CTX.demo:
        return ok(installed=True, versions=config.DEMO_NODE, default="20")
    from ..context import run, have
    code, out, _ = run(["node", "-v"])
    default = out.strip().lstrip("v") if code == 0 else ""
    versions = set()
    if default:
        versions.add(default.split(".")[0])
    for d in sorted(glob.glob("/usr/local/n/versions/node/*")) + \
            sorted(glob.glob("/opt/node*/bin")):
        name = d.rstrip("/").split("/")[-1]
        if name.replace(".", "").isdigit() or name.isdigit():
            versions.add(name.split(".")[0])
    return ok(installed=bool(default or versions),
              versions=sorted(versions),
              default=default.split(".")[0] if default else "")


@get("/api/services")
def services_list(handler, qs):
    return ok(services=services.detect_services())


@post("/api/services/restart")
def service_restart(handler, body):
    import re
    name = str(body.get("name") or "")
    if not re.match(r"^[a-zA-Z0-9@._\-]+$", name):
        return err("некорректное имя службы")
    okc, msg = services.restart(name)
    if okc:
        return done("служба %s перезапущена" % name)
    return err(msg, 500)


@get("/api/packages")
def packages_status(handler, qs):
    store = CTX.store.data
    return ok(upgradable=packages.upgradable(),
              apt_available=packages.apt_available(),
              apt_updated=store.get("packages", {}).get("apt_updated", ""))


@get("/api/packages/task")
def packages_task(handler, qs):
    return ok(**packages.task_status())


@post("/api/packages/update_index")
def packages_update_index(handler, body):
    okc, errs = packages.apt_update()
    if not okc:
        return err(errs)
    return done("обновление индексов apt запущено")


@post("/api/packages/upgrade")
def packages_upgrade(handler, body):
    okc, errs = packages.upgrade_packages(body.get("names") or
                                          body.get("packages") or [])
    if not okc:
        return err(errs)
    return done("обновление пакетов запущено")


@get("/api/conf/php_ini")
def php_ini_read(handler, qs):
    version = qs.get("version", [""])[0]
    import re
    if not re.match(r"^\d+\.\d+$", version or ""):
        return err("укажите версию PHP")
    path = confeditor.php_ini_path(version)
    from ..core import files as files_mod
    text, e = files_mod.read(path)
    if e:
        return err(e, 400)
    return ok(path=path, content=text, rules=_ini_rules_ru())


def _ini_rules_ru():
    return {k: {"desc": v[2], "kind": v[0]}
            for k, v in confeditor.PHP_INI_RULES.items()}


@post("/api/conf/php_ini")
def php_ini_save(handler, body):
    version = str(body.get("version") or "")
    content = body.get("content", "")
    import re
    if not re.match(r"^\d+\.\d+$", version):
        return err("укажите версию PHP")
    if len(content) > 1_000_000:
        return err("файл слишком большой")
    path = confeditor.php_ini_path(version)
    okc, errs = confeditor.save_php_ini(path, content)
    if not okc:
        return err("не сохранено: %s" % errs, 400)
    return done("php.ini для PHP %s сохранён и проверен" % version)
