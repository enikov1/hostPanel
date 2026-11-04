<script setup lang="ts">
/* ============ Страница «Обзор» (старый id 'overview') ============ */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api/client';
import { toastErr } from '../lib/toast';
import { fmtSize, fmtDate, humanUptime } from '../lib/format';
import { drawLine, cssVar } from '../lib/charts';
import { me } from '../stores';
import StatCard from '../components/StatCard.vue';
import UiIcon from '../components/UiIcon.vue';
import type { OverviewData, SvcInfo, NotificationItem } from './monitoring/types';

const router = useRouter();

const d = ref<OverviewData | null>(null);
const cpuCanvas = ref<HTMLCanvasElement | null>(null);
let timer: ReturnType<typeof setInterval> | null = null;

const m = computed(() => d.value?.metrics);
const hist = computed<number[]>(() => {
  const h = m.value?.hist || [];
  return h.length ? h : [0, 0];
});
const sitesLoad = computed(() => d.value?.sites_load || { cpu: 0, mem_mb: 0, php_workers: 0 });
const svcTop = computed<SvcInfo[]>(() =>
  ((d.value?.services || []) as SvcInfo[]).filter((s) => s.exists).slice(0, 7));
const notices = computed<NotificationItem[]>(() =>
  ((d.value?.notifications || []) as NotificationItem[]).slice(0, 6));

/* ---- чек-лист «Первые шаги»: от нуля до готового сайта ---- */
interface QsStep { done: boolean; t: string; d: string; path: string; query?: Record<string, string> }
const quickStart = computed<QsStep[] | null>(() => {
  if (!d.value) return null;
  const svcs = d.value.services || [];
  const phpOk = svcs.some((s) => s.exists && /^php[\d.]+-fpm$/.test(s.name));
  const mailOk = svcs.some((s) => s.exists && (s.name === 'postfix' || s.name === 'dovecot'));
  const steps: QsStep[] = [
    { done: !me.must_change_password, t: 'Сменить стандартный пароль панели',
      d: 'Вход admin/admin небезопасен', path: '/settings' },
    { done: phpOk, t: 'Установить PHP (или Node.js) для сайта',
      d: 'Раздел «Установка ПО» — одна кнопка', path: '/software' },
    { done: d.value.sites_count > 0, t: 'Создать первый сайт',
      d: 'Мастер за минуту соберёт сайт и базу', path: '/sites', query: { wizard: '1' } },
    { done: d.value.dbs_count > 0, t: 'Создать базу данных',
      d: 'Нужна для WordPress, магазинов и т.п.', path: '/databases', query: { create: '1' } },
    { done: mailOk, t: 'Настроить почту на своём домене',
      d: 'Свой ящик вида info@ваш-домен.ru', path: '/mail' },
    { done: d.value.backups_count > 0, t: 'Сделать первую резервную копию',
      d: 'Страховка от потери данных', path: '/backups' },
  ];
  return steps;
});
const qsLeft = computed(() => (quickStart.value || []).filter((s) => !s.done).length);

function qsGo(s: QsStep): void {
  router.push(s.query ? { path: s.path, query: s.query } : s.path);
}

function goSitesWizard(): void {
  router.push({ path: '/sites', query: { wizard: '1' } });
}
function goCreateBackup(): void {
  router.push({ path: '/backups', query: { create: '1' } });
}
function goPackages(): void {
  router.push('/packages');
}
function goServices(): void {
  router.push('/services');
}

/* ---- данные ---- */
async function load(first = false): Promise<void> {
  try {
    const r = await api('/api/overview');
    d.value = r;
    await nextTick();
    drawChart();
  } catch (e) {
    if (first) toastErr(e); /* поллинг уже идёт — ошибки тихо */
  }
}

function drawChart(): void {
  drawLine(cpuCanvas.value,
    [{ data: hist.value.length ? hist.value : [0], color: cssVar('--primary'), fill: true }],
    { max: 100, labels: ['60 с назад', 'сейчас'] });
}

async function clearNotices(): Promise<void> {
  try {
    await api('/api/notifications/read', { method: 'POST', body: {} });
    await load();
  } catch (e) { toastErr(e); }
}

function cpuBar(): string {
  const cpu = m.value?.cpu ?? 0;
  return cpu > 85 ? 'err' : cpu > 60 ? 'warn' : 'ok';
}
function ramBar(): string {
  return (m.value?.ram.percent ?? 0) > 90 ? 'err' : 'ok';
}
function diskBar(): string {
  const p = m.value?.disk.percent ?? 0;
  return p > 90 ? 'err' : p > 75 ? 'warn' : 'ok';
}
function svcPillCls(s: SvcInfo): string {
  return s.state === 'active' ? 'ok' : s.state === 'inactive' ? 'gray' : 'err';
}
function svcPillTxt(s: SvcInfo): string {
  return s.state === 'active' ? 'работает' : 'остановлена';
}

onMounted(() => {
  load(true);
  timer = setInterval(() => { void load(); }, 5000);
});
onBeforeUnmount(() => { if (timer) clearInterval(timer); });
</script>

