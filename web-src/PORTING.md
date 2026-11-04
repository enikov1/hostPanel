# Портирование страниц HostPanel на Vue 3

Контекст: панель управления хостингом. Старый фронтенд — TypeScript, который
генерирует HTML-строки + inline onclick (глобальный реестр). Портируем на
Vue 3 + Vite + vue-router (history mode, реальные URL).

## Куда класть код

- Раздел-страница = `src/views/<Имя>View.vue` (уже созданы заглушки).
- Подкомпоненты конкретного раздела (вкладки, крупные диалоги) — в
  `src/views/<razdel>/…` рядом, например `src/views/site/TabSsl.vue`.
- НЕ менять: `src/lib/*`, `src/api/client.ts`, `src/router.ts`, `src/stores.ts`,
  `src/layouts/Shell.vue`, `src/App.vue`, `src/components/*` (кит),
  `src/app.css`. Разделам ЗАПРЕЩЕНО редактировать глобальный CSS — при
  острой нужде используйте scoped-стили в своём SFC.

## Кит (всё уже написано — используйте, не дублируйте)

```ts
import { api, apiForm, downloadFile } from '../api/client';   // path 'src/api/client.ts'
import { toast, toastErr } from '../lib/toast';               // toast(msg, 'ok'|'err'|'warn')
import { confirmDlg } from '../lib/confirm';                  // confirmDlg(title, text, onOk, danger=true)
import { esc, fmtSize, fmtDate, humanUptime, humanRel, cronHuman } from '../lib/format';
import { genPassword, pwStrength } from '../lib/pw';
import { copyText } from '../lib/clipboard';                  // copyText(text, btnEl?)
import { drawLine, drawUptime, cssVar } from '../lib/charts'; // Series{data,color,fill?}, LineOptions{max?,labels?}, UptimePoint{ok,ms}
import { me, session } from '../stores';                      // me.expert, me.demo, me.version, me.home, me.www_root — reactive
import { useRouter, useRoute } from 'vue-router';
```

Компоненты (`src/components/`):

- `<UiIcon name="globe" :size="17" />` — SVG-иконка; имена: zap, menu, moon, sun,
  bell, logout, globe, db, folder, archive, lock, clock, shield, activity, file,
  gear, plus, x, check, refresh, down, up, trash, edit, ext, server, cpu, play,
  stat, wrench, pkg, pause, term.
- `<AppModal :open="dlg" :title="..." :wide="false|true|'xwide'" :locked="false" @close="dlg=false">`
  — слоты: default (тело), `footer` (кнопки). Всегда закрывать через `@close`/кнопки.
- `<PwField v-model="pw" label="Пароль" :gen="true" hint="..." />`
- `<CredRow :k="Ключ" :v="значение" />` — строка с кнопкой копирования.
- `<StatCard ic="cpu" cls="warn" :val="x" label="..." :bar-pct="null|число" bar-cls="..." />`
- `<CodeEditor v-model="text" lang="nginx|ini|apacheconf|php|sql|..." />` — Prism-редактор.

Правило шаблона: `v-model` на инпутах, `@click` на кнопках; никаких inline-строк
HTML. Для текстов с разметкой, приходящих с сервера (SVG QR-кода и т.п.) —
`v-html` точечно.

## Правила портирования

1. **Функциональность 1:1**: все вкладки, кнопки, диалоги, фильтры, валидации,
   тексты (русский), API-эндпоинты и порядок вызовов сохраняются. Это перенос,
   а не редизайн. Визуальные классы из `app.css` использовать те же
   (`.card`, `.btn`, `.btn.primary`, `.btn.danger`, `.btn.sm`, `.btn.icon`,
   `.row`, `.grid-2`, `.kv`, `.notice ok|warn|err`, `.pill`, `.mono`, `.muted`,
   `.faint`, `.field`, `.table-wrap`, `.empty`, `.bar`, `.stat`, `.tabs`,
   `.tab`, `.crumbs`, `.cred-row`, `.toast`, `.login-*`, `.bd-h`, `.bell-item` …
   смотрите существующие usages и app.css).
2. Таблицы: оберните корень страницы в `<div v-table>` — директива расставляет
   `data-l` для мобильной адаптации.
3. Загрузка данных: `onMounted` + функция `load()`; поллинг — `setInterval` с
   обязательным `onBeforeUnmount(clearInterval)`. Таймеры/AbortController для
   «живых» логов тоже чистить.
4. Модалки = `ref(false)` + `<AppModal>`; confirm — глобальный `confirmDlg`.
5. Навигация: внутри раздела — локальное состояние; между разделами —
   `<router-link>`/`router.push` с реальными URL (`/sites/12`, `/databases`…).
   Названия разделов: Обзор `/`, Живучесть `/health`, Службы `/services`,
   Сайты `/sites`, Базы данных `/databases`, Почта `/mail`, Файлы `/files`,
   Резервные копии `/backups`, Планировщик `/cron`, Установка ПО `/software`,
   Настройки ПО `/software/settings`, Пакеты `/packages`, Брандмауэр `/firewall`,
   Командная строка `/terminal`, Настройки `/settings`.
6. `/api/site/:sid/*` — `:sid` числовой id сайта.
7. Скачивания (бэкапы, дампы, файлы) — через `downloadFile(url, name)`.
8. Мультиселекты/фильтры логов — port как есть, включая сохранение в
   localStorage если оно было.
9. `me.expert` — показывать экспертные функции, `me.demo` — демо-режим (баннер).
10. Файл исходника читайте ПОЛНОСТЬЮ и переносите каждый обработчик. Ничего не
    выбрасывать без функционального эквивалента.

## Пример стиля (как писать)

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import { fmtSize } from '../../lib/format';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';

const items = ref<any[]>([]);
const dlg = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;

async function load(): Promise<void> {
  try { const d = await api('/api/xxx'); items.value = d.items || []; }
  catch (e) { /* экран уже открыт — тихо */ }
}
onMounted(() => { load(); timer = setInterval(load, 5000); });
onBeforeUnmount(() => { if (timer) clearInterval(timer); });
</script>
```

## Проверка

`cd C:\hostpanel\vue-src && npm run build` — должен проходить без ошибок TS
(vue-tsc строгий: типизируйте refs, `$event.target as HTMLInputElement` и т.п.).
