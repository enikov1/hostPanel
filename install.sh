#!/usr/bin/env bash
# HostPanel — установка одной командой (Debian/Ubuntu).
#
#   curl -fsSL https://ваш-сервер/hostpanel/install.sh | sudo bash
#   либо: sudo bash install.sh
#
# Что делает:
#   1. Ставит весь стек служб, необходимый панели: nginx, Apache (backend
#      :8081), PHP 8.3-FPM с модулями, MariaDB, certbot (Let's Encrypt),
#      Node.js + npm, Redis, Memcached, fail2ban, git, архиваторы, ufw, cron
#   2. Настраивает Apache на порт 8081 (80 занят nginx, 8080 — панелью)
#   3. Копирует пакет panel/ в /opt/hostpanel/panel
#   4. Создаёт systemd-службу hostpanel (порт 8080, автозапуск)
#   5. Печатает пароль администратора
#
# Доустановить/удалить службы позже можно в самой панели:
#   раздел «Система → Установка ПО».
set -uo pipefail

PANEL_HOME="${PANEL_HOME:-/opt/hostpanel}"
PANEL_PORT="${PANEL_PORT:-8080}"
# нестандартный HTTPS-порт панели: сканеры не находят страницу входа
# на стандартном 443 (там nginx молча рвёт соединение — return 444)
PANEL_TLS_PORT="${PANEL_TLS_PORT:-7222}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(id -u)" = "0" ] || { echo "Запустите от root: sudo bash install.sh"; exit 1; }

# ------------------------------------------- самобутстрап из GitHub --------
# Установка одной командой даже без панели рядом:
#   curl -fsSL https://raw.githubusercontent.com/enikov1/hostPanel/main/install.sh -o install.sh && sudo bash install.sh
# Если рядом с install.sh нет panel/ — скачаем репозиторий целиком.
REPO="enikov1/hostPanel"
if [ ! -d "$SRC_DIR/panel" ]; then
    echo "==> panel/ рядом с install.sh нет — скачиваю репозиторий github.com/$REPO…"
    DL_OK=0
    if command -v curl >/dev/null 2>&1; then
        mkdir -p /tmp/hostpanel-src
        if curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" \
                -o /tmp/hostpanel-src/repo.tar.gz; then
            tar xzf /tmp/hostpanel-src/repo.tar.gz -C /tmp/hostpanel-src/
            SRC_DIR="$(echo /tmp/hostpanel-src/*/)"
            DL_OK=1
        fi
    elif command -v wget >/dev/null 2>&1; then
        mkdir -p /tmp/hostpanel-src
        if wget -qO /tmp/hostpanel-src/repo.tar.gz \
                "https://github.com/$REPO/archive/refs/heads/main.tar.gz"; then
            tar xzf /tmp/hostpanel-src/repo.tar.gz -C /tmp/hostpanel-src/
            SRC_DIR="$(echo /tmp/hostpanel-src/*/)"
            DL_OK=1
        fi
    fi
    [ "$DL_OK" = "1" ] || {
        echo "ОШИБКА: не удалось скачать репозиторий. Проверьте интернет или" >&2
        echo "скачайте архив вручную: https://github.com/$REPO/archive/refs/heads/main.tar.gz" >&2
        exit 1
    }
    echo "==> Исходники скачаны: $SRC_DIR"
fi

echo "==> HostPanel: установка в $PANEL_HOME"

# ---------------------------------------------------------------- 1. стек --
echo "==> Установка служб: nginx, Apache, PHP 8.3, MariaDB, certbot, Node.js…"
export DEBIAN_FRONTEND=noninteractive

