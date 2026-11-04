<script setup lang="ts">
/* ============ Страница: Планировщик (cron) + выбор файла ============ */
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { cronHuman } from '../lib/format';
import { nextRunCron } from '../lib/cronNext';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import UiSelect from '../components/ui/UiSelect.vue';
import UiCheckbox from '../components/ui/UiCheckbox.vue';
import FilePickerModal from './cron/FilePickerModal.vue';

interface CronJob { expr: string; command: string; comment?: string; enabled: boolean }
interface SiteRow { domain: string; docroot: string }
interface LastRun { code: number; at: Date }
interface CronTemplate { icon: string; title: string; desc: string; expr: string; command: string; comment: string }

const CRON_PRESETS: [string, string][] = [
  ['* * * * *', 'каждую минуту'],
  ['*/5 * * * *', 'каждые 5 минут'],
  ['*/10 * * * *', 'каждые 10 минут'],
  ['*/15 * * * *', 'каждые 15 минут'],
  ['*/30 * * * *', 'каждые 30 минут'],
  ['0 * * * *', 'каждый час'],
  ['0 */2 * * *', 'каждые 2 часа'],
  ['0 */6 * * *', 'каждые 6 часов'],
  ['0 3 * * *', 'каждый день в 03:00'],
  ['0 3 * * 0', 'по воскресеньям в 03:00'],
  ['0 3 1 * *', '1-го числа в 03:00'],
];

/* ---- готовые задачи в один клик ---- */
const TEMPLATES: CronTemplate[] = [
  { icon: 'archive', title: 'Ежедневный бэкап всех сайтов', desc: 'Копия всех сайтов и баз раз в сутки',
    expr: '0 3 * * *', command: 'hcp-backup --all', comment: 'Ежедневный бэкап всех сайтов' },
  { icon: 'file', title: 'Еженедельная очистка старых логов', desc: 'Сжатые логи старше 30 дней удаляются',
    expr: '0 4 * * 0', command: "find /var/log/hostpanel -name '*.gz' -mtime +30 -delete",
    comment: 'Еженедельная очистка старых логов' },
  { icon: 'pkg', title: 'Очистка кеша apt', desc: 'Освобождает место на диске по воскресеньям',
    expr: '0 5 * * 0', command: 'apt-get clean', comment: 'Очистка кеша apt по воскресеньям' },
  { icon: 'globe', title: 'Проверка доступности сайта', desc: 'Проверка каждые 5 минут — впишите свой домен вместо СУБДОМЕН',
    expr: '*/5 * * * *', command: 'curl -fsS http://СУБДОМЕН/ -o /dev/null || echo FAIL',
    comment: 'Проверка доступности сайта' },
  { icon: 'trash', title: 'Удаление временных файлов', desc: 'Файлы в /tmp старше недели удаляются раз в час',
    expr: '0 * * * *', command: 'find /tmp -type f -mtime +7 -delete',
    comment: 'Удаление временных файлов раз в час' },
];

/* ---- форматирование дат (кратко: «5 ноя, 03:00») ---- */
const MONS_SHORT = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
function fmtHM(d: Date): string {
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}
function fmtNext(d: Date): string {
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return 'сегодня в ' + fmtHM(d);
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  if (d.toDateString() === tomorrow.toDateString()) return 'завтра в ' + fmtHM(d);
  return d.getDate() + ' ' + MONS_SHORT[d.getMonth()] + ', ' + fmtHM(d);
}
function fmtLastAt(d: Date): string {
  const now = new Date();
  const day = d.toDateString() === now.toDateString() ? 'сегодня'
    : d.getDate() + ' ' + MONS_SHORT[d.getMonth()];
  return day + ' ' + fmtHM(d);
}

/* ---- данные страницы ---- */
const pageState = ref<'loading' | 'ok' | 'fail'>('loading');
const jobs = ref<CronJob[]>([]);
const auto = ref(false);
const autoCron = ref('');
const sslAuto = ref(false);
const sslAutoCron = ref('');
const systemJobs = ref<string[]>([]);

const autoHuman = computed(() => cronHuman(autoCron.value) || 'cron');
const sslHuman = computed(() => cronHuman(sslAutoCron.value) || 'cron');

