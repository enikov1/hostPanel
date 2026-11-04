<script setup lang="ts">
/* ============ Вкладка «Node.js» карточки сайта ============ */
import { ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import { siteState } from './siteShared';

/* действия над приложением: restart | npm */
async function nodeAct(action: string): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const call = action === 'npm' ? '/api/sites/npm' : '/api/sites/node';
  try {
    const r = await api(call, { method: 'POST', body: { id: s.id, action } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}

/* журнал приложения Node.js */
const logsOpen = ref(false);
const logsDomain = ref('');
const logsLines = ref<string[]>([]);

async function nodeLogsDlg(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  logsDomain.value = s.domain;
  logsLines.value = [];
  logsOpen.value = true;
  try {
    const d = await api('/api/site/' + s.id + '/node_logs');
    logsLines.value = d.lines || [];
  } catch (e) { logsOpen.value = false; toastErr(e); }
}
</script>

<template>
  <div v-if="siteState.site">
    <template v-if="siteState.site.node && siteState.f_node">
      <label class="check">
        <input v-model="siteState.f_node.enabled" type="checkbox">
        Приложение Node.js включено (systemd-юнит)</label>
      <div class="row">
        <div class="field" style="flex:1">
          <label>Версия</label>
          <select v-model="siteState.f_node.version">
            <option v-for="v in ['18', '20', '22']" :key="v" :value="v">{{ v }}</option>
          </select>
        </div>
        <div class="field" style="flex:1">
          <label>Порт</label>
          <input v-model.number="siteState.f_node.port" type="number">
        </div>
        <div class="field" style="flex:1">
          <label>Файл запуска</label>
          <input v-model="siteState.f_node.script" type="text">
        </div>
      </div>
      <div class="row">
        <button class="btn" @click="nodeAct('restart')">
          <UiIcon name="refresh" :size="15" /> Перезапустить</button>
        <button class="btn" @click="nodeAct('npm')">
          <UiIcon name="down" :size="15" /> npm install</button>
        <button class="btn" @click="nodeLogsDlg()">
          <UiIcon name="file" :size="15" /> Журнал приложения</button>
      </div>
    </template>
    <div v-else class="notice warn">Node.js недоступен для этого сайта</div>

    <AppModal :open="logsOpen" :title="'Журнал Node.js: ' + logsDomain" wide @close="logsOpen = false">
      <div class="logbox"><span class="mono" style="white-space:pre-wrap">{{ logsLines.join('\n') }}</span></div>
      <template #footer>
        <button class="btn" @click="logsOpen = false">Закрыть</button>
      </template>
    </AppModal>
  </div>
</template>
