# ТЗ 3: Настройки уведомлений (типы событий) + кнопка бэкапа сайта в списке

Файлы: C:\hostpanel\web-src\src\views\SettingsView.vue (уведомления — таб
«Уведомления»), C:\hostpanel\web-src\src\views\SitesView.vue (кнопка бэкапа
в строке сайта). Не трогать другие файлы.

## 1. Уведомления — выбор типов событий

Бэкенд готов:
- GET /api/settings → settings.notify.events = {site_down, site_recover,
  backup, cert, password, security} (bool; отсутствующий ключ = включено).
- POST /api/settings/save body { notify_events: {site_down: true, ...} }
  (ключи: site_down, site_recover, backup, cert, password, security).

В карточке «Уведомления о проблемах» (с логотипами mail/telegram — уже есть)
переименуйте в «Уведомления» и добавьте:
- Секцию «Что отправлять» — список событий (UiCheckbox на каждое):
  site_down — «Сайт недоступен», site_recover — «Сайт восстановился»,
  backup — «Резервные копии (создание/восстановление)», cert —
  «Сертификаты (перевыпуск, истечение)», password — «Смена паролей и
  реквизитов», security — «Безопасность: входы в панель, fail2ban»
  (этот чекбокс заменяет/дублирует текущий ntSec — объедините: ntSec при
  сохранении пишет notify.security.enabled; теперь единый источник —
  notify_events.security; обновите settingsSave соответственно).
- Логика: чекбоксы событий читают/пишут локальный reactive объект
  notifyEvents (из GET /api/settings → settings.notify.events, отсутствующий
  ключ = true); settingsSave() добавляет notify_events в body (все 6 ключей).
- Подпись: «Выберите, о чём сообщать. Каналы (e-mail/Telegram) настраиваются
  галочками ниже — события шлются во все включённые каналы.»

## 2. Кнопка «Сделать бэкап» в строке сайта (SitesView)

- В actions-cell каждой строки (корневой) добавить кнопку «⬇ Бэкап»
  (UiIcon name="archive", размер 14): POST /api/backups/create
  {site_ids: [s.id], with_db: true} → toast «Резервная копия создана:
  <размер>» + предложение перейти в /backups (тост достаточно).
- В подтверждении не нуждается (не деструктивное), но во время выполнения —
  :disabled и текст «Создаю…».
- Также для строк поддоменов (children) — та же кнопка.
- Проверьте, что существующий функционал строк не сломался.

## Сборка
`cd C:\hostpanel\web-src && npm run build` — 0 ошибок. Отчитайтесь по пунктам.
