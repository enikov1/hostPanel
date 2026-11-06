# -*- coding: utf-8 -*-
"""Глобальные константы HostPanel: пути, лимиты, справочники.

Ничего кроме констант здесь нет — модуль импортируется всеми остальными
и не должен зависеть от состояния выполнения.
"""
import os

VERSION = "2.23.1"
PANEL_NAME = "HostPanel"

# --- пути -------------------------------------------------------------
DEFAULT_HOME = "/opt/hostpanel"     # рабочая папка панели (по умолчанию)
WWW_ROOT = "/var/www"               # корень сайтов в рабочем режиме
REAL_LOGS_DIR = "/var/log/hostpanel"  # логи сайтов в рабочем режиме
CRON_LOG_DIR = "/var/log/hostpanel-cron"  # журналы вывода cron-задач
PMA_HTPASSWD_DIR = "/etc/nginx/hostpanel-pma"  # basic-auth phpMyAdmin
# заглушка для IP-адреса сервера: отдаётся с кодом 404 и noindex,
# редактируется из панели (страница «Сайты»)
DEFAULT_SITE_DIR = os.path.join(DEFAULT_HOME, "default-site")

# стартовое содержимое заглушки (используется install.sh и панелью)
DEFAULT_PLACEHOLDER_HTML = """<!DOCTYPE html>
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
"""

# --- уведомления (e-mail / Telegram) --------------------------------------
NOTIFY_TIMEOUT = 15                 # сек — таймаут отправки одного канала

# каталог веб-интерфейса (html/css/js) внутри пакета
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# --- ограничения (безопасность) ----------------------------------------
SESSION_TTL = 8 * 3600              # бездействие до автоматического выхода, сек
LOGIN_MAX_FAILS = 8                 # попыток входа с одного IP за окно
LOGIN_FAIL_WINDOW = 300             # окно ограничения входа, сек
MAX_JSON_BODY = 5 * 1024 * 1024     # максимум JSON-тела запроса
MAX_UPLOAD_BODY = 200 * 1024 * 1024  # максимум загружаемого файла
MAX_LOG_READ = 2_000_000            # сколько байт лога читаем для фильтрации
EDITOR_MAX_FILE = 1_500_000         # максимум файла для редактора
HEALTH_DEFAULT_INTERVAL = 60        # период проверок живучести, сек
HEALTH_TIMEOUT = 10                 # таймаут одной проверки, сек

# --- PHP: справочник модулей и демо-наборы -----------------------------
PHP_MODULE_RU = {
    "curl": "curl — HTTP-запросы", "gd": "gd — изображения",
    "mbstring": "mbstring — строки UTF-8", "mysqli": "mysqli — MySQL",
    "pdo_mysql": "pdo_mysql — MySQL (PDO)", "xml": "xml — XML",
    "zip": "zip — архивы", "openssl": "openssl — шифрование",
    "intl": "intl — локализация", "imagick": "imagick — ImageMagick",
    "opcache": "opcache — кэширование байткода", "redis": "redis — кэш Redis",
    "soap": "soap — SOAP-сервисы", "xsl": "xsl — XSLT",
    "bcmath": "bcmath — длинная арифметика", "sqlite3": "sqlite3 — SQLite",
    "pgsql": "pgsql — PostgreSQL", "ldap": "ldap — LDAP-каталоги",
    "imap": "imap — почтовые протоколы", "exif": "exif — метаданные фото",
    "memcached": "memcached — кэш", "amqp": "amqp — очереди RabbitMQ",
    "yaml": "yaml — YAML", "gnupg": "gnupg — GnuPG",
    "ssh2": "ssh2 — SSH/SFTP", "tidy": "tidy — HTML-очистка",
}