/* ---- следующий запуск (клиентский расчёт cron) ---- */
const nowTick = ref(0); // тик раз в минуту — пересчитать «следующий запуск»
let nowTimer: ReturnType<typeof setInterval> | null = null;

const jobRows = computed(() => {
  void nowTick.value; // зависимость: пересчёт каждую минуту
  return jobs.value.map((j, i) => {
    const next = j.enabled ? nextRunCron(j.expr) : null;
    return { j, i, human: cronHuman(j.expr), next };
  });
});

/* сводка: всего задач / включено / ближайший запуск */
const enabledCount = computed(() => jobs.value.filter((j) => j.enabled).length);
const nextOverall = computed(() => {
  void nowTick.value;
  let best: Date | null = null;
  for (const j of jobs.value) {
    if (!j.enabled) continue;
    const n = nextRunCron(j.expr);
    if (n && (!best || n < best)) best = n;
  }
  return best;
});

/* ---- статус последнего запуска (из журнала) ---- */
const lastRuns = ref<Record<string, LastRun | null>>({}); // ключ — команда задачи
let lastRunGen = 0;

async function loadLastRuns(): Promise<void> {
  const gen = ++lastRunGen;
  const targets = jobs.value.filter((j) => j.enabled && j.command);
  const results = await Promise.all(targets.map(async (j): Promise<LastRun | null> => {
    try {
      const d = await api('/api/cron/log?command=' + encodeURIComponent(j.command));
      return parseLastRun(d.lines || []);
    } catch { return null; } // ошибка одной задачи не ломает список
  }));
  if (gen !== lastRunGen) return; // устаревший ответ — список уже менялся
  const map: Record<string, LastRun | null> = {};
  targets.forEach((j, k) => { map[j.command] = results[k]; });
  for (const j of jobs.value) if (j.enabled && !(j.command in map)) map[j.command] = null;
  lastRuns.value = map;
}

/** Последний блок журнала: «=== дата запускаю: …» … «[код завершения: N]» */
function parseLastRun(lines: string[]): LastRun | null {
  let start = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (lines[i].startsWith('===')) { start = i; break; }
  }
  if (start < 0) return null;
  const dm = lines[start].match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  let code = -1;
  for (let i = start + 1; i < lines.length; i++) {
    const cm = lines[i].match(/\[код завершения: (-?\d+)\]/);
    if (cm) { code = +cm[1]; break; }
  }
  if (code < 0) return null; // блок без кода завершения — не считаем
  const at = dm ? new Date(+dm[1], +dm[2] - 1, +dm[3], +dm[4], +dm[5]) : new Date();
  return { code, at };
}

function lastRunView(j: CronJob): { cls: string; text: string } | null {
  if (!j.enabled) return null;
  const info = lastRuns.value[j.command];
  if (info === undefined) return null; // ещё загружается
  if (info === null) return { cls: 'pill gray', text: 'ещё не запускалась' };
  if (info.code === 0) return { cls: 'pill ok', text: 'последний запуск: ок, ' + fmtLastAt(info.at) };
  return { cls: 'pill err', text: 'ошибка (код ' + info.code + '), ' + fmtLastAt(info.at) };
}

async function load(): Promise<void> {
  let d: any;
  try { d = await api('/api/cron'); }
  catch (e) { pageState.value = 'fail'; toastErr(e); return; }
  jobs.value = d.jobs || [];
  auto.value = !!d.auto;
  autoCron.value = d.auto_cron || '';
  sslAuto.value = !!d.ssl_auto;
  sslAutoCron.value = d.ssl_auto_cron || '30 3,15 * * *';
  systemJobs.value = d.system_jobs || [];
  tmplOpen.value = !(d.jobs || []).length; // новичку сразу показать шаблоны
  pageState.value = 'ok';
  loadLastRuns(); // не блокирует рендер списка
}
onMounted(() => {
  load();
  nowTimer = setInterval(() => { nowTick.value++; }, 60000);
});
onUnmounted(() => {
  if (nowTimer) { clearInterval(nowTimer); nowTimer = null; }
});

/* ---- сохранение ---- */
async function cronSave(): Promise<void> {
  try {
    const r = await api('/api/cron/save', { method: 'POST', body: {
      jobs: jobs.value,
      auto: auto.value,
      auto_cron: autoCron.value,
      ssl_auto: sslAuto.value,
      ssl_auto_cron: sslAutoCron.value,
    } });
    toast(r.message);
  } catch (e) { toastErr(e); }
  loadLastRuns(); // состав/команды задач могли измениться
}

