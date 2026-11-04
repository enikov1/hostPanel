<script setup lang="ts">
/* ============ Вкладка «Статистика» карточки сайта ============ */
import { nextTick, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { drawLine, cssVar } from '../../lib/charts';
import { fmtSize } from '../../lib/format';
import StatCard from '../../components/StatCard.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const err = ref('');
const st = ref<any | null>(null);
const cv = ref<HTMLCanvasElement | null>(null);

const errs404 = () => (st.value.codes.find((c: any[]) => c[0] === '404') || [0, 0])[1];
const errs500 = () => (st.value.codes.find((c: any[]) => c[0] === '500') || [0, 0])[1];

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  err.value = '';
  try {
    const d = await api('/api/site/' + s.id + '/stats');
    st.value = d.stats;
    await nextTick(draw);
  } catch (e: any) {
    err.value = e.message || String(e);
  }
  loading.value = false;
}

function draw(): void {
  if (!st.value || !cv.value) return;
  const labels = st.value.series.map((x: any) => x.day.slice(8) + '.' + x.day.slice(5, 7));
  drawLine(cv.value, [
    { data: st.value.series.map((x: any) => x.requests), color: cssVar('--primary'), fill: true },
    { data: st.value.series.map((x: any) => x.bytes / 1024 / 1024), color: cssVar('--info') },
  ], { labels: [labels[0], labels[labels.length - 1]] });
}

onMounted(load);
</script>

<template>
  <div>
    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="err" class="empty">нет данных: {{ err }}</div>
    <template v-else-if="st">
      <div class="grid g4" style="margin-bottom:12px">
        <StatCard ic="activity" cls="c1" :val="Number(st.requests).toLocaleString('ru-RU')" label="Запросов всего" />
        <StatCard ic="up" cls="c2" :val="fmtSize(st.bytes)" label="Трафик" />
        <StatCard ic="globe" cls="c3" :val="st.top_ips.length" label="Активных IP (топ-10)" />
        <StatCard ic="file" cls="c4" :val="errs404() + ' / ' + errs500()" label="Ошибок 404 / 500" />
      </div>
      <canvas ref="cv" class="chart"></canvas>
      <div class="split" style="margin-top:12px">
        <div>
          <b class="muted" style="font-size:12.5px">Популярные страницы</b>
          <template v-if="st.top_urls.length">
            <div v-for="(u, i) in st.top_urls" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono">{{ u[0] }}</span><span class="pill gray">{{ u[1] }}</span>
            </div>
          </template>
          <div v-else class="empty">нет данных</div>
        </div>
        <div>
          <b class="muted" style="font-size:12.5px">Активные IP</b>
          <template v-if="st.top_ips.length">
            <div v-for="(u, i) in st.top_ips" :key="i" class="row"
                 style="justify-content:space-between;font-size:12.5px;padding:3px 0">
              <span class="mono">{{ u[0] }}</span><span class="pill gray">{{ u[1] }}</span>
            </div>
          </template>
          <div v-else class="empty">нет данных</div>
        </div>
      </div>
    </template>
  </div>
</template>