DEMO_PHP = {
    "8.3": ["bcmath", "calendar", "ctype", "curl", "dom", "fileinfo", "filter",
            "ftp", "gd", "gettext", "iconv", "intl", "json", "libxml",
            "mbstring", "mysqli", "mysqlnd", "openssl", "pcntl", "pcre",
            "PDO", "pdo_mysql", "pdo_sqlite", "Phar", "posix", "readline",
            "session", "SimpleXML", "soap", "sockets", "sodium", "SPL",
            "sqlite3", "tokenizer", "xml", "xmlreader", "xmlwriter", "xsl",
            "zip", "zlib"],
    "8.2": ["bcmath", "calendar", "ctype", "curl", "dom", "exif", "fileinfo",
            "filter", "ftp", "gd", "gettext", "iconv", "imagick", "intl",
            "json", "libxml", "mbstring", "mysqli", "mysqlnd", "openssl",
            "opcache", "pcntl", "pcre", "PDO", "pdo_mysql", "pdo_sqlite",
            "Phar", "posix", "redis", "session", "SimpleXML", "soap",
            "sockets", "sodium", "SPL", "sqlite3", "tokenizer", "xml",
            "xmlreader", "xmlwriter", "xsl", "zip", "zlib"],
    "8.1": ["bcmath", "calendar", "ctype", "curl", "dom", "fileinfo", "filter",
            "ftp", "gd", "iconv", "intl", "json", "libxml", "mbstring",
            "mysqli", "openssl", "opcache", "pcre", "PDO", "pdo_mysql",
            "Phar", "posix", "session", "SimpleXML", "sockets", "SPL",
            "sqlite3", "tokenizer", "xml", "xmlwriter", "xsl", "zip", "zlib"],
    "7.4": ["calendar", "ctype", "curl", "dom", "fileinfo", "filter", "ftp",
            "gd", "hash", "iconv", "json", "libxml", "mbstring", "mysqli",
            "openssl", "pcre", "PDO", "pdo_mysql", "Phar", "posix", "session",
            "SimpleXML", "SPL", "sqlite3", "tokenizer", "xml", "xmlwriter",
            "zip", "zlib"],
}
DEMO_NODE = ["18", "20", "22"]

# --- страны для гео-фильтров (ISO 3166-1 alpha-2) ----------------------
COUNTRIES = {
    "RU": "Россия", "UA": "Украина", "BY": "Беларусь", "KZ": "Казахстан",
    "UZ": "Узбекистан", "KG": "Киргизия", "AM": "Армения", "AZ": "Азербайджан",
    "GE": "Грузия", "MD": "Молдова", "TJ": "Таджикистан", "TM": "Туркмения",
    "DE": "Германия", "FR": "Франция", "GB": "Великобритания", "IT": "Италия",
    "ES": "Испания", "PT": "Португалия", "NL": "Нидерланды", "BE": "Бельгия",
    "AT": "Австрия", "CH": "Швейцария", "SE": "Швеция", "NO": "Норвегия",
    "FI": "Финляндия", "DK": "Дания", "PL": "Польша", "CZ": "Чехия",
    "SK": "Словакия", "HU": "Венгрия", "RO": "Румыния", "BG": "Болгария",
    "GR": "Греция", "HR": "Хорватия", "RS": "Сербия", "LT": "Литва",
    "LV": "Латвия", "EE": "Эстония", "IE": "Ирландия", "IS": "Исландия",
    "TR": "Турция", "CY": "Кипр", "MT": "Мальта", "LU": "Люксембург",
    "US": "США", "CA": "Канада", "MX": "Мексика", "BR": "Бразилия",
    "AR": "Аргентина", "CL": "Чили", "CO": "Колумбия", "PE": "Перу",
    "CN": "Китай", "JP": "Япония", "KR": "Южная Корея", "IN": "Индия",
    "ID": "Индонезия", "VN": "Вьетнам", "TH": "Таиланд", "SG": "Сингапур",
    "MY": "Малайзия", "PH": "Филиппины", "HK": "Гонконг", "TW": "Тайвань",
    "IL": "Израиль", "AE": "ОАЭ", "SA": "Саудовская Арабия", "QA": "Катар",
    "IR": "Иран", "IQ": "Ирак", "EG": "Египет", "ZA": "Южная Африка",
    "NG": "Нигерия", "KE": "Кения", "MA": "Марокко", "TN": "Тунис",
    "AU": "Австралия", "NZ": "Новая Зеландия",
}