function toggleJob(i: number, checked: boolean): void {
  if (jobs.value[i]) { jobs.value[i].enabled = checked; cronSave(); }
}

/* ---- создание / редактирование ---- */
const editOpen = ref(false);
const editIdx = ref(-1);
const fExpr = ref('');
const fCmd = ref('');
const fCmt = ref('');
const sites = ref<SiteRow[]>([]);
const siteSel = ref('');
const cmdEl = ref<HTMLInputElement | null>(null);

/* черновик модалки (переживает закрытие — как cronState в исходнике) */
let draft: { idx: number; expr: string; command: string; comment: string } | null = null;

const editHuman = computed(() => {
  const h = cronHuman(fExpr.value);
  return h ? 'Это значит: ' + h
    : 'Формат cron: минуты часы день-месяца месяц день-недели — 5 полей через пробел';
});
const editNext = computed(() => {
  const d = nextRunCron(fExpr.value);
  return d ? 'Следующий запуск при таком расписании: ' + fmtNext(d) : '';
});

function loadSites(): void {
  api('/api/sites').then((d) => { sites.value = d.sites || []; }).catch(() => {});
}

function remember(): void {
  if (editOpen.value)
    draft = { idx: editIdx.value, expr: fExpr.value, command: fCmd.value, comment: fCmt.value };
}

function openEdit(idx: number): void {
  let j: CronJob = idx >= 0 ? { ...jobs.value[idx] } :
    { expr: '0 3 * * *', command: '', comment: '', enabled: true };
  if (draft && draft.idx === idx) {
    j.expr = draft.expr;
    j.command = draft.command;
    j.comment = draft.comment;
  }
  draft = null;
  editIdx.value = idx;
  fExpr.value = j.expr;
  fCmd.value = j.command;
  fCmt.value = j.comment || '';
  siteSel.value = '';
  editOpen.value = true;
  loadSites();
}

/* задача из шаблона — та же модалка, предзаполненная */
function useTemplate(t: CronTemplate): void {
  draft = null;
  editIdx.value = -1;
  fExpr.value = t.expr;
  fCmd.value = t.command;
  fCmt.value = t.comment;
  siteSel.value = '';
  editOpen.value = true;
  loadSites();
  if (t.command.includes('СУБДОМЕН'))
    toast('Впишите адрес своего сайта вместо СУБДОМЕН', 'warn');
}

function siteInsert(): void {
  if (siteSel.value) {
    insertAtCursor(siteSel.value);
    remember();
  }
  siteSel.value = '';
}

function insertAtCursor(text: string): void {
  const inp = cmdEl.value;
  if (!inp) return;
  const s = inp.selectionStart == null ? inp.value.length : inp.selectionStart;
  const e = inp.selectionEnd == null ? s : inp.selectionEnd;
  fCmd.value = inp.value.slice(0, s) + text + inp.value.slice(e);
  nextTick(() => {
    inp.focus();
    const pos = s + text.length;
    inp.setSelectionRange(pos, pos);
  });
}

async function saveEdit(): Promise<void> {
  const expr = fExpr.value.trim(), cmd = fCmd.value.trim();
  if (expr.split(/\s+/).length !== 5) {
    toast('В расписании должно быть 5 полей через пробел, например: 0 3 * * *', 'warn');
    return;
  }
  if (!cmd) { toast('Укажите команду — что именно запускать', 'warn'); return; }
  const j: CronJob = { expr, command: cmd, comment: fCmt.value.trim(), enabled: true };
  if (editIdx.value >= 0) jobs.value[editIdx.value] = j;
  else jobs.value.push(j);
  draft = null;
  await cronSave();
  editOpen.value = false;
}

/* ---- удаление ---- */
function del(i: number): void {
  const j = jobs.value[i] || ({ expr: '', command: '', enabled: false } as CronJob);
  const name = j.comment || (j.command || '').slice(0, 40);
  confirmDlg('Удалить задачу?',
    'Задача «' + name + '» больше не будет запускаться по расписанию.',
    async () => {
      jobs.value.splice(i, 1);
      await cronSave();
      toast('Задача удалена');
    });
}

