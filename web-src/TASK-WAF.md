# ТЗ: вкладка «Фильтры» карточки сайта → полноценный WAF-модуль

Переработать `C:\hostpanel\web-src\src\views\site\TabSecurity.vue`.
Бэкенд УЖЕ готов (panel/api/sites.py + panel/core/security.py) — ниже API.
Файл большой, редактируйте целиком; логику secAddIp/secRemoveIp/secSave
адаптируйте под новую схему. Сборка в конце обязательна:
`cd C:\hostpanel\web-src && npm run build`.

## API

### GET /api/site/:sid/security →
```json
{
  "security": {
    "geo_allow": ["BY"], "geo_deny": ["RU"],
    "ip_allow": [], "ip_deny": [],
    "block_bots": false, "waf": false,
    "rate_limit": 0, "rate_burst": 20,
    "ua_categories": ["scanners", "ai"],
    "ua_rules": [{"pattern": "semrush", "note": "SEO-парсер"}],
    "block_empty_ua": false,
    "ref_block": ["spam-site.com"], "ref_allow": [],
    "block_empty_ref": false
  },
  "countries": {"RU": "Россия", "BY": "Беларусь", ...},
  "bot_categories": {
    "scanners": {"name": "Сканеры уязвимостей", "desc": "..."},
    "abuse": {"name": "SEO-парсеры и abuse-боты", "desc": "..."},
    "ai": {"name": "ИИ-сборщики данных", "desc": "..."},
    "http_tools": {"name": "HTTP-инструменты (без браузера)", "desc": "..."},
    "headless": {"name": "Headless-браузеры", "desc": "..."}
  }
}
```

### POST /api/sites/security  body: {id, security: {...}}
Отправляйте НОВУЮ схему (geo_allow/geo_deny — НЕ geo_mode/geo_countries;
оба списка пусты = фильтр стран выключен). Ключи: geo_allow, geo_deny,
ua_categories, ua_rules (массив {pattern, note}), block_empty_ua,
ref_block, ref_allow, block_empty_ref, ip_allow, ip_deny, block_bots, waf,
rate_limit, rate_burst.

### GET /api/site/:sid/stats?days=30 →
`stats.top_uas` = [[userAgent, count]...], `stats.top_refs` =
[[домен, count]...] — для блока «Анализ из логов».

## Требования к UI (все группы — карточки .card с .card-h, описания .faint)

1. **Карточка «Доступ по странам»**:
   - Два отдельных списка: «Разрешённые страны» (зелёные chip) и
     «Запрещённые страны» (красные chip). Их можно КОМБИНИРОВАТЬ
     (бэкенд проверяет независимо). Пусты оба = фильтр выключен.
   - Каждому списку — свой добавляющий селект. Страна выбирается через
     **кастомный поиск**: инлайн-компонент в этом файле (не глобальный) —
     поле ввода + выпадающий список стран (name+code), фильтрация по
     подстроке (по коду и названию), у каждой страны ФЛАГ-эмодзи
     (flagEmoji(code) = String.fromCodePoint(...[...'CC'].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))).
     Не добавлять страну дважды; chip с флагом и × на удаление.
   - Если списки пусты — плашка «гео-фильтр выключен».
   - Если бэкенд вернёт отсутствие geoip2 (в security-ответе поля нет —
     оставьте прежнюю логику с кнопкой установки из старого файла, она
     проверялась через /api/geo... — просто перенесите старую проверку
     `geoAvailable` и кнопку secGeoInstall как было).
2. **Чёрный/Белый список IP** — как в текущей версии (две карточки рядом,
   .split), не потерять.
3. **Карточка «Боты и User-Agent»**:
   - Пять категорий из bot_categories: чекбокс-карточки (UiCheckbox) с
     названием, описанием (desc) и иконкой UiIcon: scanners→wrench,
     abuse→down, ai→cpu, http_tools→term, headless→pause.
   - Свои правила: список {pattern, note} + форма добавления
     (поле pattern — «regex или подстрока», поле note). Удаление ×.
   - Чекбокс «Блокировать запросы без User-Agent».
   - Примечание: поисковые роботы (Googlebot, YandexBot…) никогда не
     блокируются категориями — упомянуть текстом.
4. **Карточка «Источники (Referer)»**:
   - ref_block (чипы с × + поле добавления, например spam-site.com),
     ref_allow (белый список), чекбокс «Блокировать запросы без Referer».
5. **Блок «Анализ из логов»** (синхронизация с логами):
   - При открытии вкладки загрузить /stats?days=30.
   - Секция «Top User-Agent (30 дней)»: строки UA + счётчик + кнопка
     «Блок» (добавляет в ua_rules c note='из логов'; для ботов-категорий
     можно подсказать категорию). Секция «Top источники»: домен + счётчик +
     «Блок» (добавляет в ref_block).
   - Кнопка «Обновить анализ».
6. **Автоматическая защита** (старая карточка с block_bots и waf) —
   оставить с описаниями (как сейчас).
7. **Ограничение частоты** — оставить как есть.
8. Кнопка «Применить правила» внизу + пояснение (как сейчас).

## Правила

- Скрипт-логика: state под новую схему; страна-функции для двух списков.
- Не трогать другие файлы, ui/*, app.css. Сборка в конце — 0 ошибок.
