<script setup lang="ts">
/* ============ Вкладка «Статистика» карточки сайта ============
   Фильтры (период, код, IP, URL, только ошибки/боты), графики
   запросов/трафика и почасовой активности, коды статусов,
   топ страниц / IP / ботов / источников / User-Agent. */
import { nextTick, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { drawLine, cssVar } from '../../lib/charts';
import { fmtSize } from '../../lib/format';
import StatCard from '../../components/StatCard.vue';
import UiIcon from '../../components/UiIcon.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const err = ref('');
const st = ref<any | null>(null);
const cv = ref<HTMLCanvasElement | null>(null);
const cvHours = ref<HTMLCanvasElement | null>(null);

/* ---------- фильтры ---------- */
const fDays = ref(14);
const fCode = ref('');
const fIp = ref('');
const fUrl = ref('');
const fErrors = ref(false);
const fBots = ref(false);
const filterActive = ref(false);
let applyTimer: ReturnType<typeof setTimeout> | null = null;

function codeClass(code: string): string {
  if (code.startsWith('2')) return 'ok';
  if (code.startsWith('3')) return 'gray';
  if (code.startsWith('4')) return 'warn';
  return 'err';
}

function pick(list: Array<[string, number]>, code: string): number {
  const found = (list || []).find((c) => c[0] === code);
  return found ? found[1] : 0;
}

function err4xx(): number {
  return (st.value?.codes || [])
    .filter((c: any[]) => c[0].startsWith('4'))
    .reduce((a: number, c: any[]) => a + c[1], 0);
}
function err5xx(): number {
  return (st.value?.codes || [])
    .filter((c: any[]) => c[0].startsWith('5'))
    .reduce((a: number, c: any[]) => a + c[1], 0);
}

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  err.value = '';
  try {
    const q = new URLSearchParams();
    q.set('days', String(fDays.value));
    if (fCode.value) q.set('code', fCode.value);
    if (fIp.value.trim()) q.set('ip', fIp.value.trim());
    if (fUrl.value.trim()) q.set('url', fUrl.value.trim());
    if (fErrors.value) q.set('errors_only', '1');
    if (fBots.value) q.set('bots_only', '1');
    filterActive.value =
      !!(fCode.value || fIp.value.trim() || fUrl.value.trim() ||
         fErrors.value || fBots.value);
    const d = await api('/api/site/' + s.id + '/stats?' + q.toString());
    st.value = d.stats;
    loading.value = false;   // сначала рендерим canvas, потом рисуем
    await nextTick(draw);
  } catch (e: any) {
    err.value = e.message || String(e);
  }
  loading.value = false;
}

function applyFilters(): void { load(); }

function resetFilters(): void {
  fCode.value = '';
  fIp.value = '';
  fUrl.value = '';
  fErrors.value = false;
  fBots.value = false;
  applyFilters();
}

/** Автоприменение с задержкой — чтобы не дёргать парс на каждый символ. */
function debouncedApply(): void {
  if (applyTimer) clearTimeout(applyTimer);
  applyTimer = setTimeout(applyFilters, 700);
}

function setDays(n: number): void {
  fDays.value = n;
  applyFilters();
}

