# -*- coding: utf-8 -*-
"""Контекст выполнения: режим (демо/рабочий), папки, хранилище, запуск команд.

Все модули панели обращаются к глобальному состоянию через этот модуль,
а не через import-ы друг друга — так нет циклических зависимостей.
"""
import os
import shutil
import subprocess
import threading

from . import config

# Общая блокировка состояния: под ней работают все HTTP-обработчики
# (server.py) и фоновые мутирующие участки (health, фоновые задачи) —
# иначе json.dump в save() может увидеть мутируемый dict.
STATE_LOCK = threading.RLock()


class Ctx:
    """Изменяемое состояние процесса (заполняется при старте)."""

    def __init__(self):
        self.demo = True
        self.home = ""
        self.www_root = config.WWW_ROOT
        self.store = None

    @property
    def is_root(self):
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False


CTX = Ctx()


def set_context(demo, home, store):
    CTX.demo = bool(demo)
    CTX.home = home
    CTX.store = store


def run(cmd, timeout=60, input_text=None, as_root=False, cwd=None, env=None):
    """Запуск внешней команды списком аргументов (без shell — защита
    от инъекций). Возвращает (код, stdout, stderr). В демо-режиме
    команды не выполняются. env — дополнительные переменные окружения
    (PATH и пр. наследуются от панели)."""
    if CTX.demo:
        return 0, "", ""
    if as_root and not CTX.is_root:
        cmd = ["sudo", "-n"] + list(cmd)
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update(env)
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True,
                           timeout=timeout, input=input_text, cwd=cwd,
                           env=full_env)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except FileNotFoundError:
        return 127, "", "не найдено: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "", "превышено время выполнения команды"
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def have(binname):
    """Установлен ли бинарник (в демо-режиме — нет)."""
    if CTX.demo:
        return False
    return shutil.which(binname) is not None


def site_docroot_abs(site):
    """Абсолютный путь к docroot сайта."""
    p = site["docroot"]
    if os.path.isabs(p):
        return p
    return os.path.join(CTX.home, p)


def fm_allowed(path):
    """Разрешён ли путь файловому менеджеру (защита от выхода за корни)."""
    real = os.path.realpath(path)
    if CTX.demo:
        roots = config.fm_roots_demo(os.path.realpath(CTX.home))
    elif CTX.store and CTX.store.data["settings"].get("fm_restricted", True):
        roots = [os.path.realpath(r) for r in config.fm_roots(CTX.home)]
    else:
        return real.startswith("/")
    for root in roots:
        if real == root or real.startswith(root + os.sep):
            return True
    return False
