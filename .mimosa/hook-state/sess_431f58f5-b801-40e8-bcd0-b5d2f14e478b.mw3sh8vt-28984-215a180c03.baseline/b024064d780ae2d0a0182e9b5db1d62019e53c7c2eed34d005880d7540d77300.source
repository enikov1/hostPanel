# -*- coding: utf-8 -*-
"""Шаблоны конфигов веб-серверов и генерация/валидация/применение.

Каждый конфиг сайта собирается из templates + настроек безопасности,
перед записью проверяется синтаксис (nginx -t / apachectl configtest),
при ошибке откат на предыдущую версию.
"""
import os
import re

from .. import config
from ..context import CTX, run, have
from .. import utils

NGINX_SITE_TPL = """# HostPanel: сайт {domain}
server {{
    listen 80;
{ssl_listen}    server_name {server_names};
{http_redirect}
    root {docroot};
    index index.php index.html index.htm;

    access_log {logs_dir}/{domain}.access.log;
    error_log  {logs_dir}/{domain}.error.log;

    client_max_body_size {upload_size};

    # --- HostPanel: режим обслуживания ---
{maintenance}

    # --- HostPanel: фильтры (гео / IP / боты / WAF / rate limit) ---
{security}

{extra}

    location ~ /\\.ht {{ deny all; }}
}}
"""

NGINX_SSL_BLOCK = """    listen 443 ssl;
    ssl_certificate {cert};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
"""

NGINX_MAINTENANCE_ON = """    error_page 503 @maintenance;
    if (-f {maintenance_flag}) {{
        return 503;
    }}
    # именованная локация: обычный URI зацикливается (server-level if
    # выполняется снова при internal redirect) и nginx отдаёт дефолтную 503
    location @maintenance {{
        root {panel_home};
        try_files /hostpanel-maintenance.html =503;
    }}
"""

NGINX_PHP_LOC = """    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php{php}-fpm{pool_suffix}.sock;
    }}"""

PMA_PROTECT_LOC = """    # --- HostPanel: защита phpMyAdmin (basic auth) ---
    location ^~ /pma/ {{
        auth_basic "phpMyAdmin";
        auth_basic_user_file {htpasswd};
        location ~ \\.php$ {{
            include snippets/fastcgi-php.conf;
            fastcgi_pass unix:/run/php/php{php}-fpm{pool_suffix}.sock;
        }}
    }}
"""

NGINX_PROXY_LOC = """    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}"""

APACHE_SITE_TPL = """# HostPanel: сайт {domain}
<VirtualHost *:{port}>
    ServerName {domain}
{aliases}    DocumentRoot {docroot}
    <Directory {docroot}>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
{php_handler}{maintenance}{security}
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}-error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}-access.log combined
</VirtualHost>
"""

APACHE_PHP_HANDLER = """    <FilesMatch \\.php$>
        SetHandler "proxy:unix:/run/php/php{php}-fpm{pool_suffix}.sock|fcgi://localhost"
    </FilesMatch>
"""

APACHE_MAINTENANCE = """    RewriteEngine On
    RewriteCond %{{DOCUMENT_ROOT}}/hostpanel-maintenance.flag -f
    RewriteRule ^ - [R=503,L]
    ErrorDocument 503 /hostpanel-maintenance.html
"""

FPM_POOL_TPL = """; HostPanel: пул PHP-FPM для {domain}
[{pool}]
user = www-data
group = www-data
listen = /run/php/php{php}-fpm{pool_suffix}.sock
listen.owner = www-data
listen.group = www-data
pm = {pm}
pm.max_children = {max_children}
pm.start_servers = {start_servers}
pm.min_spare_servers = {min_spare}
pm.max_spare_servers = {max_spare}
php_admin_value[error_log] = {logs_dir}/{domain}.php-error.log
php_admin_flag[log_errors] = on
"""

# --- профили производительности сайта (галочки в карточке сайта) -----------

PERF_KEYS = ("gzip", "static_cache", "hsts", "http2")


def default_perf():
    return {"gzip": False, "static_cache": False, "hsts": False,
            "http2": False}


