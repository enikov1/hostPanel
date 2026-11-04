# Задание: фиксы находок бэкенд-ревью (P2/P3)

Панель: C:\hostpanel\panel\ (Python 3.8+ stdlib, ThreadingHTTPServer,
STATE_LOCK = threading.RLock из context.py — общий замок на обработку
API-запроса). Уже исправлено (НЕ трогать): security.py дубль apply_security,
sites.py валидация update (webserver/php/fpm/node) + zip-slip + run import,
state.py _Flock реентерабельность, panelupdate.py locks+extract guard,
sites.py _reissue под STATE_LOCK.

## Исправить:

1. **core/health.py snapshot_disk** (строка ~24): мутирует state и save()
   без STATE_LOCK — обернуть тело в `with STATE_LOCK:` (импорт уже есть
   или добавьте from ..context import CTX, STATE_LOCK).

2. **server.py handle_login** (~строка 421): `creds["must_change_password"]`
   + `store.save()` вне STATE_LOCK — обернуть в `with STATE_LOCK:`.

3. **core/security.py + api/sites.py save_security**: WAF-инъекция через
   `;` и `}` в UA-паттернах: в save_security валидация отвергает только
   `"` `\` `{` — добавьте запрет `;`, `}`, `\r`, `\n`. В core/security.py
   `_ua_lines_for`/`_ref_lines_for` добавьте такой же фильтр (пропуск
   строк с `;`, `}`, кавычками — defensive). В `_ref_lines_for` экранируйте
   точку домена: `%s` в regex — домен `spam.site.com` матчит любой символ —
   замените точки на `\\.` перед подстановкой.

4. **panelupdate.py status()**: блокирующий urlopen (до 8 сек) выполняется
   в request-потоке под STATE_LOCK — панель замерзает на каждый опрос.
   Кеш: module-var `_last_check = [0.0, ""]` (ts, version); если свежее
   300 сек — использовать кеш; иначе fetch и обновить кеш (fetch вне
   общего STATE_LOCK — он и так выполняется до `with LOCK` в status(),
   но с кешем будет редко).

5. **api/security.py** — мёртвый дубль старого security.py (не
   импортируется) — УДАЛИТЬ файл. Проверьте grep: `from .api import security`
   / `api.security` нигде. Если импортируется — не удалять, сообщить.

6. **core/security.py security_status**: не знает про geo_allow/geo_deny —
   добавьте ветки (только из: … / кроме: …) по новым полям (мигрируйте
   через geo_lists(sec)) и упоминание ua_categories/ua_rules/ref_block
   если их ещё нет.

7. **api/mail.py mail_dkim_generate** (~строка 140): валидация домена
   пропускает `..` → path traversal при записи ключа. Добавьте
   `utils.valid_domain(domain)` + явный запрет '..'.

8. **api/manage.py firewall_add**: `proto` не валидируется (любая строка
   уходит в ufw) — проверяйте `proto in ("tcp", "udp")` (ufw синтаксис:
   proto указывается один раз; если 'both' — вызывайте без proto);
   диапазон портов `8000:99999` — проверяйте ОБА конца на 1–65535.

9. **P3-батч**:
   - api/sites.py создание сайта/поддомена: id `int(time.time()*1000) % 1e9`
     — коллизии; замените на `random`/`secrets.token_hex`-подобный
     уникальный int (или глобальный счётчик с time).
   - api/sites.py stats/log handlers: `int(qs[...])` без try → 500 при
     мусоре в query; оберните try → err("некорректный параметр", 400).
   - server.py: заголовок X-Real-IP от loopback валидируйте
     utils.valid_ip (иначе мусор в LOGIN_FAILS).
   - api/sites.py save_security: `if "geo_allow" in updates:` перезаписывает
     ОБА списка одним условием — обновляйте каждый список при наличии
     СВОЕГО ключа.
   - api/manage.py upload/db_import: при превышении MAX_UPLOAD_BODY
     (`handler._oversized`) возвращайте err("файл слишком большой", 413).
   - api/general.py metrics: глобальный `_METRICS` мутируется из разных
     потоков — threading.Lock.
   - НЕ удаляйте panel/general.py пока (проверьте grep «import general»
     по panel/ — если никто не импортирует, удалите; если импортируется —
     не трогайте).

## Правила
- py_compile в конце: `cd C:\hostpanel && python -m py_compile panel/*.py panel/api/*.py panel/core/*.py` — OK.
- НЕ трогать frontend, ui, router.
- Отчитайтесь: исправлено/пропущено по пунктам.
