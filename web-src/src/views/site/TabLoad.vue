<script setup lang="ts">
/* ============ Вкладка «Нагрузка» карточки сайта ============ */
import { onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { fmtSize } from '../../lib/format';
import StatCard from '../../components/StatCard.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const err = ref('');
const l = ref<any | null>(null);

const t = () => (l.value ? (l.value.total || { cpu: 0, mem_mb: 0, php_workers: 0 })
  : { cpu: 0, mem_mb: 0, php_workers: 0 });

function cpuCls(cpu: number): string {
  return cpu > 80 ? 'err' : cpu > 50 ? 'warn' : 'ok';
}

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  err.value = '';
  try {
    const d = await api('/api/site/' + s.id + '/load');
    l.value = d.load;
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
    <template v-else-if="l">
      <div class="grid g4" style="margin-bottom:12px">
        <StatCard ic="cpu" cls="c1" :val="t().cpu + '%'" label="CPU сайта (PHP + Node)"
                  :bar-pct="Math.min(100, t().cpu)" :bar-cls="cpuCls(t().cpu)" />
        <StatCard ic="server" cls="c2" :val="fmtSize(t().mem_mb * 1024 * 1024)" label="Память сайта" />
        <StatCard ic="gear" cls="c3" :val="t().php_workers" label="PHP-воркеров" />
        <StatCard ic="activity" cls="c4" :val="l.node ? 'работает' : '—'" label="Node.js" />
      </div>

      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Процессы PHP-FPM пула</span></div>
        <div v-if="l.php.length" class="twrap">
          <table>
            <thead><tr><th>PID</th><th>CPU %</th><th>Память</th><th>Время работы</th></tr></thead>
            <tbody>
              <tr v-for="p in l.php" :key="p.pid">
                <td class="mono">{{ p.pid }}</td>
                <td>{{ p.cpu }}</td>
                <td>{{ p.mem_mb }} МБ</td>
                <td class="mono">{{ p.time }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">воркеров нет (сайт без PHP или нет запросов)</div>
      </div>
    </template>
  </div>
</template>
