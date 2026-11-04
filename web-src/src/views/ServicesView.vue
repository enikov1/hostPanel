<script setup lang="ts">
/* ============ Страница «Службы» (старый id 'services') ============ */
import { ref, computed, onMounted, nextTick } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { humanRel } from '../lib/format';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import type { SvcInfo } from './monitoring/types';

const services = ref<SvcInfo[]>([]);
const activeCount = computed(() =>
  services.value.filter((s) => s.state === 'active').length);

function pillCls(s: SvcInfo): string {
  return s.state === 'active' ? 'ok' : s.state === 'inactive' ? 'gray' : 'err';
}
function pillTxt(s: SvcInfo): string {
  return s.state === 'active' ? 'работает' : s.state === 'inactive' ? 'остановлена' : s.state;
}
function relTxt(s: SvcInfo): string {
  return s.uptime_sec ? humanRel(s.uptime_sec) : '—';
}

async function load(): Promise<void> {
  try {
    const d = await api('/api/services');
    services.value = d.services || [];
  } catch (e) {
    services.value = [];
    toastErr(e);
  }
}

/* ---- перезапуск службы ---- */
const restarting = ref<string>('');
async function svcRestart(name: string): Promise<void> {
  restarting.value = name;
  try {
    const r = await api('/api/services/restart', { method: 'POST', body: { name } });
    toast(r.message || 'готово');
    await load();
  } catch (e) { toastErr(e); }
  restarting.value = '';
}

/* ---- журнал службы ---- */
const logsDlg = ref(false);
const logsName = ref('');
const logText = ref('');
const logBox = ref<HTMLElement | null>(null);

async function svcLogs(name: string): Promise<void> {
  logsName.value = name;
  logText.value = 'Загрузка…';
  logsDlg.value = true;
  await nextTick();
  await svcLogsReload();
}

async function svcLogsReload(): Promise<void> {
  const name = logsName.value;
  if (!name) return;
  logText.value = 'Загрузка…';
  try {
    const r = await api('/api/services/logs?name=' + encodeURIComponent(name) + '&lines=300');
    logText.value = (r.lines || []).join('\n') || 'журнал пуст';
  } catch (e: any) {
    logText.value = 'ОШИБКА: ' + (e.message || String(e));
  }
  await nextTick();
  const el = logBox.value;
  if (el) el.scrollTop = el.scrollHeight;
}

onMounted(() => { void load(); });
</script>

<template>
  <div v-table>
    <div class="toolbar">
      <span class="muted" style="font-size:13px">
        Работают: <b>{{ activeCount }}</b> из {{ services.length }}</span>
    </div>
    <div class="card" style="padding:6px 10px">
      <div class="twrap"><table>
        <thead><tr>
          <th>Служба</th><th>Состояние</th><th>Работает уже</th>
          <th>Последний перезапуск</th><th></th>
        </tr></thead>
        <tbody>
          <tr v-for="s in services" :key="s.name">
            <td class="mono">{{ s.name }}</td>
            <td><span class="pill" :class="pillCls(s)">{{ pillTxt(s) }}</span></td>
            <td class="mono">{{ s.uptime_h || '—' }}</td>
            <td class="mono muted">
              <template v-if="s.since">{{ s.since }}
                <span class="faint">({{ relTxt(s) }} назад)</span></template>
              <template v-else>—</template>
            </td>
            <td>
              <div class="actions-cell">
                <button class="btn sm" @click="svcLogs(s.name)">
                  <UiIcon name="file" :size="14" /> Логи</button>
                <button class="btn sm" :disabled="restarting === s.name" @click="svcRestart(s.name)">
                  <UiIcon name="refresh" :size="14" /> Перезапустить</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table></div>
    </div>

    <AppModal :open="logsDlg" :title="'Журнал: ' + logsName" :wide="true"
              @close="logsDlg = false">
      <div ref="logBox" class="logbox"
           style="max-height:420px;overflow:auto;background:var(--hover)">{{ logText }}</div>
      <template #footer>
        <button class="btn primary" @click="svcLogsReload">Обновить</button>
        <button class="btn" @click="logsDlg = false">Закрыть</button>
      </template>
    </AppModal>
  </div>
</template>
