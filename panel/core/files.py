# -*- coding: utf-8 -*-
"""Файловый менеджер: операции над файлами с проверкой допустимости путей."""
import datetime as dt
import mimetypes
import os
try:
    import pwd            # Linux: имена владельцев файлов
except ImportError:       # демо на другой ОС — владелец остаётся числом
    pwd = None
import shutil
import stat as statmod
import tarfile
import zipfile

from .. import config
from .. import utils
from ..context import CTX, fm_allowed

TEXT_EXT = (".txt", ".log", ".conf", ".json", ".yaml", ".yml", ".xml",
            ".html", ".htm", ".css", ".js", ".php", ".py", ".sh", ".sql",
            ".ini", ".env", ".htaccess", ".md", ".csv", ".toml", ".service",
            ".cnf")


def _entry_stat(full, name):
    st = os.lstat(full)
    is_dir = statmod.S_ISDIR(st.st_mode)
    is_link = statmod.S_ISLNK(st.st_mode)
    target = ""
    if is_link:
        try:
            target = os.readlink(full)
        except OSError:
            target = "?"
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name if pwd else str(st.st_uid)
    except KeyError:
        owner = str(st.st_uid)
    ext = os.path.splitext(name)[1].lower()
    editable = (not is_dir and st.st_size <= config.EDITOR_MAX_FILE and
                (ext in TEXT_EXT or ext == "" or ext == "." + name.lstrip(".")))
    return {"name": name + ("/" if is_dir else ""),
            "type": "dir" if is_dir else "link" if is_link else "file",
            "size": 0 if is_dir else st.st_size,
            "mtime": dt.datetime.fromtimestamp(st.st_mtime).strftime(
                "%Y-%m-%d %H:%M"),
            "perms": statmod.filemode(st.st_mode),
            "octal": format(statmod.S_IMODE(st.st_mode), "o").zfill(3),
            "owner": owner, "target": target, "editable": bool(editable)}


def list_dir(path):
    full = os.path.realpath(path)
    if not os.path.exists(full):
        return None, "путь не найден"
    if not os.path.isdir(full):
        return None, "это не папка"
    items = []
    try:
        for name in os.listdir(full):
            if name in (".", ".."):
                continue
            try:
                items.append(_entry_stat(os.path.join(full, name), name))
            except OSError:
                continue
    except PermissionError:
        return None, "отказано в доступе"
    items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
    parent = os.path.dirname(full) if full != "/" else ""
    return {"path": full, "parent": parent, "items": items}, ""


def mkdir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True, ""
    except OSError as e:
        return False, str(e)


def save(path, content):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True, ""
    except OSError as e:
        return False, str(e)


def read(path):
    try:
        if os.path.getsize(path) > config.EDITOR_MAX_FILE:
            return None, "файл слишком большой для редактора (>1,5 МБ)"
        text = utils.read_text_file(path)
        if text is None:
            return None, "двоичный файл — предпросмотр недоступен"
        return text, ""
    except OSError as e:
        return None, str(e)


