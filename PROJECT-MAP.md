
## 23. Итерация 2026-11-04 (ночь 2): GitHub, установка одной командой, самообновление

- **Репозиторий**: github.com/enikov1/hostPanel (main). В репо: panel/ (код +
  готовая сборка web/ — node для установки не нужен), web-src/ (исходники
  Vue), install.sh, uninstall.sh, hcp, VERSION, build-production.sh.
  Секреты и машинные файлы (deploy.sh, реквизиты, hostpanel-data/,
  production/, server-pull/) — в .gitignore. .gitattributes фиксирует LF
  для .sh/.py.
- **Установка одной командой** (как у HestiaCP): install.sh при отсутствии
  рядом panel/ сам скачивает архив репозитория с GitHub (curl/wget) и
  продолжает установку. `curl -o install.sh ... && sudo bash install.sh`
  или `git clone ... && sudo bash hostPanel/install.sh`.
- **Самообновление из панели**: core/panelupdate.py + API
  GET /api/panel/update (текущая vs версия на GitHub по raw VERSION,
  сравнение числовых сегментов) и POST /api/panel/update/run — фоновая
  задача: скачать main.tar.gz, проверить состав, бэкап в
  /opt/hostpanel/panel.bak-<метка> (хранятся последние 3), замена файлов,
  рестарт через threading.Timer(2.0) — чтобы успеть отдать ответ. В демо
  запрещено. UI: карточка «Обновления панели» в Настройках (проверка,
  кнопка обновления, живой лог) + индикатор «⬆ доступна vX.Y.Z» в подвале
  сайдбара.
- **Проверено живьём**: панель 2.16.0 на сервере обнаружила 2.16.1 в GitHub,
  обновилась сама и перезапустилась (panel.bak-... создан).
- build-production.sh: источник кода — panel/ из репо (не server-pull),
  фронтенд — web-src/.

## 22. Итерация 2026-11-04 (ночь): сборка production-дистрибутива

- `build-production.sh` — одна команда собирает `C:\hostpanel\production`:
  установщики (install.sh, uninstall.sh, hcp, VERSION, README) + `panel/`
  (код Python без __pycache__/.bak + свежая сборка фронтенда в `panel/web`)
  + архив `hostpanel-<версия>.tar.gz` — одним файлом на сервер.
- Установка на чистый сервер: `scp production/hostpanel-*.tar.gz root@IP:/root/`
  → `tar xzf` → `bash install.sh`. Пароль админа: `cat /opt/hostpanel/admin.txt`.
- Состав архива сверён с работающей панелью на сервере (diff — нулевой).
- Фикс вёрстки: Vue монтировался в `#app`, на который в app.css завязан
  каркас (display:flex) — экраны сжимались и липли влево. Точка монтирования
  переименована в `#ui`, оболочка рендерит `#app` как в исходной вёрстке.

## 21. Итерация 2026-11-04 (вечер): новый фронтенд на Vue 3 — реальные URL без #решётки

- **Полная замена фронтенда**: string-HTML TypeScript (ts-src, ~300 КБ, сборка
  через tsc + Prism-vendor) заменён на Vue 3 + Vite + vue-router
  (TypeScript, `<script setup>`). Все 15 разделов перенесены 1:1:
  Обзор / Живучесть / Службы / Сайты + карточка сайта (вкладки) / Базы
  данных / Почта / Файлы / Бэкапы / Планировщик / Установка ПО / Настройки
  ПО / Пакеты / Брандмауэр / Терминал / Настройки панели.
- **Реальные URL** (history mode, SPA-fallback в server.py): `/`,
  `/health`, `/services`, `/sites`, `/sites/<id>`, `/databases`, `/mail`,
  `/files`, `/backups`, `/cron`, `/software`, `/software/settings`,
  `/packages`, `/firewall`, `/terminal`, `/settings`. Карточка сайта —
  отдельная страница вместо модалки. Хеш-навигация `#` убрана полностью.
- **server.py**: serve_static отдаёт `/assets/*` (хеш в имени, Cache-Control
  immutable) и index.html на любой страничный путь; `/api/*` и `/status`
  работают как раньше. Бэкап старого фронтенда: `panel/web-backup-old`.
- **Кит UI** (panel/web-src/src/components): AppModal (locked/wide), confirm
  (глобальный), PwField, CredRow, StatCard, CodeEditor (Prism через npm),
  UiIcon, ToastHost; либы: toast с «объяснителями» ошибок, форматтеры,
  графики на canvas (линия + uptime), темы, clipboard.
- **Найдено при прогоне**: ForcePwModal вычислял isDefault при монтировании,
  а не при открытии — исправлено (computed); ToastHost не был подключён в
  App.vue — добавлен.
- Версия 2.15.0. Демо-прогон (Windows, python -m panel --demo): вход, смена
  пароля, все 13 маршрутов + карточка /sites/1 отрисованы. Боевой сервер
  проверен через SSH-туннель: вход, /sites с живыми сайтами, выход.

## 20. Итерация 2026-11-04 (вторая половина): вход, SSL/www, GeoIP2, pma, настройки ПО

- **Экран входа**: футер удалён, в шапке только «HostPanel vX.Y.Z» (версия
  приходит в /api/login-state → поле version). Локальная копия ts-src
  перенесена в /opt/hostpanel/panel/web-src (там же сборка: npm i
  typescript + ./build.sh, node 22 на сервере).
- **SSL**: certbot вызывается с --expand — больше не падает вопросом
  «expand and replace?» при существующем сертификате. www добавляется в
  SAN и server_name ТОЛЬКО при флаге www у сайта (галочки в мастере
  создания и в «Основном» сайта; сниппет «редирект www → без www» тоже
  включает www в server_name). core/templates.site_server_names() —
  единая точка. Для существующих сайтов флаг по умолчанию выключен.
- **GeoIP2 через «Установка ПО»**: элемент каталога geoip2 (группа «SSL и
  безопасность») ставит libnginx-mod-http-geoip2 и скачивает свежий
  GeoLite2-Country.mmdb из автообновляемого зеркала P3TERX/GeoLite.mmdb
  (официальная раздача MaxMind требует ключа, download.dbip.com из РФ не
  резолвится), кладёт /etc/cron.monthly/hostpanel-geodb для ежемесячного
  обновления. software.item_status умеет provide_files. В «Безопасности»
  сайта — кнопка установки без ухода со страницы.
- **phpMyAdmin**: диалог показывался и для неустановленного pma, «Открыть
  в новом окне» звал window.open(undefined) → пустая вкладка. Теперь
  диалог проверяет installed, window.open(url,'_blank','noopener').
- **Настройки ПО**: страница перестроена в плитки по группам; настройки
  каждого модуля — в модальном окне (поля + пароли + конфиги). Добавлены
  записи PHP X.Y (FPM) для каждой установленной версии: ключевые
  директивы php.ini (memory_limit, upload/post size, max_execution_time,
  max_input_vars, display_errors, opcache.enable, date.timezone) с
  чтением/правкой файла, дубли гасятся, отсутствующее дописывается после
  [PHP]; при сохранении перезапуск FPM с откатом. Проверено round-trip на
  php8.2.