# Репозиторий sury: PHP 7.4–8.5 (в Ubuntu 26.04 из коробки только 8.5;
# PPA ondrej/php новые выпуски Ubuntu не поддерживает)
if [ ! -s /etc/apt/sources.list.d/php-sury.list ]; then
    echo "==> Подключение репозитория PHP packages.sury.org…"
    (curl -fsSL https://packages.sury.org/php/apt.gpg \
         -o /etc/apt/trusted.gpg.d/sury.gpg 2>/dev/null || \
     wget -qO /etc/apt/trusted.gpg.d/sury.gpg \
         https://packages.sury.org/php/apt.gpg) && \
    . /etc/os-release && \
    echo "deb https://packages.sury.org/php/ $VERSION_CODENAME main" \
        > /etc/apt/sources.list.d/php-sury.list
fi
# почта: postfix ставим неинтерактивно (иначе debconf спрашивает тип)
echo "postfix postfix/main_mailer_type string 'Local only'" | debconf-set-selections 2>/dev/null || true
echo "postfix postfix/mailname string $(hostname)" | debconf-set-selections 2>/dev/null || true

apt-get update -y >/dev/null 2>&1 || echo "   предупреждение: apt-get update завершился с ошибкой"

APT_PKGS=(nginx libnginx-mod-http-geoip2 apache2
  php8.3-fpm php8.3-cli php8.3-mysql php8.3-curl php8.3-gd php8.3-mbstring
  php8.3-xml php8.3-zip php8.3-bcmath php8.3-intl php8.3-opcache
  mariadb-server mariadb-client
  certbot python3-certbot-nginx python3-certbot-apache
  postfix dovecot-core dovecot-imapd dovecot-pop3d mailutils
  nodejs npm redis-server memcached fail2ban git unzip zip ufw cron openssl qrencode)
if apt-get install -y "${APT_PKGS[@]}"; then
    echo "   стек служб установлен"
else
    echo "   ПРЕДУПРЕЖДЕНИЕ: часть пакетов не установилась." >&2
    echo "   Доустановите их позже в панели: Система → Установка ПО." >&2
fi

# ------------------------------------------------- 2. настройка служб ------
echo "==> Настройка Apache (backend :8081) и служб автозапуска…"
a2enmod proxy_fcgi rewrite headers expires >/dev/null 2>&1 || true
a2dissite 000-default >/dev/null 2>&1 || true
if ! grep -q '^Listen 8081' /etc/apache2/ports.conf 2>/dev/null; then
    sed -i 's/^Listen 80$/Listen 8081/' /etc/apache2/ports.conf 2>/dev/null || true
    grep -q '^Listen 8081' /etc/apache2/ports.conf 2>/dev/null || \
        echo 'Listen 8081' >> /etc/apache2/ports.conf
fi
echo 'ServerName localhost' > /etc/apache2/conf-available/servername.conf
a2enconf servername >/dev/null 2>&1 || true
systemctl daemon-reload >/dev/null 2>&1 || true
systemctl enable --now nginx apache2 mariadb php8.3-fpm redis-server \
    memcached postfix dovecot cron >/dev/null 2>&1 || true

# ------------------------------------------- 2.5 брандмауэр (ufw) ---------
# Панель и внутренние службы не должны быть видны из интернета: к панели
# ходят по SSH-туннелю (или через TLS-фронт nginx :443), СУБД/Redis/кэш
# слушают только localhost.
if command -v ufw >/dev/null 2>&1; then
    echo "==> Настройка брандмауэра ufw…"
    ufw default deny incoming >/dev/null 2>&1 || true
    ufw default allow outgoing >/dev/null 2>&1 || true
    for p in 22 25 80 110 143 443 587 993 995 "$PANEL_TLS_PORT"; do
        ufw allow "$p/tcp" >/dev/null 2>&1 || true
    done
    ufw --force enable >/dev/null 2>&1 || true
    echo "   открыто снаружи: 22 (SSH), 80/443 (сайты),"
    echo "                    25/587/110/143/993/995 (почта)"
    echo "   закрыто: $PANEL_PORT (панель — по SSH-туннелю), 8081 (Apache),"
    echo "            3306 (MariaDB), 5432 (PG), 6379 (Redis), 11211 (Memcached)"
else
    echo "   ПРЕДУПРЕЖДЕНИЕ: ufw не установлен — порт панели открыт снаружи."
fi

# ------------------------- 2.7 заглушка для IP-адреса (nginx) -------------
# Запросы к голому IP (порт 80 и 443) получают страницу-заглушку с кодом
# 404 и запретом индексации. Разметку можно править из панели
# («Сайты → Заглушка для IP»): /opt/hostpanel/default-site/placeholder.html
if command -v nginx >/dev/null 2>&1; then
    echo "==> Заглушка для IP-адреса (404, noindex) на портах 80 и 443…"
    mkdir -p "$PANEL_HOME/default-site"
    if [ ! -s "$PANEL_HOME/default-site/placeholder.html" ]; then
        cat > "$PANEL_HOME/default-site/placeholder.html" <<'EOF'
<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<title>Страница не найдена</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;background:#f4f5f7;
color:#333;display:flex;min-height:100vh;align-items:center;justify-content:center;
margin:0}
.c{max-width:480px;text-align:center;padding:40px}
h1{font-size:20px;margin:0 0 10px}
p{color:#777;line-height:1.6;margin:0;font-size:14px}
</style></head>
<body><div class="c"><h1>404</h1>
<p>Здесь пока нет сайта.<br>
Скоро на этом адресе появится что-то интересное.</p></div></body></html>
EOF
    fi
    # стандартный vhost :80 → заглушка (заменяет страницу nginx по умолчанию)
    cat > /etc/nginx/sites-available/default <<EOF
# HostPanel: заглушка для голого IP-адреса (404 + noindex).
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    add_header X-Robots-Tag "noindex, nofollow" always;
    error_page 404 /placeholder.html;
    location = /placeholder.html {
        internal;
        root $PANEL_HOME/default-site;
    }
    location / {
        return 404;
    }
}
EOF
    nginx -t && systemctl reload nginx || true
