<script setup lang="ts">
/* ============ Страница: Настройки (пароль, уведомления, 2FA, диск, миграция) ============ */
import { reactive, ref, onMounted, onBeforeUnmount } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { esc } from '../lib/format';
import { me, session } from '../stores';
import { applyTheme } from '../lib/theme';
import { copyText } from '../lib/clipboard';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';

/* ---------- настройки панели ---------- */
const settings = reactive({
  theme: 'light',
  backup_retention: 7,
  panel_port: 8080,
  health_interval: 60,
  fm_restricted: true,
  weekly_report_enabled: false,
  public_status: false,
});
const expert = ref(!!me.expert);
const ntSec = ref(false);

/* ---------- уведомления ---------- */
const ntEmail = reactive({
  enabled: false, host: '', port: 587, user: '', pass: '', from: '', to: '',
});
const ntTg = reactive({ enabled: false, token: '', chat: '' });

/* ---------- журнал, сессии, 2FA, диск ---------- */
const panelLog = ref('');
const sessions = ref<any[]>([]);
const curSid = ref('');
const totpOn = ref(false);
const disk = ref<any>(null);

/* ---------- пароль ---------- */
const pwOld = ref('');
const pwNew = ref('');

/* ---------- 2FA: модалка включения/выключения ---------- */
const totpDlg = ref(false);
const totpSecret = ref('');
const totpQr = ref('');
const totpCode = ref('');
const totpDisDlg = ref(false);
const totpPw = ref('');

/* ---------- импорт настроек ---------- */
const impDlg = ref(false);
const impData = ref<any>(null);
const impPreview = ref('');
const impReady = ref(false);
const impReport = ref<string[]>([]);
const impApplied = ref(false);

/* ---------- обновления панели (GitHub) ---------- */
const upd = ref<any>(null);
const updBusy = ref(false);
let updTimer: ReturnType<typeof setInterval> | null = null;

async function updCheck(silent = false): Promise<void> {
  if (!silent) updBusy.value = true;
  try { upd.value = await api('/api/panel/update'); }
  catch (e) { if (!silent) toastErr(e); }
  finally { if (!silent) updBusy.value = false; }
}

async function updRun(): Promise<void> {
  confirmDlg('Обновить панель?',
    'Панель скачает версию ' + (upd.value?.latest || 'из репозитория') +
    ' с GitHub, заменит файлы (текущие сохранятся в бэкап) и перезапустится. ' +
    'Страница откроется сама после перезапуска.',
    async () => {
      try {
        const r = await api('/api/panel/update/run', { method: 'POST', body: {} });
        toast(r.message || 'Обновление запущено');
        updTimer = setInterval(() => {
          updCheck(true).then(() => {
            if (upd.value && upd.value.task && !upd.value.task.running) {
              if (updTimer) { clearInterval(updTimer); updTimer = null; }
              // панель сейчас перезапустится — через пару секунд перезагружаем страницу
              setTimeout(() => { window.location.reload(); }, 4000);
            }
          });
        }, 2000);
      } catch (e) { toastErr(e); }
    });
}

onBeforeUnmount(() => { if (updTimer) clearInterval(updTimer); });

async function load(): Promise<void> {
  let d: any;
  try {
    d = await api('/api/settings');
    const [log, sess, totp] = await Promise.all([
      api('/api/panellog').then((x) => x.log),
      api('/api/sessions').catch(() => null),
      api('/api/totp/status').catch(() => null)]);
    panelLog.value = (log || []).map((l: any) => l.ts + '  ' + l.text).join('\n');
    sessions.value = (sess && sess.sessions) || [];
    curSid.value = sess ? sess.current : '';
    totpOn.value = !!(totp && totp.enabled);
  } catch (e) { toastErr(e); return; }
  const s = d.settings;
  settings.theme = s.theme === 'dark' ? 'dark' : 'light';
  settings.backup_retention = Number(s.backup_retention);
  settings.panel_port = Number(s.panel_port);
  settings.health_interval = Number(s.health_interval) || 60;
  settings.fm_restricted = s.fm_restricted !== false;
  settings.weekly_report_enabled = !!s.weekly_report_enabled;
  settings.public_status = !!s.public_status;
  const n = s.notify || { email: {}, tg: {} };
  const e = n.email || {}, t = n.tg || {};
  ntSec.value = !!(n.security || {}).enabled;
  ntEmail.enabled = !!e.enabled; ntEmail.host = e.host || '';
  ntEmail.port = Number(e.port) || 587; ntEmail.user = e.user || '';
  ntEmail.pass = e.pass || ''; ntEmail.from = e.from || e.user || '';
  ntEmail.to = e.to || '';
  ntTg.enabled = !!t.enabled; ntTg.token = t.token || ''; ntTg.chat = t.chat || '';
  loadDiskCard();
}

