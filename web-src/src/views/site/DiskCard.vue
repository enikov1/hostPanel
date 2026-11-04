<script setup lang="ts">
/* ============ Карточка «Место по сайтам»: бары + график роста ============ */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { drawLine, cssVar } from '../../lib/charts';
import { fmtSize } from '../../lib/format';
import type { Site } from './siteShared';

const props = defineProps<{ sites: Site[] }>();

interface DiskRow { domain: string; disk: number; grow: number }

const cv = ref<HTMLCanvasElement | null>(null);
const hasChart = ref(true);

const rows = computed<DiskRow[]>(() => {
  return props.sites.filter((s) => !s.parent)
    .map((s) => ({
      domain: s.domain,
      disk: s.disk || 0,
      grow: (s.disk_hist || []).length >= 2
        ? (s.disk || 0) - (s.disk_hist as { t: string; mb: number }[])[0].mb * 1024 * 1024
        : 0,
    }))
    .sort((a, b) => b.disk - a.disk).slice(0, 8);
});

const total = computed(() => rows.value.reduce((a, x) => a + x.disk, 0));
const maxDisk = computed(() => Math.max(...rows.value.map((x) => x.disk), 1));

function pct(x: DiskRow): number {
  return Math.max(2, Math.round(x.disk / maxDisk.value * 100));
}

function growPill(x: DiskRow): string {
  if (x.grow > 1024 * 1024) return '+' + fmtSize(x.grow);
  if (x.grow < -1024 * 1024) return fmtSize(x.grow);
  return '';
}
function growCls(x: DiskRow): string {
  return x.grow > 1024 * 1024 ? 'pill warn' : x.grow < -1024 * 1024 ? 'pill ok' : '';
}

function draw(): void {
  const canvas = cv.value;
  if (!canvas) return;
  const byDate: Record<string, number> = {};
  props.sites.filter((s) => !s.parent).forEach((s) =>
    (s.disk_hist || []).forEach((p) => {
      const day = (p.t || '').slice(0, 10);
      // точка раз в 6 часов — берём ПОСЛЕДНЮЮ точку дня, а не сумму
      if (day) byDate[day] = (p.mb || 0);
    }));
  const days = Object.keys(byDate).sort();
  if (days.length < 2) { hasChart.value = false; return; }
  hasChart.value = true;
  const data = days.map((d) => byDate[d]);
  drawLine(canvas, [{ data, color: cssVar('--primary'), fill: true }],
    { labels: [days[0], days[days.length - 1]], max: Math.max(...data, 1) * 1.2 });
}

watch(() => props.sites, () => { void nextTick(draw); }, { deep: false });
onMounted(() => { void nextTick(draw); });
onBeforeUnmount(() => { /* canvas уходит вместе с компонентом */ });
</script>

<template>
  <div v-if="rows.length" class="card" style="margin-bottom:12px">
    <div class="card-h">
      <span class="card-t">Место по сайтам</span><span class="card-spacer"></span>
      <span class="pill gray">всего {{ fmtSize(total) }}</span>
    </div>
    <div style="padding:6px 8px 2px">
      <div v-for="x in rows" :key="x.domain" class="row"
           style="align-items:center;gap:10px;padding:3px 0">
        <span style="width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
              :title="x.domain">{{ x.domain }}</span>
        <div style="flex:1;height:14px;border-radius:7px;background:var(--border);overflow:hidden">
          <div :style="{ width: pct(x) + '%', height: '100%', borderRadius: '7px', background: 'var(--primary)' }"></div>
        </div>
        <b style="width:70px;text-align:right">{{ fmtSize(x.disk) }}</b>
        <span v-if="growPill(x)" :class="growCls(x)" style="font-size:11px">{{ growPill(x) }}</span>
      </div>
    </div>
    <canvas v-show="hasChart" ref="cv" class="chart" style="height:120px;margin-top:6px"></canvas>
    <div class="faint" style="font-size:11.5px;padding:0 8px 8px">Полоски — текущий размер папки каждого сайта,
      график — суммарный рост места (точка раз в 6 часов). Жёлтый значок — прирост с первой точки истории.</div>
  </div>
</template>
