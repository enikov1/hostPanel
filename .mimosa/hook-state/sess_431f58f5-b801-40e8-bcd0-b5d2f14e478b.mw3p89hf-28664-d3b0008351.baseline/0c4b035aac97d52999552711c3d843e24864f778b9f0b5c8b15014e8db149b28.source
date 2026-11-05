# -*- coding: utf-8 -*-
"""Node.js-приложения сайтов: systemd-юниты, npm, журналы."""
import glob
import os
import re
import shutil

from ..context import CTX, run, have
from .. import utils

NODE_UNIT_TPL = """[Unit]
Description=HostPanel Node.js: {domain}
After=network.target

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={node_bin} {script}
Restart=on-failure
RestartSec=3
User=www-data
Environment=PORT={port}
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
"""


def unit_name(domain):
    return "hostpanel-node-" + re.sub(r"[^a-z0-9-]", "", domain.lower())


def bin_path(version):
    if CTX.demo:
        return "/usr/bin/node"
    for c in ("node" + version, "node"):
        if have(c):
            return shutil.which(c)
    for d in glob.glob("/usr/local/n/versions/node/%s*/bin/node" % version):
        return d
    return shutil.which("node") or "/usr/bin/node"


def apply(site, action="restart"):
    """Управление systemd-юнитом Node.js-приложения сайта."""
    node = site.get("node") or {}
    if not node.get("enabled"):
        return True, ""
    unit = unit_name(site["domain"])
    cwd = site["docroot"]
    if not os.path.isabs(cwd):
        cwd = os.path.join(CTX.home, cwd)
    conf = NODE_UNIT_TPL.format(domain=site["domain"], cwd=cwd,
                                node_bin=bin_path(node.get("version", "20")),
                                script=node.get("script", "app.js"),
                                port=node.get("port", 3000))
    if not CTX.demo:
        path = "/etc/systemd/system/%s.service" % unit
        with open(path, "w", encoding="utf-8") as f:
            f.write(conf)
        run(["systemctl", "daemon-reload"], as_root=True)
        run(["chown", "-R", "www-data:www-data", cwd], as_root=True)
    if action == "enable":
        code, _, err = run(["systemctl", "enable", "--now", unit],
                           timeout=60, as_root=True)
    elif action == "stop":
        code, _, err = run(["systemctl", "stop", unit], timeout=60,
                           as_root=True)
    elif action == "disable":
        # остановить и убрать из автозапуска (юнит-файл остаётся до
        # удаления сайта — конфиг перегенерируется без proxy_pass)
        code, _, err = run(["systemctl", "disable", "--now", unit],
                           timeout=60, as_root=True)
    else:
        code, _, err = run(["systemctl", "restart", unit], timeout=60,
                           as_root=True)
    if CTX.demo:
        return True, "демо: %s выполнено" % action
    return code == 0, ("" if code == 0 else err)


def remove_unit(site):
    if CTX.demo:
        return
    unit = unit_name(site["domain"])
    run(["systemctl", "stop", unit], timeout=30, as_root=True)
    run(["systemctl", "disable", unit], timeout=30, as_root=True)
    try:
        os.remove("/etc/systemd/system/%s.service" % unit)
    except OSError:
        pass
    run(["systemctl", "daemon-reload"], as_root=True)


def logs(site, lines=100):
    unit = unit_name(site["domain"])
    if CTX.demo:
        return ["[демо] журнал Node.js-приложения %s" % site["domain"],
                "2026-11-02 09:00:01 server listening on port %d"
                % (site.get("node", {}) or {}).get("port", 3000),
                "2026-11-02 09:00:05 GET /api/v1/status 200 12ms"]
    code, out, err = run(["journalctl", "-u", unit, "-n", str(lines),
                          "--no-pager", "-o", "short-iso"], timeout=30)
    return (out or err).splitlines()