def perf_extra(site):
    """Секции nginx по галочкам производительности сайта."""
    perf = site.get("perf") or {}
    blocks = []
    if perf.get("gzip"):
        blocks.append(
            "    # HostPanel: сжатие ответов\n"
            "    gzip on;\n"
            "    gzip_comp_level 5;\n"
            "    gzip_min_length 1024;\n"
            "    gzip_types text/plain text/css text/xml application/json "
            "application/javascript application/xml image/svg+xml;\n"
            "    gzip_vary on;")
    # кэш статики не включаем для nginx+node: docroot может не содержать
    # файлы приложения, и nginx начнёт отвечать 404 вместо прокси
    if perf.get("static_cache") and site["webserver"] != "nginx+node":
        blocks.append(
            "    # HostPanel: кэш статики в браузере (30 дней)\n"
            "    location ~* \\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|"
            "woff2|ttf|webp|avif)$ {\n"
            "        expires 30d;\n"
            '        add_header Cache-Control "public";\n'
            "        access_log off;\n"
            "    }")
    ssl = site.get("ssl") or {}
    if perf.get("hsts") and ssl.get("kind") not in ("", "none"):
        blocks.append(
            "    # HostPanel: браузер ходит на сайт только по HTTPS\n"
            '    add_header Strict-Transport-Security "max-age=31536000" '
            "always;")
    return "\n".join(blocks)


# --- генерация секции фильтров безопасности (nginx) ------------------------

def nginx_security_section(site, sec=None):
    """Cloudflare-подобные фильтры для nginx: гео, IP-списки, боты,
    WAF, rate limit. Секция строится по сайту (map-ключи по домену)."""
    from . import security
    return security.site_section(site, sec)


def apache_security_section(sec):
    from . import security
    return security.apache_filters(sec)


# --- управление конфигами ---------------------------------------------------

def site_log_paths(site):
    if CTX.demo:
        d = os.path.join(CTX.home, "logs")
    else:
        d = config.REAL_LOGS_DIR
        os.makedirs(d, exist_ok=True)
    return {"access": os.path.join(d, site["domain"] + ".access.log"),
            "error": os.path.join(d, site["domain"] + ".error.log")}


def pool_name(domain):
    return re.sub(r"[^a-z0-9]", "", domain.lower())[:20] or "site"


def _pool_suffix(site):
    """Пулы поддоменов живут в отдельном сокете, чтобы можно было
    настраивать независимо."""
    return "-" + pool_name(site["domain"])


def nginx_conf_path(domain):
    return "/etc/nginx/sites-available/%s.conf" % domain


def apache_conf_path(domain):
    return "/etc/apache2/sites-available/%s.conf" % domain


def fpm_conf_path(site):
    php = site.get("php") or "8.2"
    return "/etc/php/%s/fpm/pool.d/%s.conf" % (php, pool_name(site["domain"]))


def validate_nginx():
    """Проверка синтаксиса nginx; True если конфиг валиден."""
    code, _out, _err = run(["nginx", "-t"], timeout=30)
    return code == 0


def validate_apache():
    if not have("apache2ctl"):
        return True
    code, _out, _err = run(["apache2ctl", "configtest"], timeout=30)
    return code == 0