def delete(path):
    full = os.path.realpath(path)
    # запрещаем удалять корень ФС (на любой ОС: "/", "C:\")
    drive, tail = os.path.splitdrive(full)
    if tail in ("", "/", "\\"):
        return False, "нельзя удалить корень"
    try:
        if os.path.isdir(full) and not os.path.islink(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return True, ""
    except OSError as e:
        return False, str(e)


def rename(src, new_name):
    new_name = os.path.basename(new_name.replace("/", "").replace("\\", ""))
    if not new_name or new_name in (".", ".."):
        return False, "некорректное имя"
    try:
        dst = os.path.join(os.path.dirname(os.path.realpath(src)), new_name)
        os.rename(src, dst)
        return True, os.path.basename(dst)
    except OSError as e:
        return False, str(e)


def chmod(path, octal):
    try:
        os.chmod(path, int(octal, 8))
        return True, ""
    except (OSError, ValueError) as e:
        return False, str(e)


def download_info(path):
    full = os.path.realpath(path)
    if not os.path.isfile(full):
        return None
    mime = mimetypes.guess_type(full)[0] or "application/octet-stream"
    return {"path": full, "size": os.path.getsize(full), "mime": mime,
            "name": os.path.basename(full)}


def move(src, dest_dir):
    """Перемещение файла/папки в другую папку (drag&drop проводника)."""
    base = os.path.basename(src.rstrip("/"))
    dest = os.path.join(dest_dir, base)
    real_src = os.path.realpath(src)
    real_dest = os.path.realpath(dest_dir)
    # нельзя перемещать папку внутрь самой себя или своего потомка
    if real_dest == real_src or real_dest.startswith(real_src + os.sep):
        return False, "нельзя переместить папку внутрь самой себя"
    if os.path.exists(dest):
        return False, "в папке уже есть объект с именем " + base
    try:
        shutil.move(src, dest)
        return True, dest
    except OSError as e:
        return False, str(e)


def copy(src, dest_dir):
    """Копирование файла/папки в другую папку."""
    base = os.path.basename(src.rstrip("/"))
    dest = os.path.join(dest_dir, base)
    real_dest = os.path.realpath(dest_dir)
    if os.path.realpath(src).startswith(real_dest + os.sep) and             os.path.isdir(src):
        return False, "нельзя копировать папку внутрь самой себя"
    if os.path.exists(dest):
        return False, "в папке уже есть объект с именем " + base
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        return True, dest
    except OSError as e:
        return False, str(e)


def extract(path):
    """Распаковка zip/tar.gz/tgz/tar рядом с архивом (с защитой от zip-slip)."""
    full = os.path.realpath(path)
    d = os.path.dirname(full)
    base = os.path.splitext(os.path.basename(full))[0]
    if base.endswith(".tar"):
        base = base[:-4]
    dest = os.path.join(d, base)
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(d, "%s-%d" % (base, n))
        n += 1
    try:
        os.makedirs(dest)
        if zipfile.is_zipfile(full):
            with zipfile.ZipFile(full) as z:
                for member in z.infolist():
                    target = os.path.realpath(
                        os.path.join(dest, member.filename))
                    if not (target == dest or
                            target.startswith(dest + os.sep)):
                        raise ValueError("небезопасное имя в архиве: %s"
                                         % member.filename)
                    if statmod.S_ISLNK((member.external_attr >> 16)
                                       & 0o170000):
                        raise ValueError("симлинк в архиве: %s"
                                         % member.filename)
                z.extractall(dest)
        else:
            with tarfile.open(full, "r:*") as t:
                members = [m for m in t.getmembers()
                           if not os.path.isabs(m.name) and
                           ".." not in m.name]
                try:
                    # filter="data" режет симлинки/ devices/ absolute-пути
                    t.extractall(dest, members=members, filter="data")
                except TypeError:  # Python < 3.12 без параметра filter
                    t.extractall(dest, members=members)
        return True, dest
    except (OSError, ValueError, tarfile.TarError,
            zipfile.BadZipFile) as e:
        shutil.rmtree(dest, ignore_errors=True)
        return False, str(e)


def zip_paths(paths, dest):
    try:
        if dest.lower().endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(
                    dest, "w:gz" if not dest.endswith(".tar") else "w") as t:
                for p in paths:
                    t.add(p, arcname=os.path.basename(p))
        else:
            if not dest.lower().endswith(".zip"):
                dest += ".zip"
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
                for p in paths:
                    if os.path.isdir(p):
                        for root, _dirs, files in os.walk(p):
                            for fn in files:
                                fp = os.path.join(root, fn)
                                z.write(fp, os.path.relpath(
                                    fp, os.path.dirname(p)))
                    else:
                        z.write(p, os.path.basename(p))
        return True, dest
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as e:
        return False, str(e)


def upload(dest_dir, filename, data):
    """Сохраняет загруженный файл. Имя очищается, путь проверяется."""
    fname = os.path.basename(filename.replace("\\", "/"))
    if not fname or fname in (".", ".."):
        return False, "некорректное имя файла"
    dest = os.path.join(dest_dir, fname)
    if not fm_allowed(dest):
        return False, "путь недоступен"
    try:
        with open(dest, "wb") as f:
            f.write(data)
        return True, fname
    except OSError as e:
        return False, str(e)