/* ---------- сохранение настроек / темы ---------- */
async function settingsSave(): Promise<void> {
  const expChanged = expert.value !== !!me.expert;
  try {
    const r = await api('/api/settings/save', { method: 'POST', body: {
      theme: settings.theme,
      backup_retention: +settings.backup_retention,
      panel_port: +settings.panel_port,
      health_interval: +settings.health_interval,
      fm_restricted: settings.fm_restricted,
      expert_mode: expert.value,
      weekly_report_enabled: settings.weekly_report_enabled,
      public_status: settings.public_status,
      notify: { security: { enabled: ntSec.value } } } });
    toast(r.message);
    if (expChanged) setTimeout(() => location.reload(), 700);
  } catch (e) { toastErr(e); }
}

function onThemeChange(): void {
  settingsSave();
  applyTheme(String(settings.theme));
}

/* ---------- смена пароля администратора ---------- */
async function changePass(): Promise<void> {
  try {
    await api('/api/password/change', { method: 'POST', body: {
      old: pwOld.value, new: pwNew.value } });
    pwOld.value = '';
    pwNew.value = '';
    session.defaultPw = false;
    toast('Пароль изменён');
  } catch (e) { toastErr(e); }
}

/* ---------- уведомления: e-mail и Telegram ---------- */
async function notifySave(): Promise<void> {
  const r = await api('/api/settings/save', { method: 'POST', body: { notify: {
    email: { enabled: ntEmail.enabled, host: ntEmail.host,
      port: +ntEmail.port || 587, user: ntEmail.user,
      pass: ntEmail.pass, from: ntEmail.from, to: ntEmail.to },
    tg: { enabled: ntTg.enabled, token: ntTg.token, chat: ntTg.chat } } } });
  toast(r.message);
}

async function notifySaveSafe(): Promise<void> {
  try { await notifySave(); } catch (e) { toastErr(e); }
}

async function notifyTest(): Promise<void> {
  try {
    await notifySave();
    const r = await api('/api/notify/test', { method: 'POST', body: {} });
    toast(r.message);
  } catch (e) { toastErr(e); }
}

/* ---------- безопасность: 2FA и активные сессии ---------- */
function shortUa(ua: string): string {
  const m = (ua || '').match(/(Edg|Chrome|Firefox|Safari|OPR)\/[\d.]+/);
  if (m) return m[0];
  if (/python|curl|wget/i.test(ua || '')) return (ua || '').slice(0, 40);
  return (ua || '').slice(0, 44) || 'неизвестное устройство';
}