def write_text_atomic(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".hp-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def read_conf(path):
    """Читает конфиг для будущего отката; отсутствие файла = None."""
    try:
        return utils.read_text_file(path)
    except OSError:
        return None


def site_server_names(site):
    """Имена сервера для конфигов: www добавляется ТОЛЬКО когда сайт
    действительно обслуживает www — флаг www у сайта или включён
    сниппет «редирект www → без www» (для редиректа www тоже нужен
    в server_name). Поддомены всегда без www."""
    domain = site["domain"]
    if site.get("parent"):
        return domain
    want_www = bool(site.get("www")) or bool(
        (site.get("snippets") or {}).get("www_redirect"))
    return domain + (" www." + domain if want_www else "")


def write_site_configs(site, old_domain=None):
    """Генерирует конфиги nginx/apache/fpm для сайта (рабочий режим).
    Перед применением проверяет синтаксис, при ошибке откатывает."""
    if CTX.demo:
        return True, ""
    domain = site["domain"]
    docroot = utils.safe_join("/", site["docroot"].lstrip("/")) \
        if os.path.isabs(site["docroot"]) else site["docroot"]
    logs_dir = config.REAL_LOGS_DIR
    os.makedirs(docroot, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    maintenance_page = os.path.join(config.DEFAULT_HOME, "maintenance")
    names = site_server_names(site)

    # -- общие конфиги фильтров (geo/rate-limit) перед генерацией ----------
    if not CTX.demo:
        from . import security as sec_mod
        sec = site.get("security") or {}
        if (sec.get("geo_mode") in ("allow", "deny") and
                [c for c in (sec.get("geo_countries") or [])
                 if utils.valid_country(c)]):
            ok_geo, err_geo = sec_mod.ensure_geo_map()
            if not ok_geo and CTX.store:
                CTX.store.notify(
                    "Гео-фильтр %s неактивен: %s" % (domain, err_geo), "warn")
        if int((sec.get("rate_limit") or 0)) > 0:
            ok_rl, err_rl = sec_mod.ensure_rate_limit_conf()
            if not ok_rl and CTX.store:
                CTX.store.notify("Rate-limit %s: %s" % (domain, err_rl),
                                 "warn")
        ok_waf, err_waf = sec_mod.ensure_waf_conf()
        if not ok_waf and CTX.store:
            CTX.store.notify("WAF %s: %s" % (domain, err_waf), "warn")

    # -- nginx ----------------------------------------------------------
    nginx_written = False
    old_nginx = None
    # конфиг nginx нужен всем типам, кроме чистого apache
    # (static и nginx+node тоже обслуживаются через nginx)
    if site["webserver"] != "apache":
        if site["webserver"] == "nginx+node" and \
                site.get("node", {}).get("enabled"):
            extra = NGINX_PROXY_LOC.format(port=site["node"].get("port", 3000))
        elif site.get("php"):
            extra = NGINX_PHP_LOC.format(
                php=site["php"], pool_suffix=_pool_suffix(site))
        else:
            extra = "    # статический сайт"
        # защита phpMyAdmin (nginx-сайты; apache — через .htaccess)
        if (site.get("apps") or {}).get("pma", {}).get("protected") and \
                site.get("php") and site["webserver"] == "nginx":
            extra = PMA_PROTECT_LOC.format(
                htpasswd=os.path.join(
                    config.PMA_HTPASSWD_DIR,
                    "%s.htpasswd" % pool_name(site["domain"])),
                php=site["php"], pool_suffix=_pool_suffix(site)) + extra
        # --- сниппеты из «библиотеки» сайта ---
        snip = site.get("snippets") or {}
        snippet_blocks = []
        if snip.get("www_redirect"):
            snippet_blocks.append(
                "    # HostPanel: редирект www → без www\n"
                "    if ($host ~* ^www\\.) { return 301 $scheme://%s"
                "$request_uri; }" % domain)
        if (snip.get("admin_ip") or "").strip():
            ips = ", ".join(ip.strip() for ip in
                            snip["admin_ip"].replace(",", " ").split()
                            if ip.strip())
            # путь админки настраивается (admin, wp-admin, administrator…)
            import re as _re
            apath = _re.sub(r"[^a-zA-Z0-9_\-/]", "",
                            str(snip.get("admin_path") or "admin")).strip("/")
            if not apath:
                apath = "admin"
            segs = [_re.escape(x) for x in apath.split("/") if x]
            rx = "^/(?:%s)(?:/|$)" % "|".join(segs)
            snippet_blocks.append(
                "    # HostPanel: /%s только с указанных IP\n"
                "    location ~ %s {\n"
                "        allow %s;\n"
                "        deny all;\n"
                "        try_files $uri $uri/ /index.php$is_args$args;\n"
                "    }" % (apath, rx, ips))
        upload_size = (snip.get("upload_size") or "").strip() or "64m"
        ssl = site.get("ssl") or {}
        ssl_listen = ""
        http_redirect = ""
        if ssl.get("kind") != "none" and not CTX.demo:
            from . import ssl as ssl_mod
            p = ssl_mod.paths(domain)
            # страховка: файлы сертификата могут пропасть (переезд, ручная
            # чистка) — тогда 443-блок с битым путём уронит весь nginx -t.
            # Не выпускаем SSL-блок и предупреждаем.
            if not (os.path.exists(p["cert"]) and os.path.exists(p["key"])):
                if CTX.store:
                    CTX.store.notify(
                        "SSL %s: файлы сертификата не найдены (%s) — "
                        "443-блок не применён. Перевыпустите сертификат."
                        % (domain, p["cert"]), "warn")
            else:
                ssl_listen = NGINX_SSL_BLOCK.format(cert=p["cert"],
                                                    key=p["key"])
            if (site.get("perf") or {}).get("http2"):
                ssl_listen = ssl_listen.replace(
                    "listen 443 ssl;", "listen 443 ssl http2;")
            # HTTPS обязателен: HTTP-запросы переводятся на https (безопасный
            # вариант if — только return; ACME-проверки certbot --nginx
            # выполняются до включения редиректа или временно меняют конфиг)
            http_redirect = ("    if ($scheme = http) {\n"
                             "        return 301 https://$host$request_uri;\n"
                             "    }\n")
        maintenance = ""
        if site.get("maintenance"):
            # страница обслуживания лежит рядом с флагом (туда её пишет
            # set_maintenance) — корень локации должен совпадать
            mflag = maintenance_flag_path(site)
            maintenance = NGINX_MAINTENANCE_ON.format(
                maintenance_flag=mflag,
                panel_home=os.path.dirname(mflag))
        else:
            maintenance = "    # обслуживание выключено"
        perf_blocks = perf_extra(site)
        if perf_blocks:
            extra = (extra + "\n\n" + perf_blocks) if extra.strip() \
                else perf_blocks
        if snippet_blocks:
            block = "\n".join(snippet_blocks)
            extra = (block + "\n\n" + extra) if extra.strip() else block
        conf = NGINX_SITE_TPL.format(
            domain=domain, server_names=names, docroot=docroot,
            logs_dir=logs_dir, upload_size=upload_size, extra=extra,
            ssl_listen=ssl_listen, maintenance=maintenance,
            http_redirect=http_redirect,
            security=nginx_security_section(site))
        av = nginx_conf_path(domain)
        old_nginx = read_conf(av)
        write_text_atomic(av, conf)
        nginx_written = True
        en = "/etc/nginx/sites-enabled/%s.conf" % domain
        if not os.path.exists(en):
            os.symlink(av, en)

    # -- apache ----------------------------------------------------------
    apache_written = False
    old_apache = None
    if "apache" in site["webserver"]:
        php_handler = ""
        if site.get("php"):
            php_handler = APACHE_PHP_HANDLER.format(
                php=site["php"], pool_suffix=_pool_suffix(site))
        # apache всегда слушает 8081 (backend): порт 80 занят nginx,
        # 8080 — самой панелью
        port = 8081
        # ServerAlias = все имена, кроме основного (www — только если
        # сайт его обслуживает)
        aliases = "".join("    ServerAlias %s\n" % n
                          for n in site_server_names(site).split(" ")[1:])
        maintenance = APACHE_MAINTENANCE if site.get("maintenance") else ""
        conf = APACHE_SITE_TPL.format(
            domain=domain, aliases=aliases, docroot=docroot, port=port,
            php_handler=php_handler, maintenance=maintenance,
            security=apache_security_section(site.get("security") or {}))
        av = apache_conf_path(domain)
        old_apache = read_conf(av)
        write_text_atomic(av, conf)
        apache_written = True
        run(["a2ensite", domain], as_root=True)
        if php_handler:
            run(["a2enmod", "proxy_fcgi", "rewrite"], as_root=True)

    # -- пул FPM -----------------------------------------------------------
    fpm_written = False
    old_fpm = None
    if site.get("php") and site.get("fpm") and \
            site["webserver"] in ("nginx", "nginx+apache", "apache"):
        pool = FPM_POOL_TPL.format(
            domain=domain, pool=pool_name(domain), php=site["php"],
            pool_suffix=_pool_suffix(site), logs_dir=logs_dir,
            **site["fpm"])
        fp = fpm_conf_path(site)
        old_fpm = read_conf(fp)
        write_text_atomic(fp, pool)
        fpm_written = True

    # -- валидация и откат ---------------------------------------------------
    ok = True
    errs = []
    if nginx_written and not validate_nginx():
        ok = False
        errs.append("nginx: ошибка синтаксиса, конфиг откачен")
        _restore(nginx_conf_path(domain), old_nginx)
    if apache_written and not validate_apache():
        ok = False
        errs.append("apache: ошибка синтаксиса, конфиг откачен")
        _restore(apache_conf_path(domain), old_apache)
    if fpm_written:
        php = site.get("php") or "8.2"
        # бинарник называется php-fpm8.3 (юнит — php8.3-fpm)
        binname = "php-fpm" + php
        if have(binname):
            code, _out, err = run([binname, "-t"], timeout=30)
            if code != 0:
                ok = False
                errs.append("php-fpm: %s" % (err or "ошибка конфигурации"))
                _restore(fpm_conf_path(site), old_fpm)
    if not ok:
        return False, "; ".join(errs)
    if fpm_written:
        # новый/изменённый пул подхватывается только после reload php-fpm
        php = site.get("php") or "8.2"
        run(["systemctl", "reload", "php%s-fpm" % php], timeout=30,
            as_root=True)
    webserver_reload()
    return True, ""


def _restore(path, old_content):
    if old_content is None:
        try:
            os.remove(path)
        except OSError:
            pass
    else:
        write_text_atomic(path, old_content)


def webserver_reload():
    for s in ("nginx", "apache2"):
        code, out, _ = run(["systemctl", "is-active", s], timeout=10)
        if code == 0 and out.strip() == "active":
            run(["systemctl", "reload", s], timeout=30, as_root=True)


def remove_site_configs(site, domain=None):
    domain = domain or site["domain"]
    if CTX.demo:
        return
    for path in (nginx_conf_path(domain),
                 "/etc/nginx/sites-enabled/%s.conf" % domain,
                 apache_conf_path(domain),
                 "/etc/apache2/sites-enabled/%s.conf" % domain,
                 fpm_conf_path(site)):
        try:
            if os.path.islink(path) or os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    if have("a2dissite"):
        run(["a2dissite", domain], as_root=True)
    webserver_reload()


def provision_site_files(site):
    """Создаёт папки сайта, заглушку индекса и выставляет права."""
    docroot = site["docroot"] if os.path.isabs(site["docroot"]) \
        else os.path.join(CTX.home, site["docroot"])
    try:
        os.makedirs(docroot, exist_ok=True)
        index = os.path.join(docroot, "index.html")
        if not os.path.exists(index) and not os.path.exists(
                os.path.join(docroot, "index.php")):
            with open(index, "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html>\n<html lang=\"ru\">\n<head>"
                        "<meta charset=\"utf-8\"><title>%s</title></head>\n"
                        "<body><h1>Сайт %s создан панелью HostPanel</h1>"
                        "</body></html>\n" % (site["domain"], site["domain"]))
        if not CTX.demo:
            run(["chown", "-R", "www-data:www-data", docroot], as_root=True)
    except OSError as e:
        return "Не удалось создать папки сайта: %s" % e
    return ""


def maintenance_flag_path(site):
    """Файл-флаг режима обслуживания (его наличие включает 503)."""
    root = os.path.dirname(site["docroot"].rstrip("/")) \
        if not os.path.isabs(site["docroot"]) else \
        os.path.dirname(site["docroot"].rstrip("/"))
    if CTX.demo:
        return os.path.join(CTX.home, root, "hostpanel-maintenance.flag")
    return os.path.join(os.path.dirname(site["docroot"].rstrip("/")),
                        "hostpanel-maintenance.flag")


def set_maintenance(site, enabled):
    """Включает/выключает режим обслуживания (HTTP 503 + страница).
    Возвращает (ok, err) — конфиг валидируется, при ошибке откатывается."""
    flag = maintenance_flag_path(site)
    page_dir = os.path.dirname(flag)
    if enabled:
        os.makedirs(page_dir, exist_ok=True)
        with open(flag, "w", encoding="utf-8") as f:
            f.write("on\n")
        page = os.path.join(page_dir, "hostpanel-maintenance.html")
        if not os.path.exists(page):
            with open(page, "w", encoding="utf-8") as f:
                f.write(MAINTENANCE_PAGE % site["domain"])
    else:
        try:
            os.remove(flag)
        except OSError:
            pass
    site["maintenance"] = bool(enabled)
    if not CTX.demo:
        ok, err = write_site_configs(site)
        webserver_reload()
        return ok, err
    return True, ""


MAINTENANCE_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>Сайт на техническом обслуживании</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
.c{max-width:520px;text-align:center;padding:40px}h1{font-size:22px;margin:0 0 12px}
p{color:#94a3b8;line-height:1.6;margin:0}</style></head>
<body><div class="c"><h1>Ведутся технические работы</h1>
<p>Сайт <b>%s</b> временно недоступен.<br>Скоро мы вернёмся — попробуйте
обновить страницу через несколько минут.</p></div></body></html>
"""

SITE_DISABLED_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>Сайт отключён</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
.c{max-width:520px;text-align:center;padding:40px}
h1{font-size:22px;margin:0 0 12px}p{color:#94a3b8;line-height:1.6;margin:0}
.b{display:inline-block;margin-top:20px;padding:8px 18px;border:1px solid #475569;
border-radius:10px;color:#e2e8f0;text-decoration:none;font-size:14px}</style></head>
<body><div class="c"><h1>Сайт отключён</h1>
<p>Сайт <b>%s</b> в данный момент отключён администратором.<br>
Работа будет возобновлена после включения сайта в панели управления.</p>
</div></body></html>
"""

SITE_DISABLED_NGINX_TPL = """# HostPanel: сайт {domain} отключён через панель
server {{
    listen 80;
{ssl_listen}    server_name {server_names};
    access_log off;
    error_page 503 @disabled;
    location @disabled {{
        root {maintenance_dir};
        try_files /site-disabled.html =503;
    }}
    location / {{
        return 503;
    }}
}}
"""

SITE_DISABLED_APACHE_TPL = """# HostPanel: сайт {domain} отключён через панель
<VirtualHost *:8081>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot {maintenance_dir}
    <Directory {maintenance_dir}>
        Require all granted
    </Directory>
    RewriteEngine On
    RewriteRule ^ - [R=503,L]
    ErrorDocument 503 /site-disabled.html
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}-disabled-error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}-disabled-access.log combined
</VirtualHost>
"""


def _maintenance_dir():
    return os.path.join(config.DEFAULT_HOME, "maintenance")


def _write_disabled_page(domain):
    d = _maintenance_dir()
    os.makedirs(d, exist_ok=True)
    page = os.path.join(d, "site-disabled.html")
    if not os.path.exists(page):
        with open(page, "w", encoding="utf-8") as f:
            f.write(SITE_DISABLED_PAGE % "ваш сайт")
    return d


def write_site_disabled(site):
    """Заглушка «сайт отключён» (HTTP 503) вместо снятия конфига.

    Пишет отдельный конфиг-заглушку в sites-enabled (обычным файлом, не
    симлинком), чтобы домен не отдавал дефолтную страницу веб-сервера.
    """
    if CTX.demo:
        return True, ""
    domain = site["domain"]
    mdir = _write_disabled_page(domain)
    ssl_listen = ""
    ssl = site.get("ssl") or {}
    if ssl.get("kind") not in (None, "", "none"):
        from . import ssl as ssl_mod
        p = ssl_mod.paths(domain)
        if os.path.exists(p["cert"]) and os.path.exists(p["key"]):
            ssl_listen = NGINX_SSL_BLOCK.format(cert=p["cert"], key=p["key"])
    conf = SITE_DISABLED_NGINX_TPL.format(
        domain=domain, server_names=site_server_names(site),
        maintenance_dir=mdir, ssl_listen=ssl_listen)
    try:
        en = "/etc/nginx/sites-enabled/%s.conf" % domain
        if os.path.islink(en):
            os.remove(en)
        write_text_atomic(en, conf)
    except OSError as e:
        return False, str(e)
    # apache-заглушка для сайтов с apache
    if "apache" in site["webserver"]:
        try:
            av = apache_conf_path(domain)
            write_text_atomic(av, SITE_DISABLED_APACHE_TPL.format(
                domain=domain, maintenance_dir=mdir))
            run(["a2ensite", domain], as_root=True)
        except OSError as e:
            return False, str(e)
    webserver_reload()
    return True, ""


def remove_site_disabled(site):
    """Убирает конфиг-заглушку перед включением сайта."""
    if CTX.demo:
        return
    en = "/etc/nginx/sites-enabled/%s.conf" % site["domain"]
    try:
        # заглушка — обычный файл; боевой конфиг — симлинк
        if os.path.exists(en) and not os.path.islink(en):
            os.remove(en)
    except OSError:
        pass
    webserver_reload()
