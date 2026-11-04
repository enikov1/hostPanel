<script setup lang="ts">
/* Брандмауэр: список правил, добавление порта, заблокированные IP (fail2ban). */
import { ref, onMounted } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import UiSelect from '../components/ui/UiSelect.vue';

interface FwRule {
  port: string;
  action: string;
  from: string;
  comment: string;
}

const active = ref(false);
const backend = ref('');
const rules = ref<FwRule[]>([]);
const banned = ref<string[]>([]);

const dlg = ref(false);
const port = ref('');
const act = ref('allow');
const comment = ref('');

function isAllow(a: unknown): boolean {
  return String(a).indexOf('allow') >= 0 || a === 'ALLOW';
}

async function load(): Promise<void> {
  try {
    const d = await api('/api/firewall');
    active.value = !!d.active;
    backend.value = d.backend || '';
    rules.value = d.rules || [];
    banned.value = d.banned || [];
  } catch (e) {
    toastErr(e);
  }
}

function addDlg(): void {
  port.value = '';
  act.value = 'allow';
  comment.value = '';
  dlg.value = true;
}

async function add(): Promise<void> {
  try {
    const r = await api('/api/firewall/add', { method: 'POST', body: {
      port: port.value.trim(), action: act.value,
      comment: comment.value.trim() } });
    toast(r.message);
    dlg.value = false;
    load();
  } catch (e) {
    toastErr(e);
  }
}

onMounted(load);
</script>

<template>
  <div v-table>
    <div class="toolbar">
      <span class="pill" :class="active ? 'ok' : 'warn'"><span class="dot"></span>{{ active ? 'активен' : 'неактивен' }}</span>
      <span class="muted">backend: {{ backend }}</span>
      <span class="spacer"></span>
      <button class="btn primary" @click="addDlg()"><UiIcon name="plus" :size="15" /> Правило</button>
    </div>
    <div class="card" style="padding:6px 10px">
      <div class="twrap">
        <table>
          <thead><tr><th>Порт</th><th>Действие</th><th>Источник</th><th>Комментарий</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in rules" :key="i">
              <td class="mono">{{ r.port }}</td>
              <td>
                <span class="pill" :class="isAllow(r.action) ? 'ok' : 'err'">{{ isAllow(r.action) ? 'разрешено' : 'запрещено' }}</span>
              </td>
              <td class="muted">{{ r.from }}</td>
              <td class="muted">{{ r.comment || '' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!rules.length" class="empty">правил нет</div>
      </div>
    </div>
    <div v-if="banned.length" class="card">
      <div class="card-h"><span class="card-t">Заблокированные IP (fail2ban)</span></div>
      <span v-for="ip in banned" :key="ip" class="pill err mono" style="margin:3px">{{ ip }}</span>
    </div>

    <AppModal :open="dlg" title="Новое правило" @close="dlg = false">
      <div class="row">
        <div class="field" style="flex:1">
          <label>Порт (например 8080 или 3000:3010)</label>
          <input v-model="port" type="text" placeholder="8080">
        </div>
        <div class="field" style="flex:1">
          <label>Действие</label>
          <UiSelect v-model="act"
                    :options="[{ value: 'allow', label: 'разрешить' },
                      { value: 'deny', label: 'запретить' }]" />
        </div>
      </div>
      <div class="field">
        <label>Комментарий (необязательно)</label>
        <input v-model="comment" type="text" maxlength="100"
               placeholder="например: панель управления">
        <div class="faint" style="font-size:11.5px;margin-top:4px">
          Правило открывает или закрывает порт для доступа из любой сети.
          Комментарий поможет потом вспомнить, зачем порт открыт.
        </div>
      </div>
      <template #footer>
        <button class="btn primary" @click="add()">Добавить</button>
        <button class="btn" @click="dlg = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
