<script setup lang="ts">
/* ============ Вкладка «Логи» карточки сайта: access/error + фильтры ============
   Один журнал активен, одна кнопка очистки — для активного журнала.
   Автообновление, раздельные фильтры, явные пустые состояния. */
import { nextTick, onMounted, onBeforeUnmount, ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import { confirmDlg } from '../../lib/confirm';
import UiIcon from '../../components/UiIcon.vue';
import UiSelect from '../../components/ui/UiSelect.vue';
import UiCheckbox from '../../components/ui/UiCheckbox.vue';
import { siteState } from './siteShared';

const logKind = ref<'access' | 'error'>('access');
const lines = ref<string[]>([]);
const total = ref(0);
const loaded = ref(false);
const logBox = ref<HTMLElement | null>(null);

/* фильтры */
const fQ = ref('');
const fCode = ref('');
const fIp = ref('');
const fUrl = ref('');
const fSince = ref('');
const fUntil = ref('');
const fErr = ref(false);
const fBots = ref(false);
const filtersOn = ref(false);

const auto = ref(false);
let autoTimer: ReturnType<typeof setInterval> | null = null;

const CODES = ['200', '301', '302', '304', '403', '404', '429', '500', '502', '503'];

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
  loaded.value = true;
  await nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight;
  });
}

function resetFilters(): void {
  fQ.value = ''; fCode.value = ''; fIp.value = ''; fUrl.value = '';
  fSince.value = ''; fUntil.value = ''; fErr.value = false; fBots.value = false;
  applyLogFilters();
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
  filtersOn.value = !!(fQ.value || fCode.value || fIp.value || fUrl.value ||
    fSince.value || fUntil.value || fErr.value || fBots.value);
  try {
    const d = await api('/api/site/' + s.id + '/logs?' + p.toString());
    void renderLogBox(d);
  } catch (e) { toastErr(e); }
}

/** Очистка ТОЛЬКО активного журнала — чтобы нельзя было ошибиться. */
function logsClear(): void {
  const s = siteState.site;
  if (!s) return;
  const kind = logKind.value;
  confirmDlg('Очистить ' + (kind === 'access' ? 'access' : 'error') + '-журнал',
    'Все записи журнала «' + (kind === 'access' ? 'Access' : 'Error') +
    '» сайта ' + s.domain + ' будут удалены. Это безопасно — журнал начнёт ' +
    'заполняться заново. Активный сайт может дописать новые строки уже через ' +
    'пару секунд — это нормально.',
    async () => {
      try {
        const r = await api('/api/site/' + s.id + '/logs_clear',
          { method: 'POST', body: { kind } });
        toast(r.message);
        void siteLog(kind);
      } catch (e) { toastErr(e); }
    }, false);
}

function toggleAuto(): void {
  if (auto.value) {
    autoTimer = setInterval(() => {
      void api('/api/site/' + (siteState.site?.id || 0) + '/logs?type=' +
        logKind.value).then(renderLogBox).catch(() => { /* тихо */ });
    }, 10000);
  } else if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
  }
}

onMounted(() => { void siteLog('access'); });
onBeforeUnmount(() => { if (autoTimer) clearInterval(autoTimer); });
</script>

<template>
  <div>
    <!-- панель журнала -->
    <div class="card" style="margin:0 0 10px;padding:12px 14px">
      <div class="row" style="gap:10px;flex-wrap:wrap;align-items:center">
        <div class="row" style="gap:0">
          <button class="btn sm" :class="{ primary: logKind === 'access' }"
                  style="border-radius:4px 0 0 4px"
                  @click="siteLog('access')">Access-лог</button>
          <button class="btn sm" :class="{ primary: logKind === 'error' }"
                  style="border-radius:0 4px 4px 0;margin-left:-1px"
                  @click="siteLog('error')">Error-лог</button>
        </div>
        <span class="pill gray" v-if="loaded">
          показано {{ lines.length }} из {{ total }}</span>
        <span style="width:1px;height:22px;background:var(--border)"></span>
        <UiCheckbox v-model="auto" @update:model-value="toggleAuto()">
          авто-обновление 10 сек</UiCheckbox>
        <span style="flex:1"></span>
        <button class="btn sm" @click="siteLogRefresh()">
          <UiIcon name="refresh" :size="13" /> Обновить</button>
        <button class="btn sm danger" @click="logsClear()">
          <UiIcon name="trash" :size="13" />
          Очистить {{ logKind === 'access' ? 'access' : 'error' }}-журнал
        </button>
      </div>
    </div>

    <!-- фильтры -->
    <div class="card" style="margin:0 0 10px;padding:12px 14px">
      <div class="row" style="gap:10px;flex-wrap:wrap;align-items:flex-end">
        <div class="f grow" style="min-width:200px">
          <label style="margin:0 0 4px">Поиск по тексту</label>
          <input v-model="fQ" type="text" placeholder="подстрока в строке лога"
                 @input="applyLogFilters()">
        </div>
        <div class="f" style="width:110px;margin:0">
          <label style="margin:0 0 4px">Код</label>
          <UiSelect v-model="fCode" @change="applyLogFilters()"
                    :options="[{ value: '', label: 'все' },
                      ...CODES.map(c => ({ value: c, label: c }))]" />
        </div>
        <div class="f" style="width:140px;margin:0">
          <label style="margin:0 0 4px">IP</label>
          <input v-model="fIp" type="text" placeholder="1.2.3.4"
                 @input="applyLogFilters()">
        </div>
        <div class="f grow" style="min-width:160px;margin:0">
          <label style="margin:0 0 4px">URL содержит</label>
          <input v-model="fUrl" type="text" placeholder="/wp-admin"
                 @input="applyLogFilters()">
        </div>
        <div class="f" style="width:150px;margin:0">
          <label style="margin:0 0 4px">С даты</label>
          <input v-model="fSince" type="date" @change="applyLogFilters()">
        </div>
        <div class="f" style="width:150px;margin:0">
          <label style="margin:0 0 4px">По дату</label>
          <input v-model="fUntil" type="date" @change="applyLogFilters()">
        </div>
      </div>
      <div class="row" style="gap:14px;margin-top:8px;flex-wrap:wrap">
        <UiCheckbox v-model="fErr" @update:model-value="applyLogFilters()">
          только ошибки (4xx/5xx)</UiCheckbox>
        <UiCheckbox v-model="fBots" @update:model-value="applyLogFilters()">
          только боты</UiCheckbox>
        <button v-if="filtersOn" class="btn sm" @click="resetFilters()">
          <UiIcon name="x" :size="13" /> Сбросить фильтры</button>
      </div>
    </div>

    <!-- журнал -->
    <div ref="logBox" class="logbox">
      <template v-if="!loaded">Выберите журнал…</template>
      <template v-else-if="lines.length">
        <div v-for="(l, i) in lines" :key="i" :class="lineCls(l)">{{ l }}</div>
      </template>
      <template v-else>
        <div style="padding:18px;text-align:center;color:var(--muted)">
          Журнал пуст — он был очищен или в нём ещё нет новых записей.
          <template v-if="filtersOn"><br>Попробуйте сбросить фильтры.</template>
        </div>
      </template>
    </div>
  </div>
</template>