function draw(): void {
  if (!st.value) return;
  const labels = (st.value.series || []).map((x: any) =>
    x.day.slice(8) + '.' + x.day.slice(5, 7));
  if (cv.value) {
    drawLine(cv.value, [
      { data: st.value.series.map((x: any) => x.requests),
        color: cssVar('--primary'), fill: true },
      { data: st.value.series.map((x: any) => +(x.bytes / 1048576).toFixed(2)),
        color: cssVar('--info') },
    ], { labels: [labels[0] || '', labels[labels.length - 1] || ''] });
  }
  if (cvHours.value) {
    const hrs = st.value.hours || [];
    // все 24 часа подряд, нули включительно
    const map: Record<string, number> = {};
    hrs.forEach((h: any[]) => { map[h[0]] = h[1]; });
    const data: number[] = [];
    const hLabels: string[] = [];
    for (let i = 0; i < 24; i++) {
      const key = ('0' + i).slice(-2) + ':00';
      data.push(map[key] || 0);
      hLabels.push(key);
    }
    drawLine(cvHours.value, [
      { data, color: cssVar('--ok'), fill: true },
    ], { labels: [hLabels[0], hLabels[23]] });
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null;
onMounted(() => { load(); });
</script>

<template>
  <div>
    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="err" class="empty">нет данных: {{ err }}</div>
    <template v-else-if="st">
      <!-- фильтры -->
      <div class="card" style="margin:0 0 12px">
        <div class="row" style="gap:8px;flex-wrap:wrap;align-items:center">
          <span class="muted" style="font-size:12.5px">Период:</span>
          <button v-for="n in [7, 14, 30, 90]" :key="n" class="btn sm"
                  :class="fDays === n ? 'primary' : ''"
                  @click="setDays(n)">{{ n }} дн.</button>
          <span style="width:1px;height:22px;background:var(--border)"></span>
          <select v-model="fCode" class="sm" style="width:auto"
                  @change="applyFilters()">
            <option value="">любой код</option>
            <option value="200">200 OK</option>
            <option value="301">301 редирект</option>
            <option value="302">302 редирект</option>
            <option value="404">404 не найдено</option>
            <option value="403">403 запрещено</option>
            <option value="500">500 ошибка</option>
          </select>
          <input v-model="fIp" class="sm" style="width:140px"
                 placeholder="IP-адрес" @input="debouncedApply()">
          <input v-model="fUrl" class="sm" style="width:170px"
                 placeholder="подстрока в URL" @input="debouncedApply()">
          <label class="check" style="margin:0">
            <input v-model="fErrors" type="checkbox" @change="applyFilters()">
            только ошибки (4xx/5xx)
          </label>
          <label class="check" style="margin:0">
            <input v-model="fBots" type="checkbox" @change="applyFilters()">
            только боты
          </label>
          <button class="btn sm" @click="applyFilters()">
            <UiIcon name="refresh" :size="13" /> Применить
          </button>
          <button v-if="filterActive" class="btn sm" @click="resetFilters()">
            <UiIcon name="x" :size="13" /> Сбросить
          </button>
        </div>
        <div v-if="filterActive" class="faint"
             style="font-size:11.5px;margin-top:6px">
          Фильтр активен — статистика считается по хвосту журнала (до 20 МБ),
          без фильтра показываются данные за всё время наблюдения.
        </div>
      </div>

      <!-- карточки -->
      <div class="grid g4" style="margin-bottom:12px">
        <StatCard ic="activity" cls="c1"
                  :val="Number(st.requests).toLocaleString('ru-RU')"
                  label="Запросов" />
        <StatCard ic="up" cls="c2" :val="fmtSize(st.bytes)" label="Трафик" />
        <StatCard ic="globe" cls="c3"
                  :val="Number(st.unique_ips).toLocaleString('ru-RU')"
                  label="Уникальных IP" />
        <StatCard ic="file" cls="c4"
                  :val="err4xx().toLocaleString('ru-RU') + ' / ' +
                        err5xx().toLocaleString('ru-RU')"
                  label="Ошибок 4xx / 5xx" />
        <StatCard ic="cpu" cls="c3"
                  :val="Number(st.bots).toLocaleString('ru-RU')"
                  :label="'Ботов · ' +
                    (st.requests ? Math.round(st.bots * 100 / st.requests) : 0) + '%'" />
        <StatCard ic="stat" cls="c1"
                  :val="st.requests ? fmtSize(st.bytes / st.requests) : '—'"
                  label="Средний ответ" />
        <StatCard ic="clock" cls="c2"
                  :val="st.requests && st.series.length
                    ? Math.round(st.requests / st.series.length)
                        .toLocaleString('ru-RU')
                    : 0"
                  label="Запросов в день (средн.)" />
        <StatCard ic="shield" cls="c4"
                  :val="st.requests ? Math.round(err4xx() + err5xx() != 0
                    ? (err4xx() + err5xx()) * 100 / st.requests : 0) + '%' : '0%'"
                  label="Доля ошибок" />
      </div>

      <!-- графики -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Запросы и трафик по дням</span>
          <span style="margin-left:auto;display:flex;gap:14px;font-size:12px">
            <span><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--primary);margin-right:5px"></i>запросы</span>
            <span><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--info);margin-right:5px"></i>трафик, МБ</span>
          </span>
        </div>
        <canvas ref="cv" class="chart" style="height:220px"></canvas>
      </div>

      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Активность по часам суток</span>
          <span class="faint" style="margin-left:auto;font-size:12px">когда сайт загружен сильнее всего</span>
        </div>
        <canvas ref="cvHours" class="chart" style="height:160px"></canvas>
      </div>

      <!-- коды статусов -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Коды ответов</span></div>
        <template v-if="st.codes.length">
          <div v-for="c in st.codes" :key="c[0]" class="row"
               style="gap:10px;align-items:center;padding:4px 0">
            <span class="pill" :class="codeClass(c[0])" style="width:52px;text-align:center">{{ c[0] }}</span>
            <div class="bar" style="flex:1">
              <i :class="codeClass(c[0])"
                 :style="{ width: Math.max(2, c[1] * 100 / st.codes[0][1]) + '%',
                           background: codeClass(c[0]) === 'gray' ? 'var(--muted)' : '' }"></i>
            </div>
            <span class="mono" style="width:80px;text-align:right">
              {{ c[1].toLocaleString('ru-RU') }}</span>
            <span class="faint" style="width:52px;text-align:right">
              {{ st.requests ? Math.round(c[1] * 100 / st.requests) : 0 }}%</span>
          </div>
        </template>
        <div v-else class="empty">нет данных</div>
      </div>

      <!-- методы и источники -->
      <div class="split" style="margin-bottom:12px">
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">HTTP-методы</span></div>
          <div v-if="st.methods && st.methods.length" class="row"
               style="gap:8px;flex-wrap:wrap">
            <span v-for="m in st.methods" :key="m[0]" class="pill gray">
              {{ m[0] }} · {{ m[1].toLocaleString('ru-RU') }}</span>
          </div>
          <div v-else class="empty">нет данных</div>
        </div>
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Откуда приходят (рефереры)</span></div>
          <template v-if="st.top_refs && st.top_refs.length">
            <div v-for="(r, i) in st.top_refs" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono">{{ r[0] }}</span>
              <span class="pill gray">{{ r[1].toLocaleString('ru-RU') }}</span>
            </div>
          </template>
          <div v-else class="empty">прямые заходы</div>
        </div>
      </div>

      <!-- топы: страницы, IP, боты/UA -->
      <div class="split">
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Популярные страницы</span></div>
          <template v-if="st.top_urls.length">
            <div v-for="(u, i) in st.top_urls" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono" style="word-break:break-all">{{ u[0] }}</span>
              <span class="pill gray" style="flex-shrink:0;margin-left:8px">{{ u[1].toLocaleString('ru-RU') }}</span>
            </div>
          </template>
          <div v-else class="empty">нет данных</div>
        </div>
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Активные IP</span></div>
          <template v-if="st.top_ips.length">
            <div v-for="(u, i) in st.top_ips" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono">{{ u[0] }}</span>
              <span class="pill gray">{{ u[1].toLocaleString('ru-RU') }}</span>
            </div>
          </template>
          <div v-else class="empty">нет данных</div>
        </div>
      </div>

      <div class="split" style="margin-top:12px">
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">User-Agent (клиенты)</span></div>
          <template v-if="st.top_uas && st.top_uas.length">
            <div v-for="(u, i) in st.top_uas" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono" style="word-break:break-all">{{ u[0] }}</span>
              <span class="pill gray" style="flex-shrink:0;margin-left:8px">{{ u[1].toLocaleString('ru-RU') }}</span>
            </div>
          </template>
          <div v-else class="empty">нет данных</div>
        </div>
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Боты</span></div>
          <div class="kv">
            <b>Запросов ботов</b><span>{{ Number(st.bots).toLocaleString('ru-RU') }}
              ({{ st.requests ? Math.round(st.bots * 100 / st.requests) : 0 }}%)</span>
            <b>Людей/систем</b><span>{{ Number(st.requests - st.bots).toLocaleString('ru-RU') }}</span>
          </div>
          <div class="faint" style="font-size:11.5px;margin-top:6px">
            Боты определяются по User-Agent (bot, crawler, spider). Грубые сканеры
            видно во вкладке «Фильтры» — там настраивается их блокировка.
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