<template>
  <div v-table>
    <div v-if="!d" class="empty">Загрузка…</div>
    <template v-else>
      <!-- чек-лист «Первые шаги» -->
      <div v-if="qsLeft === 0" class="notice ok" style="margin-bottom:16px">
        <UiIcon name="check" :size="15" />
        Все первые шаги выполнены — сервер полностью готов к работе. Ниже — текущее состояние.
      </div>
      <div v-else class="card" style="margin-bottom:16px">
        <div class="card-h"><span class="card-t">Первые шаги</span><span class="card-spacer"></span>
          <span class="pill info">осталось шагов: {{ qsLeft }}</span></div>
        <div v-for="s in quickStart" :key="s.t" class="qs-item">
          <span class="qs-ico" :class="s.done ? 'done' : 'todo'">
            <UiIcon :name="s.done ? 'check' : 'clock'" :size="14" />
          </span>
          <span class="qs-t" :style="s.done ? 'text-decoration:line-through;color:var(--faint)' : ''">
            {{ s.t }}<small v-if="!s.done">{{ s.d }}</small>
          </span>
          <button v-if="!s.done" class="btn sm" @click="qsGo(s)">Перейти →</button>
        </div>
      </div>

      <!-- метрики -->
      <div class="grid g4" style="margin-bottom:16px">
        <StatCard ic="cpu" cls="c1" :val="(m?.cpu ?? 0) + '%'"
                  :label="'Процессор (' + (m?.cores ?? 0) + ' ядер)'"
                  :bar-pct="m?.cpu ?? 0" :bar-cls="cpuBar()" />
        <StatCard ic="server" cls="c2"
                  :val="fmtSize(m?.ram.used) + ' / ' + fmtSize(m?.ram.total)"
                  label="Оперативная память" :bar-pct="m?.ram.percent ?? 0" :bar-cls="ramBar()" />
        <StatCard ic="archive" cls="c3" :val="(m?.disk.percent ?? 0) + '%'"
                  :label="'Диск занят (' + fmtSize(m?.disk.used) + ' из ' + fmtSize(m?.disk.total) + ')'"
                  :bar-pct="m?.disk.percent ?? 0" :bar-cls="diskBar()" />
        <StatCard ic="activity" cls="c4"
                  :val="(m?.net.in_mbit ?? 0) + ' / ' + (m?.net.out_mbit ?? 0) + ' Мбит/с'"
                  label="Сеть (вход / выход)" :bar-pct="null" />
      </div>

      <div class="split">
        <div>
          <div class="card">
            <div class="card-h"><span class="card-t">Нагрузка процессора</span>
              <span class="card-spacer"></span>
              <span class="pill info"><span class="dot pulse"></span>в реальном времени</span></div>
            <canvas ref="cpuCanvas" class="chart"></canvas>
            <div class="muted" style="font-size:12.5px;margin-top:8px">
              Аптайм: <b>{{ humanUptime(m?.uptime_sec ?? 0) }}</b> ·
              Load average: <b>{{ (m?.load || []).join(' / ') }}</b>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><span class="card-t">Нагрузка сайтов на систему</span></div>
            <div class="kv">
              <b>PHP-воркеры (все сайты)</b><span>{{ sitesLoad.php_workers }}</span>
              <b>CPU всех сайтов</b><span>{{ sitesLoad.cpu }}%</span>
              <b>Память всех сайтов</b><span>{{ fmtSize(sitesLoad.mem_mb * 1024 * 1024) }}</span>
            </div>
            <div class="row" style="margin-top:12px">
              <button class="btn primary" @click="goSitesWizard">
                <UiIcon name="plus" :size="15" />Создать сайт</button>
              <button class="btn" @click="goCreateBackup">
                <UiIcon name="archive" :size="15" />Создать бэкап</button>
              <button class="btn" @click="goPackages">
                <UiIcon name="pkg" :size="15" />Обновления</button>
            </div>
          </div>
        </div>
        <div>
          <div class="card">
            <div class="card-h"><span class="card-t">Сайты</span><span class="card-spacer"></span>
              <span class="pill gray">{{ d.sites_enabled }} из {{ d.sites_count }} активны</span></div>
            <div v-if="d.sites_maintenance" class="notice warn" style="margin-bottom:8px">
              {{ d.sites_maintenance }} сайт(ов) в режиме обслуживания</div>
            <div class="kv">
              <b>Базы данных</b><span>{{ d.dbs_count }}</span>
              <b>Резервные копии</b><span>{{ d.backups_count }}</span>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><span class="card-t">Службы</span><span class="card-spacer"></span>
              <button class="btn sm" @click="goServices">все →</button></div>
            <div v-if="!svcTop.length" class="empty">нет данных</div>
            <div v-for="s in svcTop" :key="s.name"
                 class="row" style="justify-content:space-between;padding:5px 0">
              <span class="mono">{{ s.name }}</span>
              <span class="pill" :class="svcPillCls(s)">{{ svcPillTxt(s) }}</span>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><span class="card-t">События</span><span class="card-spacer"></span>
              <button class="btn sm" @click="clearNotices">очистить</button></div>
            <div v-if="!notices.length" class="empty">событий нет</div>
            <div v-for="(n, i) in notices" :key="i"
                 style="padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">
              {{ n.text }}
              <div class="faint" style="font-size:11.5px">{{ fmtDate(n.ts) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
