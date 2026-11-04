<script setup lang="ts">
/* ============ Страница: Планировщик (cron) + выбор файла ============ */
import { ref, computed, onMounted, nextTick } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { cronHuman } from '../lib/format';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import FilePickerModal from './cron/FilePickerModal.vue';

interface CronJob { expr: string; command: string; comment?: string; enabled: boolean }
interface SiteRow { domain: string; docroot: string }

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

const jobRows = computed(() => jobs.value.map((j, i) => ({
  j, i, human: cronHuman(j.expr),
})));

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
  pageState.value = 'ok';
}
onMounted(load);

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
}

function toggleJob(i: number, ev: Event): void {
  const checked = (ev.target as HTMLInputElement).checked;
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
  api('/api/sites').then((d) => { sites.value = d.sites || []; }).catch(() => {});
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

async function openRun(i: number): Promise<void> {
  const j = jobs.value[i] || ({ expr: '', command: '', enabled: false } as CronJob);
  runTitle.value = (j.comment || j.command || '').slice(0, 60);
  runResult.value = null;
  runOpen.value = true;
  try {
    const r = await api('/api/cron/run', { method: 'POST', body: { index: i } });
    if (!runOpen.value) return;
    runResult.value = { code: r.code, output: r.output || '' };
  } catch (e) { toastErr(e); }
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

      <div class="toolbar">
        <button class="btn primary" @click="openEdit(-1)">
          <UiIcon name="plus" :size="15" />Добавить задачу</button>
        <span class="spacer"></span>
        <label class="check" style="margin:0" title="Копия всех сайтов и баз по расписанию">
          <input v-model="auto" type="checkbox" @change="cronSave()"> Автобэкап по расписанию</label>
        <input v-model="autoCron" type="text" style="width:110px" class="mono"
               title="Расписание автобэкапа" @change="cronSave()">
        <span class="faint" style="font-size:11.5px">{{ autoHuman }}</span>
        <label class="check" style="margin:0"
               title="Сертификаты Let's Encrypt продлеваются автоматически (certbot renew); панель предупредит, если сертификат истекает раньше чем через 14 дней">
          <input v-model="sslAuto" type="checkbox" @change="cronSave()"> Автопродление SSL</label>
        <input v-model="sslAutoCron" type="text" style="width:110px" class="mono"
               title="Расписание проверки сертификатов" @change="cronSave()">
        <span class="faint" style="font-size:11.5px">{{ sslHuman }}</span>
      </div>

      <div v-if="jobs.length" class="card" style="padding:6px 10px">
        <div class="twrap"><table>
          <thead><tr><th>Расписание</th><th>Команда</th><th>Описание</th><th>Вкл.</th><th></th></tr></thead>
          <tbody>
            <tr v-for="row in jobRows" :key="row.i">
              <td>
                <span class="mono">{{ row.j.expr }}</span>
                <div v-if="row.human" class="faint" style="font-size:11.5px;margin-top:2px">{{ row.human }}</div>
              </td>
              <td class="mono" style="word-break:break-all">{{ row.j.command }}</td>
              <td class="muted">{{ row.j.comment || '' }}</td>
              <td><input type="checkbox" :checked="row.j.enabled" @change="toggleJob(row.i, $event)"></td>
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
        <select v-model="siteSel" style="flex:1" @change="siteInsert()">
          <option value="">— вставить путь к сайту —</option>
          <option v-for="s in sites" :key="s.docroot" :value="s.docroot">{{ s.domain }}</option>
        </select>
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
