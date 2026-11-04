<script setup lang="ts">
/* ============ Вкладка «Живучесть» карточки сайта ============ */
import { nextTick, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { drawUptime } from '../../lib/charts';
import { fmtDate } from '../../lib/format';
import StatCard from '../../components/StatCard.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const err = ref('');
const h = ref<any | null>(null);
const cv = ref<HTMLCanvasElement | null>(null);

function upCls(v: any): string {
  const x = v || 0;
  return x >= 99.5 ? 'ok' : x >= 97 ? 'warn' : 'err';
}

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  err.value = '';
  try {
    const d = await api('/api/site/' + s.id + '/health');
    h.value = d.report;
    await nextTick(() => drawUptime(cv.value, (h.value.series || [])));
  } catch (e: any) {
    err.value = e.message || String(e);
  }
  loading.value = false;
}

onMounted(load);
</script>

<template>
  <div>
    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="err" class="empty">{{ err }}</div>
    <template v-else-if="h">
      <div class="grid g4" style="margin-bottom:12px">
        <StatCard ic="activity" cls="c1" :val="h.uptime_24h != null ? h.uptime_24h + '%' : '—'"
                  label="Доступность 24 ч" :bar-pct="h.uptime_24h || 0" :bar-cls="upCls(h.uptime_24h)" />
        <StatCard ic="stat" cls="c2" :val="h.uptime_7d != null ? h.uptime_7d + '%' : '—'"
                  label="Доступность 7 дней" :bar-pct="h.uptime_7d || 0" :bar-cls="upCls(h.uptime_7d)" />
        <StatCard ic="clock" cls="c3" :val="(h.avg_ms || 0) + ' мс'" label="Средний ответ" />
        <StatCard ic="shield" cls="c4" :val="(h.incidents || []).length" label="Инцидентов" />
      </div>
      <canvas ref="cv" class="chart sm"></canvas>

      <div class="card" style="margin:12px 0 0">
        <div class="card-h"><span class="card-t">Инциденты</span></div>
        <div v-if="(h.incidents || []).length" class="twrap">
          <table>
            <thead><tr><th>Начало</th><th>Конец</th></tr></thead>
            <tbody>
              <tr v-for="(i, idx) in h.incidents" :key="idx">
                <td class="mono">{{ fmtDate(i.start) }}</td>
                <td class="mono">
                  <template v-if="i.end">{{ fmtDate(i.end) }}</template>
                  <span v-else class="pill err">продолжается</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">инцидентов не зафиксировано</div>
      </div>
    </template>
  </div>
</template>