# --- WAF и боты (регулярные выражения nginx) ---------------------------
BAD_BOTS_RE = (r"~*(?:bot|crawler|spider|scraper|curl|wget|python-requests"
               r"|scrapy|zgrab|masscan|nikto|sqlmap|havij|dirbuster)")
WAF_ARGS_RE = (r"(?:union[\s+]select|select[\s+].+[\s+]from|insert[\s+]into"
               r"|drop[\s+]table|benchmark\(|sleep\(|<script|javascript:"
               r"|onerror=|onload=|document\.cookie|\.\./\.\.)")
WAF_PATHS_RE = (r"(?:^|/)(?:\.git|\.svn|\.hg|\.env|\.htaccess|\.htpasswd"
                r"|wp-config\.php|phpinfo\.php|composer\.json|\.aws)"
                r"(?:/|$)")

# --- WAF: категории ботов для выборной блокировки ------------------------
# id -> (regex без модификатора, человекочитаемое название, описание)
# Regex подставляется в nginx map как ~*<regex>; составлен без спецкавычек.
BOT_CATEGORIES = {
    "scanners": (r"sqlmap|nikto|nmap|masscan|acunetix|nessus|openvas|"
                 r"dirbuster|gobuster|wpscan|arachni|w3af|havij|zgrab",
                 "Сканеры уязвимостей",
                 "Инструменты поиска дыр: sqlmap, nikto, WPScan и подобные. "
                 "Ломаются к сайту постоянно — блокировать почти всегда стоит."),
    "abuse": (r"semrush|ahrefs|mj12bot|dotbot|petalbot|serpstatbot|blexbot|"
              r"megaindex|backlinkspy|linkdex",
              "SEO-парсеры и abuse-боты",
              "Парсеры позиций и обратных ссылок: нагружают сайт, пользы "
              "посетителям не приносят."),
    "ai": (r"GPTBot|ClaudeBot|Claude-Web|CCBot|anthropic-ai|PerplexityBot|"
           r"Google-Extended|Bytespider|ImagesiftBot|cohere-ai|omgili",
           "ИИ-сборщики данных",
           "Боты языковых моделей (ChatGPT, Claude, Gemini и др.) — обучают "
           "модели на вашем контенте без ссылок на источник."),
    "http_tools": (r"python-requests|python-urllib|Go-http-client|Java/|"
                   r"libwww|scrapy|httpclient|okhttp|dart:io",
                   "HTTP-инструменты (без браузера)",
                   "Запросы из скриптов и библиотек без браузерного "
                   "User-Agent. Осторожно: это же могут слать ваши API-"
                   "клиенты и мониторинги."),
    "headless": (r"headlesschrome|phantomjs|puppeteer|playwright",
                 "Headless-браузеры",
                 "Браузеры без интерфейса — так работают скулпуллеры и "
                 "накрутчики поведенческих факторов."),
}
# хорошие роботы — они не должны блокироваться категориями «подряд»
SEARCH_ENGINE_RE = (r"Googlebot|bingbot|DuckDuckBot|YandexBot|Baiduspider|"
                    r"YandexImages|YandexMetrika|Applebot|Feedfetcher")

# --- файловый менеджер: разрешённые корни в рабочем режиме --------------
def fm_roots(panel_home):
    """Каталоги, доступные файловому менеджеру (рабочий режим)."""
    return [
        WWW_ROOT, panel_home, REAL_LOGS_DIR,
        "/etc/nginx", "/etc/apache2", "/etc/php", "/etc/systemd/system",
        "/etc/mysql", "/etc/letsencrypt",
    ]


def fm_roots_demo(panel_home):
    """В демо-режиме доступна только домашняя папка панели."""
    return [panel_home]
