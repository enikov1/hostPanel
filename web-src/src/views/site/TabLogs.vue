<script setup lang="ts">
/* ============ Вкладка «Логи» карточки сайта: access/error + фильтры ============ */
import { nextTick, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import { confirmDlg } from '../../lib/confirm';
import UiIcon from '../../components/UiIcon.vue';
import { siteState } from './siteShared';

const logKind = ref<'access' | 'error'>('access');
const lines = ref<string[]>([]);
const total = ref(0);
const logBox = ref<HTMLElement | null>(null);

/* фильтры (как прежний filter-bar) */
const fQ = ref('');
const fCode = ref('');
const fIp = ref('');
const fUrl = ref('');
const fSince = ref('');
const fUntil = ref('');
const fErr = ref(false);
const fBots = ref(false);

const CODES = ['200', '301', '302', '304', '403', '404', '429', '500', '502', '503'];

/* подсветка строк ошибок (как прежний renderLogBox) */
function lineCls(l: string): string {
  if (/\[error\]| 500 | 502 | 503 | 40[0-9] /.test(l)) {
    if (logKind.value === 'error' || / 5\d\d /.test(l)) return 'le';
    if (/ 40\d /.test(l)) return 'lw';
  }
  return '';
}

async function siteLog(kind: 'access' | 'error'): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  logKind.value = kind;
  let d: any;
  try { d = await api('/api/site/' + s.id + '/logs?type=' + kind); }
  catch (e) { toastErr(e); return; }
  renderLogBox(d);
}

function siteLogRefresh(): void { void siteLog(logKind.value); }

async function renderLogBox(d: any): Promise<void> {
  lines.value = d.lines || [];
  total.value = d.total || 0;
  await nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight;
  });
}

async function applyLogFilters(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const p = new URLSearchParams();
  p.set('type', logKind.value || 'access');
  if (fQ.value) p.set('q', fQ.value);
  if (fCode.value) p.set('code', fCode.value);
  if (fIp.value) p.set('ip', fIp.value);
  if (fUrl.value) p.set('url', fUrl.value);
  if (fSince.value) p.set('since', fSince.value);
  if (fUntil.value) p.set('until', fUntil.value);
  if (fErr.value) p.set('errors_only', '1');
  if (fBots.value) p.set('bots_only', '1');
  try {
    const d = await api('/api/site/' + s.id + '/logs?' + p.toString());
    void renderLogBox(d);
  } catch (e) { toastErr(e); }
}

/* очистка журнала */
function logsClear(kind: 'access' | 'error'): void {
  const s = siteState.site;
  if (!s) return;
  confirmDlg('Очистить журнал',
    'Все записи журнала «' + (kind === 'access' ? 'Access' : 'Error') + '» сайта ' +
    s.domain + ' будут удалены. Это безопасно — журнал начнёт заполняться заново.',
    async () => {
      try {
        const r = await api('/api/site/' + s.id + '/logs_clear', { method: 'POST', body: { kind } });
        toast(r.message);
        void siteLog(kind);
      } catch (e) { toastErr(e); }
    }, false);
}

onMounted(() => { /* как в оригинале: журнал не грузится, пока не выбран */ });
</script>

<template>
  <div>
    <div class="row" style="margin-bottom:10px">
      <button class="btn sm" :class="{ primary: logKind === 'access' }" @click="siteLog('access')">Access-лог</button>
      <button class="btn sm" :class="{ primary: logKind === 'error' }" @click="siteLog('error')">Error-лог</button>
      <span class="spacer"></span>
      <span class="muted" style="font-size:12.5px">последние 300 строк</span>
      <button class="btn sm danger" @click="logsClear('access')">Очистить access</button>
      <button class="btn sm danger" @click="logsClear('error')">Очистить error</button>
    </div>

    <div class="filter-bar">
      <div class="f grow">
        <label style="margin:0 0 4px">Поиск по тексту</label>
        <input v-model="fQ" type="text" placeholder="подстрока в строке лога" @input="applyLogFilters()">
      </div>
      <div class="f">
        <label style="margin:0 0 4px">Код</label>
        <select v-model="fCode" @change="applyLogFilters()">
          <option value="">все</option>
          <option v-for="c in CODES" :key="c">{{ c }}</option>
        </select>
      </div>
      <div class="f">
        <label style="margin:0 0 4px">IP</label>
        <input v-model="fIp" type="text" placeholder="1.2.3.4" @input="applyLogFilters()">
      </div>
      <div class="f">
        <label style="margin:0 0 4px">URL содержит</label>
        <input v-model="fUrl" type="text" placeholder="/wp-admin" @input="applyLogFilters()">
      </div>
      <div class="f">
        <label style="margin:0 0 4px">С даты</label>
        <input v-model="fSince" type="date" @change="applyLogFilters()">
      </div>
      <div class="f">
        <label style="margin:0 0 4px">По дату</label>
        <input v-model="fUntil" type="date" @change="applyLogFilters()">
      </div>
      <label class="check" style="margin:0">
        <input v-model="fErr" type="checkbox" @change="applyLogFilters()"> только ошибки (4xx/5xx)</label>
      <label class="check" style="margin:0">
        <input v-model="fBots" type="checkbox" @change="applyLogFilters()"> только боты</label>
      <button class="btn sm" @click="siteLogRefresh()">
        <UiIcon name="refresh" :size="13" /> Обновить</button>
    </div>

    <div class="muted" style="font-size:12px;margin-bottom:6px">
      показано {{ lines.length }} из {{ total }} строк</div>

    <div ref="logBox" class="logbox">
      <template v-if="lines.length">
        <div v-for="(l, i) in lines" :key="i" :class="lineCls(l)">{{ l }}</div>
      </template>
      <template v-else>Выберите журнал…</template>
    </div>
  </div>
</template>