/* ---- журнал запусков ---- */
const logOpen = ref(false);
const logTitle = ref('');
const logLines = ref<string[] | null>(null);

function openLog(i: number): void {
  const j = jobs.value[i] || ({ expr: '', command: '', enabled: false } as CronJob);
  logTitle.value = j.comment || (j.command || '').slice(0, 40);
  logLines.value = null;
  logOpen.value = true;
  api('/api/cron/log?command=' + encodeURIComponent(j.command || ''))
    .then((d) => {
      if (!logOpen.value) return;
      logLines.value = (d.lines && d.lines.length) ? d.lines : [];
    })
    .catch((e) => toastErr(e));
}

/* ---- запуск сейчас ---- */
const runOpen = ref(false);
const runTitle = ref('');
const runResult = ref<{ code: number; output: string } | null>(null);
let runGen = 0; // результат первой задачи не должен перетирать результат второй

async function openRun(i: number): Promise<void> {
  const gen = ++runGen;
  const j = jobs.value[i] || ({ expr: '', command: '', enabled: false } as CronJob);
  runTitle.value = (j.comment || j.command || '').slice(0, 60);
  runResult.value = null;
  runOpen.value = true;
  try {
    const r = await api('/api/cron/run', { method: 'POST', body: { index: i } });
    if (gen !== runGen || !runOpen.value) return;
    runResult.value = { code: r.code, output: r.output || '' };
    loadLastRuns(); // задача только что выполнилась — обновить статус
  } catch (e) { if (gen === runGen) toastErr(e); }
}

/* ---- выбор файла (мини-проводник) ---- */
const pickerOpen = ref(false);
const pickerStart = ref('/var/www');

function openPicker(): void {
  remember();
  const vals = sites.value.map((s) => s.docroot).filter(Boolean);
  pickerStart.value = vals.length === 1 ? vals[0] : '/var/www';
  editOpen.value = false;
  pickerOpen.value = true;
}

function onPick(p: string): void {
  pickerOpen.value = false;
  const cmd = fCmd.value || '';
  let q = p;
  if (cmd && !cmd.endsWith(' ') && !cmd.endsWith(p)) q = ' ' + p;
  fCmd.value = cmd.endsWith(q) ? cmd : cmd + q;
  editOpen.value = true;
  toast('Путь вставлен — допишите команду');
}

/* ---- карточка шаблонов: раскрыть/свернуть ---- */
const tmplOpen = ref(false);
</script>

