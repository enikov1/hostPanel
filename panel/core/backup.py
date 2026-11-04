# -*- coding: utf-8 -*-
"""Резервное копирование: tar.gz с файлами сайтов, дампами MySQL и state."""
import datetime as dt
import os
import secrets
import shutil
import tarfile
import tempfile

from .. import utils
from ..context import CTX, run, have


def create(site_ids=None, with_db=True):
    store = CTX.store
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bid = stamp + "-" + secrets.token_hex(3)
    bdir = os.path.join(store.home, "backups")
    os.makedirs(bdir, exist_ok=True)
    path = os.path.join(bdir, "backup-%s.tar.gz" % stamp)
    sites = [s for s in store.data["sites"]
             if not site_ids or s["id"] in site_ids]
    tmp = tempfile.mkdtemp(prefix="hp-dump-")
    sql_path = None
    try:
        if with_db and not CTX.demo and have("mysqldump") and \
                store.data.get("dbs"):
            args = ["mysqldump", "--single-transaction", "--databases"] + \
                [d["name"] for d in store.data["dbs"]]
            code, out, _ = run(args, timeout=600, as_root=True)
            if code == 0 and out:
                sql_path = os.path.join(tmp, "databases.sql")
                with open(sql_path, "w", encoding="utf-8") as f:
                    f.write(out)
        with tarfile.open(path, "w:gz") as tar:
            for s in sites:
                root = os.path.join(store.home, s["docroot"]) if CTX.demo \
                    else s["docroot"]
                if os.path.isdir(root):
                    tar.add(root, arcname=os.path.join("www", s["domain"]))
            if sql_path and os.path.exists(sql_path):
                tar.add(sql_path, arcname="databases.sql")
            tar.add(store.path, arcname="state.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    meta = {"id": bid, "file": path,
            "size": os.path.getsize(path) if os.path.exists(path) else 0,
            "created": utils.now_str(),
            "sites": [s["domain"] for s in sites],
            "with_db": bool(with_db), "status": "готов"}
    store.data.setdefault("backups", []).insert(0, meta)
    _retention()
    store.notify("Резервная копия создана (%s)" % utils.human_size(meta["size"]))
    store.save()
    return meta


def _retention():
    limit = int(CTX.store.data["settings"].get("backup_retention", 7) or 7)
    store = CTX.store
    backups = store.data.get("backups", [])
    while len(backups) > limit:
        old = backups.pop()
        try:
            if old.get("file") and os.path.exists(old["file"]):
                os.remove(old["file"])
        except OSError:
            pass
        store.notify("Удалена старая резервная копия от %s" % old["created"])


def restore(bid, target_domains=None):
    store = CTX.store
    meta = next((b for b in store.data["backups"] if b["id"] == bid), None)
    if not meta or not os.path.exists(meta["file"]):
        return False, "архив не найден"
    tmp = tempfile.mkdtemp(prefix="hp-restore-")
    try:
        with tarfile.open(meta["file"], "r:gz") as tar:
            # защита от zip-slip: filter="data" режет симлинки/устройства
            members = [m for m in tar.getmembers()
                       if not os.path.isabs(m.name) and ".." not in m.name]
            try:
                tar.extractall(tmp, members=members, filter="data")
            except TypeError:  # Python < 3.12 без параметра filter
                tar.extractall(tmp, members=members)
        restored = []
        errors = []
        www = os.path.join(tmp, "www")
        if os.path.isdir(www):
            for dom in os.listdir(www):
                if target_domains and dom not in target_domains:
                    continue
                site = next((s for s in store.data["sites"]
                             if s["domain"] == dom), None)
                if not site:
                    continue
                src = os.path.join(www, dom)
                dst = os.path.join(store.home, site["docroot"]) if CTX.demo \
                    else site["docroot"]
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                # копируем РЯДОМ и только потом меняем местами: при сбое
                # копирования старые файлы сайта остаются на месте
                staging = dst + ".hp-restore-new"
                shutil.rmtree(staging, ignore_errors=True)
                try:
                    shutil.copytree(src, staging)
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    os.rename(staging, dst)
                    restored.append(dom)
                except (OSError, shutil.Error) as e:
                    shutil.rmtree(staging, ignore_errors=True)
                    errors.append("%s: %s" % (dom, str(e)[:120]))
        sql = os.path.join(tmp, "databases.sql")
        if os.path.exists(sql) and not CTX.demo and have("mysql"):
            with open(sql, encoding="utf-8") as f:
                code, _out, err = run(
                    ["mysql", "--defaults-extra-file=/etc/mysql/debian.cnf"],
                    timeout=600, input_text=f.read(), as_root=True)
            if code != 0:
                errors.append("БД не восстановлена: %s"
                              % ((err or "код %s" % code)[:150])[:200])
        store.notify("Восстановлено из копии %s: %s"
                     % (meta["created"], ", ".join(restored) or "ничего"))
        if errors:
            return False, ("восстановлено: %s; ОШИБКИ: %s"
                           % (", ".join(restored) or "—", "; ".join(errors)))
        return True, "восстановлено: %s" % (", ".join(restored) or "—")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def delete(bid):
    store = CTX.store
    meta = next((b for b in store.data["backups"] if b["id"] == bid), None)
    if meta:
        try:
            if meta.get("file") and os.path.exists(meta["file"]):
                os.remove(meta["file"])
        except OSError:
            pass
        store.data["backups"].remove(meta)
        store.save()
    return True, ""