function seenWhen(x: any): string {
  const t = new Date((x.seen || 0) * 1000);
  return isNaN(t.getTime()) ? '' : t.toLocaleString('ru-RU',
    { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

async function sessionDrop(sid: string): Promise<void> {
  try {
    const r = await api('/api/sessions/drop', { method: 'POST', body: { sid } });
    toast(r.message); load();
  } catch (e) { toastErr(e); }
}

async function dropOtherSessions(): Promise<void> {
  try {
    const d = await api('/api/sessions');
    const others = (d.sessions || []).filter((x: any) => x.sid !== d.current);
    for (const x of others)
      await api('/api/sessions/drop', { method: 'POST', body: { sid: x.sid } });
    toast(others.length ? ('Завершено сессий: ' + others.length)
                        : 'Других сессий нет');
    load();
  } catch (e) { toastErr(e); }
}

async function totpEnableDlg(): Promise<void> {
  try {
    const d = await api('/api/totp/setup');
    totpSecret.value = d.secret || '';
    totpCode.value = '';
    totpQr.value = '';
    totpDlg.value = true;
    if (d.qr) {
      api('/api/totp/qr?uri=' + encodeURIComponent(d.uri)).then((q: any) => {
        totpQr.value = q.svg.replace('<svg', '<svg style="width:190px;height:190px"');
      }).catch(() => { /* тихо */ });
    }
    setTimeout(() => {
      const el = document.getElementById('totp-code') as HTMLInputElement | null;
      if (el) el.focus();
    }, 300);
  } catch (e) { toastErr(e); }
}

async function totpConfirm(): Promise<void> {
  try {
    const r = await api('/api/totp/enable', { method: 'POST', body: {
      secret: totpSecret.value, code: totpCode.value } });
    totpDlg.value = false;
    toast(r.message); load();
  } catch (e) { toastErr(e); }
}

function totpDisableDlg(): void {
  totpPw.value = '';
  totpDisDlg.value = true;
}

async function totpDisable(): Promise<void> {
  try {
    const r = await api('/api/totp/disable', { method: 'POST', body: {
      password: totpPw.value } });
    totpDisDlg.value = false;
    toast(r.message); load();
  } catch (e) { toastErr(e); }
}

/* ---------- диск: куда уходит место ---------- */
async function loadDiskCard(): Promise<void> {
  let d: any;
  try { d = await api('/api/disk'); } catch (e) { disk.value = null; return; }
  disk.value = d;
}

async function diskClean(what: string): Promise<void> {
  const names: Record<string, string> = { apt: 'кэш apt', journal: 'журнал systemd (оставить 7 дней)',
    tmp: 'временные файлы панели', backups: 'старые резервные копии (остать последние 3)' };
  confirmDlg('Очистить: ' + (names[what] || what),
    'Выполнить очистку «' + (names[what] || what) + '»?', async () => {
      try {
        const r = await api('/api/disk/clean', { method: 'POST', body: { what } });
        toast(r.message); loadDiskCard();
      } catch (e) { toastErr(e); }
    }, false);
}

/* ---------- перенос настроек на другой сервер ---------- */
async function exportSettings(): Promise<void> {
  try {
    const d = await api('/api/settings/export');
    const blob = new Blob([JSON.stringify(d.data, null, 2)],
      { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'hostpanel-settings-' +
      new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(a.href);
    toast('Файл настроек скачан');
  } catch (e) { toastErr(e); }
}

function importDlg(): void {
  impData.value = null;
  impPreview.value = '';
  impReady.value = false;
  impReport.value = [];
  impApplied.value = false;
  impDlg.value = true;
}

function onImportFile(ev: Event): void {
  const inp = ev.target as HTMLInputElement;
  const f = inp.files && inp.files[0];
  if (!f) return;
  if (f.size > 2 * 1024 * 1024) { toast('Файл больше 2 МБ — это не файл настроек', 'warn'); return; }
  const rd = new FileReader();
  rd.onload = () => {
    try {
      const data = JSON.parse(String(rd.result));
      if (data.panel !== 'HostPanel') throw new Error('это не экспорт HostPanel');
      impData.value = data;
      const sites = (data.sites || []).length;
      const cron = (data.cron || []).length;
      const mailD = ((data.mail || {}).domains || []).length;
      impPreview.value = 'Файл от ' + esc(data.exported || '?') +
        ' (панель ' + esc(data.version || '?') + '): сайтов — ' + sites +
        ', задач — ' + cron + ', почтовых доменов — ' + mailD;
      impReady.value = true;
    } catch (e: any) { toast('Не удалось прочитать файл: ' + e.message, 'warn'); }
  };
  rd.readAsText(f);
}

async function importApply(): Promise<void> {
  const data = impData.value;
  if (!data) return;
  try {
    const r = await api('/api/settings/import', { method: 'POST', body: { data } });
    impPreview.value = r.summary || 'Готово';
    impReport.value = r.report || [];
    impReady.value = false;
    impApplied.value = true;
    impData.value = null;
    toast(r.summary || 'Импорт выполнен');
  } catch (e) { toastErr(e); }
}

/* ---------- перезагрузка сервера ---------- */
function serverRebootDlg(): void {
  confirmDlg('Перезагрузка сервера',
    'Действительно перезагрузить <b>весь сервер</b>? Панель и сайты будут недоступны 1–2 минуты.',
    async () => {
      try {
        const r = await api('/api/system/reboot', { method: 'POST', body: { confirm: 'reboot' } });
        toast(r.message);
      } catch (e) { toastErr(e); }
    });
}

onMounted(() => { load(); updCheck(true); });
</script>

<template>
  <div v-table>
    <div class="split">
      <div>
        <div class="card">
          <div class="card-h"><span class="card-t">Панель</span></div>
          <div class="kv">
            <b>Версия</b><span>{{ me.version }}</span>
            <b>Режим</b><span>{{ me.demo ? 'демо (изменения не влияют на систему)' : 'рабочий' }}</span>
            <b>Домашняя папка</b><span class="mono">{{ me.home }}</span>
            <b>Корень сайтов</b><span class="mono">{{ me.www_root }}</span>
          </div>
          <label style="margin-top:12px">Тема интерфейса</label>
          <select v-model="settings.theme" @change="onThemeChange">
            <option value="dark">тёмная</option>
            <option value="light">светлая</option>
          </select>
          <label>Хранить резервных копий (шт.)</label>
          <input v-model="settings.backup_retention" type="number">
          <label>Порт панели (после смены перезапустите)</label>
          <input v-model="settings.panel_port" type="number">
          <label>Интервал проверок живучести, сек (15–3600)</label>
          <input v-model="settings.health_interval" type="number">
          <label class="check">
            <input v-model="settings.fm_restricted" type="checkbox">
            Ограничить файловый менеджер (/var/www, /etc/…, папка панели)
          </label>
          <label class="check">
            <input v-model="expert" type="checkbox">
            Режим «Эксперт» — показывать командную строку, SQL-консоль и редакторы конфигов
          </label>
          <label class="check">
            <input v-model="settings.weekly_report_enabled" type="checkbox">
            Еженедельный отчёт (понедельник 09:00, на e-mail/TG)
          </label>
          <label class="check">
            <input v-model="settings.public_status" type="checkbox">
            Публичная страница <span class="mono">/status</span> для внешних мониторингов (JSON без секретов)
          </label>
          <div class="faint" style="font-size:11.5px;margin-top:4px">По умолчанию включён «Простой» режим: скрыты инструменты для опытных, интерфейс короче.</div>
          <button class="btn primary" style="margin-top:12px" @click="settingsSave()">
            <UiIcon name="check" :size="15" /> Сохранить
          </button>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Обновления панели</span>
            <span v-if="upd && upd.update_available" class="pill warn"
                  style="margin-left:auto">доступна {{ upd.latest }}</span>
            <span v-else-if="upd && !upd.error" class="pill ok"
                  style="margin-left:auto">актуальна</span>
          </div>
          <div class="kv">
            <b>Установлена</b><span class="mono">v{{ me.version }}</span>
            <template v-if="upd && upd.latest">
              <b>В репозитории</b><span class="mono">v{{ upd.latest }}</span>
            </template>
            <b>Источник</b><span class="mono">github.com/{{ upd ? upd.repo : 'enikov1/hostPanel' }}</span>
          </div>
          <div v-if="upd && upd.error" class="notice warn" style="margin-top:8px">
            Не удалось проверить обновления: {{ upd.error }}. Проверьте интернет на сервере и попробуйте ещё раз.
          </div>
          <div v-if="upd && upd.task && upd.task.running" class="notice info" style="margin-top:8px">
            Обновление выполняется — панель перезапустится автоматически…
          </div>
          <div v-if="upd && upd.task && upd.task.log && upd.task.log.length"
               class="logbox" style="max-height:180px;margin-top:8px">{{ upd.task.log.join('\n') }}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
            <button class="btn" :disabled="updBusy || (upd && upd.task && upd.task.running)"
                    @click="updCheck()">
              <UiIcon name="refresh" :size="15" /> {{ updBusy ? 'Проверяю…' : 'Проверить обновления' }}
            </button>
            <button v-if="upd && upd.update_available" class="btn primary"
                    :disabled="upd && upd.task && upd.task.running"
                    @click="updRun()">
              <UiIcon name="up" :size="15" /> Обновить до v{{ upd.latest }}
            </button>
          </div>
          <div class="faint" style="font-size:11.5px;margin-top:6px">
            Перед заменой файлов панель сохраняет копию текущей версии; данные и настройки сайтов не затрагиваются.
          </div>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Уведомления о проблемах</span></div>
          <div class="faint" style="font-size:12.5px;line-height:1.55;margin-bottom:6px">Панель сообщит на e-mail и в Telegram, когда сайт перестанет отвечать, когда восстановится и по итогам каждого автобэкапа.</div>
          <label class="check">
            <input v-model="ntSec" type="checkbox">
            О безопасности: входы в панель и блокировки fail2ban (Telegram)
          </label>
          <label class="check">
            <input v-model="ntEmail.enabled" type="checkbox">
            E-mail (письмо через SMTP)
          </label>
          <div v-show="ntEmail.enabled" style="margin:4px 0 8px">
            <div class="field"><label>SMTP-сервер (например smtp.yandex.ru)</label><input v-model="ntEmail.host" type="text"></div>
            <div class="field"><label>Порт (465 — SSL, 587 — STARTTLS)</label><input v-model="ntEmail.port" type="number"></div>
            <div class="field"><label>Логин SMTP</label><input v-model="ntEmail.user" type="text"></div>
            <div class="field"><label>Пароль SMTP (или пароль приложения)</label><input v-model="ntEmail.pass" type="password"></div>
            <div class="field"><label>От кого (адрес в письме)</label><input v-model="ntEmail.from" type="text"></div>
            <div class="field"><label>Кому присылать уведомления</label><input v-model="ntEmail.to" type="text"></div>
          </div>
          <label class="check">
            <input v-model="ntTg.enabled" type="checkbox">
            Telegram (бот)
          </label>
          <div v-show="ntTg.enabled" style="margin:4px 0 8px">
            <div class="field"><label>Токен бота (от @BotFather)</label><input v-model="ntTg.token" type="text"></div>
            <div class="field"><label>Chat ID (узнать у @userinfobot)</label><input v-model="ntTg.chat" type="text"></div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn primary" @click="notifySaveSafe()"><UiIcon name="check" :size="15" /> Сохранить</button>
            <button class="btn" @click="notifyTest()"><UiIcon name="bell" :size="15" /> Отправить тест</button>
          </div>
          <div class="faint" style="font-size:12px;margin-top:6px">Тест отправит сообщение во все включённые каналы — удобно проверить настройки до сбоя.</div>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Журнал панели (аудит)</span></div>
          <div class="logbox" style="max-height:260px">{{ panelLog }}</div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-h"><span class="card-t">Смена пароля администратора</span></div>
          <form class="modal-form" @submit.prevent>
            <div class="field">
              <label>Текущий пароль</label>
              <input v-model="pwOld" type="password" autocomplete="current-password">
            </div>
            <PwField v-model="pwNew" label="Новый пароль"
                     hint="Минимум 8 символов. Нажмите кнопку генерации — надёжный пароль создастся сам, скопируйте его." />
            <button class="btn primary" style="margin-top:10px" @click="changePass()">Сменить пароль</button>
          </form>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Безопасность входа</span></div>
          <div class="row" style="align-items:center;gap:10px;padding:2px 0 8px">
            <span class="muted" style="font-size:13px">Двухфакторная аутентификация (приложение-аутентификатор)</span>
            <span v-if="totpOn" class="pill ok">включена</span>
            <span v-else class="pill warn">выключена</span>
            <button v-if="totpOn" class="btn sm" @click="totpDisableDlg()">Выключить</button>
            <button v-else class="btn sm primary" @click="totpEnableDlg()">Включить</button>
          </div>
          <div class="faint" style="font-size:12px;line-height:1.55;margin-bottom:6px">Второй шаг защиты: кроме пароля нужен код из приложения (Google Authenticator, Яндекс.Ключ и т.п.). Панель доступна из интернета — с 2FA украденный пароль не даст войти.</div>
          <b style="font-size:13px">Активные сессии</b>
          <template v-if="sessions.length">
            <div v-for="x in sessions" :key="x.sid"
                 class="row" style="align-items:center;gap:8px;padding:7px 0;border-top:1px solid var(--border)">
              <div style="flex:1;min-width:0">
                <b>{{ shortUa(x.ua) }}</b>
                <div class="muted" style="font-size:12px">{{ x.ip || '' }}<template v-if="seenWhen(x)"> · активность {{ seenWhen(x) }}</template></div>
              </div>
              <span v-if="x.sid === curSid" class="pill ok">это вы</span>
              <button v-else class="btn sm" @click="sessionDrop(x.sid)">Завершить</button>
            </div>
          </template>
          <div v-else class="empty">Нет активных сессий</div>
          <div style="margin-top:8px">
            <button class="btn" @click="dropOtherSessions()"><UiIcon name="logout" :size="14" /> Выйти на всех других устройствах</button>
          </div>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Перенос на другой сервер</span></div>
          <div class="faint" style="font-size:12.5px;line-height:1.6;margin-bottom:8px">Файл настроек содержит: параметры панели, задачи планировщика, список сайтов (без файлов), почтовые домены и адреса ящиков, настройки уведомлений. Пароли баз и ящиков панель не хранит — их задаёте заново; SSL-сертификаты выпустите на новом сервере. Файл содержит пароль SMTP и ключ 2FA — храните бережно.</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn primary" @click="exportSettings()"><UiIcon name="down" :size="15" /> Скачать настройки</button>
            <button class="btn" @click="importDlg()"><UiIcon name="up" :size="15" /> Импортировать из файла</button>
          </div>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Перезагрузка сервера</span></div>
          <div style="font-size:13px;line-height:1.6;color:var(--muted)">Полная перезагрузка сервера: панель и сайты будут недоступны 1–2 минуты.</div>
          <button class="btn danger" style="margin-top:10px" @click="serverRebootDlg()"><UiIcon name="refresh" :size="15" /> Перезагрузить сервер</button>
        </div>

        <div id="disk-card" class="card">
          <template v-if="disk && disk.demo">
            <div class="card-h"><span class="card-t">Диск</span></div>
            <div class="notice info">демо-данные — на рабочем сервере здесь будет разбор занятого места</div>
          </template>
          <template v-else-if="disk">
            <div class="card-h">
              <span class="card-t">Диск</span>
              <span class="card-spacer"></span>
              <span class="pill" :class="disk.percent > 85 ? 'err' : disk.percent > 70 ? 'warn' : 'ok'">занято {{ disk.percent }}% · {{ disk.used_gb }} из {{ disk.total_gb }} ГБ</span>
            </div>
            <div style="padding:6px 8px">
              <div v-for="(t, i) in (disk.top || [])" :key="i"
                   class="row" style="align-items:center;gap:10px;padding:3px 0">
                <span style="width:200px" :title="t.path">{{ t.label }}</span>
                <b style="width:90px;text-align:right">{{ t.gb }} ГБ</b>
                <span class="muted faint" style="font-size:11.5px">{{ t.path }}</span>
              </div>
            </div>
            <div class="row" style="padding:0 8px 10px;flex-wrap:wrap;gap:6px">
              <button v-if="disk.cleanable && disk.cleanable.apt" class="btn sm" @click="diskClean('apt')">Очистить кэш apt</button>
              <button v-if="disk.cleanable && disk.cleanable.journal" class="btn sm" @click="diskClean('journal')">Урезать журнал (7 дней)</button>
              <button v-if="disk.cleanable && disk.cleanable.tmp" class="btn sm" @click="diskClean('tmp')">Очистить tmp панели</button>
              <button v-if="disk.cleanable && disk.cleanable.backups" class="btn sm" @click="diskClean('backups')">Удалить старые копии</button>
            </div>
          </template>
          <div v-else class="card-h"><span class="card-t">Диск: куда уходит место</span></div>
        </div>

        <div class="card">
          <div class="card-h"><span class="card-t">Как это работает</span></div>
          <div style="font-size:13px;line-height:1.7;color:var(--muted)">
            Рабочий режим: панель запускается от root (обычно как systemd-служба hostpanel) и управляет nginx, Apache, PHP-FPM, systemd, certbot и MySQL напрямую. Все изменения конфигов валидируются (nginx -t и т.п.) и откатываются при ошибке, каждая операция пишется в журнал аудита.<br><br>
            Демо-режим: полностью безопасен, конфиги не трогаются, а сайты, логи и статистика создаются в домашней папке панели.
          </div>
        </div>
      </div>
    </div>

    <!-- 2FA: включение -->
    <AppModal :open="totpDlg" title="Включить двухфакторную аутентификацию" wide @close="totpDlg = false">
      <div class="faint" style="font-size:13px;line-height:1.6;margin-bottom:8px">
        1. Откройте приложение-аутентификатор и отсканируйте код (или введите ключ вручную).<br>
        2. Введите 6-значный код из приложения для подтверждения.
      </div>
      <div style="text-align:center;min-height:60px;background:#fff;border-radius:10px;padding:10px;margin-bottom:10px">
        <div v-if="!totpQr" class="muted" style="color:#333">Создаём QR-код…</div>
        <!-- SVG QR-кода с сервера -->
        <div v-else v-html="totpQr"></div>
      </div>
      <div class="field">
        <label>Ключ для ручного ввода</label>
        <div class="row" style="align-items:center;gap:8px">
          <b class="mono" style="flex:1;word-break:break-all">{{ totpSecret }}</b>
          <button class="btn sm" @click="copyText(totpSecret, $event.currentTarget as HTMLElement)"><UiIcon name="file" :size="13" /></button>
        </div>
      </div>
      <div class="field">
        <label>Код из приложения (6 цифр)</label>
        <input id="totp-code" v-model="totpCode" type="text" class="mono" maxlength="6" inputmode="numeric" placeholder="123456" autocomplete="one-time-code">
      </div>
      <template #footer>
        <button class="btn primary" @click="totpConfirm()"><UiIcon name="check" :size="15" /> Включить</button>
        <button class="btn" @click="totpDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- 2FA: выключение -->
    <AppModal :open="totpDisDlg" title="Выключить 2FA" wide @close="totpDisDlg = false">
      <div class="notice warn">Без 2FA для входа хватит одного пароля — панель станет уязвимее.</div>
      <div class="field">
        <label>Подтвердите текущим паролем</label>
        <input v-model="totpPw" type="password" autocomplete="current-password">
      </div>
      <template #footer>
        <button class="btn danger" @click="totpDisable()">Выключить</button>
        <button class="btn" @click="totpDisDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- импорт настроек -->
    <AppModal :open="impDlg" title="Импорт настроек" wide @close="impDlg = false">
      <div class="notice info">Выберите файл, скачанный на старом сервере. Настройки применятся, задачи заменятся, отсутствующие сайты будут созданы (файлы и базы в них загрузите отдельно).</div>
      <div class="field">
        <label>Файл настроек (JSON)</label>
        <input type="file" accept=".json,application/json" @change="onImportFile">
      </div>
      <div v-if="impPreview" class="notice ok">{{ impPreview }}</div>
      <div v-for="(x, i) in impReport" :key="i" class="muted" style="font-size:12.5px">• {{ x }}</div>
      <template #footer>
        <button v-if="impReady" class="btn primary" @click="importApply()"><UiIcon name="check" :size="15" /> Применить</button>
        <button class="btn" @click="impDlg = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