<template>
  <div v-table>
    <div v-if="pageState === 'loading'" class="empty">Загрузка…</div>
    <template v-else-if="pageState === 'ok'">
      <div class="hintbox">
        <UiIcon name="clock" :size="16" />
        <div><b>Планировщик</b> запускает команду автоматически:
          например, раз в ночь делать выгрузку базы или раз в час чистить временные файлы.
          Интервал выбирается готовыми кнопками — писать cron вручную не обязательно.</div>
      </div>

      <!-- сводка -->
      <div v-if="jobs.length" class="card" style="padding:10px 14px">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span class="pill">задач: {{ jobs.length }}</span>
          <span class="pill" :class="enabledCount ? 'ok' : 'gray'">включено: {{ enabledCount }}</span>
          <span v-if="nextOverall" class="pill info">
            <UiIcon name="clock" :size="12" />ближайший запуск: {{ fmtNext(nextOverall) }}</span>
          <span v-else-if="enabledCount === 0" class="pill gray">все задачи выключены</span>
        </div>
      </div>

      <div class="toolbar">
        <button class="btn primary" @click="openEdit(-1)">
          <UiIcon name="plus" :size="15" />Добавить задачу</button>
        <span class="spacer"></span>
        <UiCheckbox v-model="auto" title="Копия всех сайтов и баз по расписанию"
                    @update:model-value="cronSave()">Автобэкап по расписанию</UiCheckbox>
        <input v-model="autoCron" type="text" style="width:110px" class="mono"
               title="Расписание автобэкапа" @change="cronSave()">
        <span class="faint" style="font-size:11.5px">{{ autoHuman }}</span>
        <UiCheckbox v-model="sslAuto"
                    title="Сертификаты Let's Encrypt продлеваются автоматически (certbot renew); панель предупредит, если сертификат истекает раньше чем через 14 дней"
                    @update:model-value="cronSave()">Автопродление SSL</UiCheckbox>
        <input v-model="sslAutoCron" type="text" style="width:110px" class="mono"
               title="Расписание проверки сертификатов" @change="cronSave()">
        <span class="faint" style="font-size:11.5px">{{ sslHuman }}</span>
      </div>

      <!-- готовые задачи в один клик -->
      <div class="card">
        <div class="card-h" style="cursor:pointer;margin-bottom:0" @click="tmplOpen = !tmplOpen">
          <UiIcon name="zap" :size="16" />
          <span class="card-t">Шаблоны задач</span>
          <span class="card-spacer"></span>
          <span class="pill gray">готовые задачи в один клик</span>
          <button class="btn sm" type="button" :title="tmplOpen ? 'Свернуть' : 'Развернуть'">
            <UiIcon :name="tmplOpen ? 'up' : 'down'" :size="13" /></button>
        </div>
        <div v-if="tmplOpen" style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px">
          <div v-for="t in TEMPLATES" :key="t.title"
               style="flex:1 1 260px;min-width:240px;border:1px solid var(--border);border-radius:var(--r-md);padding:12px 14px">
            <div style="display:flex;align-items:center;gap:8px">
              <UiIcon :name="t.icon" :size="16" />
              <b style="font-size:13.5px">{{ t.title }}</b>
            </div>
            <div class="faint" style="font-size:12px;margin:6px 0 4px">{{ t.desc }}</div>
            <div style="margin:2px 0 8px">
              <span class="pill info">{{ cronHuman(t.expr) }}</span>
            </div>
            <div class="mono faint" style="font-size:11px;word-break:break-all;margin-bottom:10px">{{ t.command }}</div>
            <button class="btn sm primary" @click="useTemplate(t)">
              <UiIcon name="plus" :size="13" />Добавить</button>
          </div>
        </div>
      </div>

      <div v-if="jobs.length" class="card" style="padding:6px 10px">
        <div class="twrap"><table>
          <thead><tr><th>Расписание</th><th>Команда</th><th>Последний запуск</th><th>Вкл.</th><th></th></tr></thead>
          <tbody>
            <tr v-for="row in jobRows" :key="row.i">
              <td>
                <span class="mono">{{ row.j.expr }}</span>
                <div v-if="row.human" class="faint" style="font-size:11.5px;margin-top:2px">{{ row.human }}</div>
                <div v-if="row.next" class="faint" style="font-size:11.5px;margin-top:2px;display:flex;align-items:center;gap:4px">
                  <UiIcon name="clock" :size="11" />следующий запуск: {{ fmtNext(row.next) }}</div>
              </td>
              <td style="word-break:break-all">
                <span class="mono">{{ row.j.command }}</span>
                <div v-if="row.j.comment" class="faint" style="font-size:11.5px;margin-top:2px">{{ row.j.comment }}</div>
              </td>
              <td>
                <span v-if="lastRunView(row.j)" :class="lastRunView(row.j)!.cls">{{ lastRunView(row.j)!.text }}</span>
                <span v-else-if="row.j.enabled" class="faint" style="font-size:11.5px">проверяем журнал…</span>
                <span v-else class="faint" style="font-size:11.5px">—</span>
              </td>
              <td><UiCheckbox :model-value="row.j.enabled"
                              @update:model-value="(v) => toggleJob(row.i, v)" /></td>
              <td>
                <div class="actions-cell">
                  <button class="btn sm" title="Журнал запусков" @click="openLog(row.i)"><UiIcon name="file" :size="13" /></button>
                  <button class="btn sm" title="Запустить прямо сейчас — проверить, что команда работает" @click="openRun(row.i)"><UiIcon name="play" :size="13" /></button>
                  <button class="btn sm" title="Изменить" @click="openEdit(row.i)"><UiIcon name="edit" :size="13" /></button>
                  <button class="btn sm icon danger" title="Удалить" @click="del(row.i)"><UiIcon name="trash" :size="13" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table></div>
      </div>
      <div v-else class="card" style="text-align:center;padding:46px 20px">
        <div class="empty" style="padding:0 0 12px">
          Задач пока нет.<br>
          Например: раз в сутки сохранять копию базы или раз в час удалять временные файлы.
        </div>
        <button class="btn primary" @click="openEdit(-1)">
          <UiIcon name="plus" :size="15" /> Добавить первую задачу</button>
      </div>

      <div v-if="systemJobs.length" class="card">
        <div class="card-h">
          <span class="card-t">Служебные задания</span>
          <span class="card-spacer"></span>
          <span class="pill gray">созданы панелью и её службами</span>
        </div>
        <div class="logbox" style="max-height:180px">{{ systemJobs.join('\n') }}</div>
      </div>
    </template>
  </div>

  <!-- модалка создания / редактирования задачи -->
  <AppModal :open="editOpen" :title="editIdx >= 0 ? 'Изменить задачу' : 'Новая задача'" wide
            @close="editOpen = false">
    <div class="field">
      <label>Когда запускать — выберите интервал</label>
      <div class="chips" style="margin:0 0 10px">
        <button v-for="p in CRON_PRESETS" :key="p[0]" class="btn sm" type="button"
                @click="fExpr = p[0]">{{ p[1] }}</button>
      </div>
      <input v-model="fExpr" type="text" class="mono" placeholder="0 3 * * *" @input="remember()">
      <div class="faint" style="font-size:12px;margin-top:5px">{{ editHuman }}</div>
      <div v-if="editNext" class="notice info" style="margin-top:8px;font-size:12.5px">{{ editNext }}</div>
    </div>
    <div class="field">
      <label>Команда</label>
      <div class="row" style="flex-wrap:nowrap">
        <input ref="cmdEl" v-model="fCmd" type="text" class="mono"
               placeholder="/var/www/mysite.ru/script.php" style="flex:1" @input="remember()">
        <button class="btn" type="button" title="Найти файл на сервере" @click="openPicker()">
          <UiIcon name="folder" :size="14" /></button>
      </div>
      <div class="row" style="margin-top:8px">
        <UiSelect v-model="siteSel" style="flex:1" @change="siteInsert()"
                  :options="[{ value: '', label: '— вставить путь к сайту —' },
                    ...sites.map((s) => ({ value: s.docroot, label: s.domain }))]" />
      </div>
      <div class="faint" style="font-size:11.5px;margin-top:5px">
        Выберите сайт — его путь подставится в команду, допишите дальше путь до скрипта, например:
        <span class="mono">/var/www/mysite.ru/cron/job.php</span>
      </div>
    </div>
    <div class="field">
      <label>Описание (для себя)</label>
      <input v-model="fCmt" type="text" placeholder="например, ночной бэкап базы" @input="remember()">
    </div>
    <template #footer>
      <button class="btn primary" @click="saveEdit()">Сохранить</button>
      <button class="btn" @click="editOpen = false">Отмена</button>
    </template>
  </AppModal>

  <!-- мини-проводник по файлам сервера -->
  <FilePickerModal :open="pickerOpen" :start="pickerStart"
                   @close="pickerOpen = false" @pick="onPick" />

  <!-- журнал запусков -->
  <AppModal :open="logOpen" :title="'Журнал: ' + logTitle" wide @close="logOpen = false">
    <div v-if="logLines === null" class="empty">Загрузка…</div>
    <div v-else-if="logLines.length" class="logbox" style="max-height:56vh">{{ logLines.join('\n') }}</div>
    <div v-else class="empty">
      Задача ещё не запускалась — журнал пуст.<br>
      Нажмите «Запустить сейчас», чтобы проверить её и увидеть вывод.
    </div>
    <template #footer>
      <button class="btn" @click="logOpen = false">Закрыть</button>
    </template>
  </AppModal>

  <!-- запуск сейчас -->
  <AppModal :open="runOpen" :title="'Запуск: ' + runTitle" wide @close="runOpen = false">
    <div v-if="!runResult" class="empty">Выполняется…</div>
    <template v-else>
      <div :class="runResult.code === 0 ? 'notice ok' : 'notice err'">
        <b>{{ runResult.code === 0 ? 'Команда выполнена успешно.'
             : 'Команда завершилась с кодом ' + runResult.code + '.' }}</b>
        <div v-if="runResult.output" class="logbox" style="margin-top:10px;max-height:300px">{{ runResult.output }}</div>
        <div v-else class="faint" style="margin-top:6px">Вывода нет — команда отработала молча.</div>
      </div>
    </template>
    <template #footer>
      <button class="btn" @click="runOpen = false">Закрыть</button>
    </template>
  </AppModal>
</template>