fi

# ------------------------------- 2.8 TLS-фронт панели (nginx) -------------
# Самоподписанный сертификат на IP; панель доступна по
# https://<IP>:$PANEL_TLS_PORT, стандартный 443 отдаёт ту же заглушку
# (404, noindex) — страница входа не находится сканерами.
if command -v nginx >/dev/null 2>&1; then
    echo "==> TLS-фронт панели: https://<IP>:$PANEL_TLS_PORT (443 — заглушка 404)"
    mkdir -p "$PANEL_HOME/certs/panel"
    if [ ! -s "$PANEL_HOME/certs/panel/panel.crt" ]; then
        IPADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
        openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
            -keyout "$PANEL_HOME/certs/panel/panel.key" \
            -out "$PANEL_HOME/certs/panel/panel.crt" \
            -subj "/CN=${IPADDR:-hostpanel}" \
            -addext "subjectAltName=IP:${IPADDR:-127.0.0.1}" 2>/dev/null || true
        chmod 600 "$PANEL_HOME/certs/panel/panel.key"
    fi
    cat > /etc/nginx/sites-available/hostpanel-admin.conf <<EOF
# HostPanel: TLS-фронт панели (панель слушает 127.0.0.1:$PANEL_PORT).
# На стандартном 443 — пустой ответ, чтобы сканеры не находили страницу входа.
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate $PANEL_HOME/certs/panel/panel.crt;
    ssl_certificate_key $PANEL_HOME/certs/panel/panel.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    add_header X-Robots-Tag "noindex, nofollow" always;
    error_page 404 /placeholder.html;
    location = /placeholder.html {
        internal;
        root $PANEL_HOME/default-site;
    }
    location / {
        return 404;
    }
}
server {
    listen $PANEL_TLS_PORT ssl;
    listen [::]:$PANEL_TLS_PORT ssl;
    server_name _;
    ssl_certificate $PANEL_HOME/certs/panel/panel.crt;
    ssl_certificate_key $PANEL_HOME/certs/panel/panel.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 256m;
    location / {
        proxy_pass http://127.0.0.1:$PANEL_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/hostpanel-admin.conf \
        /etc/nginx/sites-enabled/hostpanel-admin.conf
    nginx -t && systemctl reload nginx || true
fi

# --------------------------------- 2.5.5 ротация логов --------------------
cat > /etc/logrotate.d/hostpanel <<EOF
/var/log/hostpanel/*.log /var/log/hostpanel-cron/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
echo "==> Ротация логов панели и сайтов настроена (logrotate, 14 дней)"

# --------------------------------- 2.6 fail2ban: защита входа в панель ----
# Неудачные входы панель пишет в /var/log/hostpanel/auth.log — по нему
# fail2ban банит подборщиков пароля (8 попыток за 5 минут → бан на 10 мин).
if command -v fail2ban-client >/dev/null 2>&1; then
    mkdir -p /var/log/hostpanel
    touch /var/log/hostpanel/auth.log && chmod 640 /var/log/hostpanel/auth.log
    cat > /etc/fail2ban/filter.d/hostpanel.conf <<'EOF'
# HostPanel: неудачные входы в панель и hcp-login (пишет api/auth.py)
[Definition]
failregex = (?:cli-)?login-failed ip=<HOST>$
ignoreregex =
EOF
    cat > /etc/fail2ban/jail.d/hostpanel.local <<EOF
[hostpanel]
enabled = true
filter = hostpanel
logpath = /var/log/hostpanel/auth.log
port = $PANEL_TLS_PORT
maxretry = 8
findtime = 300
bantime = 600
ignoreip = 127.0.0.1/8 ::1
banaction = ufw
EOF
    fail2ban-client -t >/dev/null 2>&1 && systemctl restart fail2ban || true
    echo "==> fail2ban: защита входа в панель включена (8 попыток → бан)"
fi

# ------------------------------------------------------- 3. файлы панели ---
echo "==> Установка панели в $PANEL_HOME"
mkdir -p "$PANEL_HOME"
if [ -d "$SRC_DIR/panel" ]; then
    rm -rf "$PANEL_HOME/panel"
    cp -r "$SRC_DIR/panel" "$PANEL_HOME/panel"
else
    echo "ОШИБКА: рядом с install.sh нет папки panel/" >&2
    exit 1
fi
chmod -R go-w "$PANEL_HOME/panel"

# системный пользователь без оболочки — от него читаются файлы панели
if ! id -r hostpanel >/dev/null 2>&1; then
    useradd --system --home-dir "$PANEL_HOME" --shell /usr/sbin/nologin \
        hostpanel || true
fi
chown -R hostpanel:hostpanel "$PANEL_HOME" 2>/dev/null || true

# папка для страниц обслуживания (читается nginx)
mkdir -p "$PANEL_HOME/maintenance"

# ------------------------------------------- 3.5 консольный клиент hcp ----
# hcp и обёртки hcp-login, hcp-create, ... — управление панелью из шелла.
# Токен хранится в $PANEL_HOME/cli-token (0600), команды работают только
# с самого сервера и только от root.
if [ -f "$SRC_DIR/hcp" ]; then
    install -m 755 "$SRC_DIR/hcp" /usr/local/bin/hcp
    for c in login logout info status sites create site-remove \
             reset-password mail mail-pass db db-pass backup backups \
             cron cron-run services service-restart apps help; do
        printf '#!/bin/sh\nexec /usr/local/bin/hcp %s "$@"\n' "$c" \
            > "/usr/local/bin/hcp-${c}"
        chmod 755 "/usr/local/bin/hcp-${c}"
    done
    echo "==> Консольный клиент установлен: hcp-login (после входа — hcp-info)"
else
    echo "   предупреждение: файла hcp нет в дистрибутиве — CLI не установлен"
fi

# ----------------------------------------------------- 4. systemd-юнит ----
cat > /etc/systemd/system/hostpanel.service <<EOF
[Unit]
Description=HostPanel — панель управления хостингом
After=network.target nginx.service apache2.service mariadb.service

[Service]
Type=simple
# панель работает от root: управляет nginx/apache/php-fpm/systemd/mysql
ExecStart=/usr/bin/python3 -m panel --port $PANEL_PORT
WorkingDirectory=$PANEL_HOME
Environment=PYTHONPATH=$PANEL_HOME
Restart=on-failure
RestartSec=3
# ужесточение службы
NoNewPrivileges=no
PrivateTmp=yes
ProtectSystem=no
ProtectHome=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hostpanel >/dev/null
systemctl restart hostpanel

# ----------------------------------------------------------- 5. логи ------
mkdir -p /var/log/hostpanel

sleep 1
if systemctl is-active --quiet hostpanel; then
    echo ""
    echo "=============================================================="
    echo " HostPanel установлен и запущен!"
    echo " Адрес:   https://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):$PANEL_TLS_PORT"
    echo "          (самоподписанный сертификат — браузер предупредит;"
    echo "           локально и по SSH-туннелю: http://127.0.0.1:$PANEL_PORT)"
    echo " Логин:   admin"
    echo " Пароль:  cat $PANEL_HOME/admin.txt"
    echo " Службы:  nginx, Apache (:8081), PHP 8.3-FPM, MariaDB, Redis,"
    echo "          Memcached, fail2ban — управление: Система → Службы,"
    echo "          установка/удаление ПО: Система → Установка ПО"
    echo " Логи:    journalctl -u hostpanel -f"
    echo "=============================================================="
    echo " Рекомендуется сразу:"
    echo "  1) сменить пароль в Настройках (стандартный admin/admin)"
    echo "  2) включить двухфакторную аутентификацию (Настройки → Безопасность)"
    echo "  3) панель открывать по SSH-туннелю (порт $PANEL_PORT закрыт"
    echo "     снаружи брандмауэром):"
    echo "     ssh -L $PANEL_PORT:127.0.0.1:$PANEL_PORT user@server"
else
    echo "ОШИБКА: служба не запустилась, см. journalctl -u hostpanel -n 50" >&2
    exit 1
fi
