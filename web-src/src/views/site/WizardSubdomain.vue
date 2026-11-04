<script setup lang="ts">
/* ============ Мастер поддомена ( wizardSubdomain + subCreate ) ============ */
import { ref, watch } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import { WEBSERVERS } from './siteShared';

const props = defineProps<{ open: boolean; parentId: number; parentDomain: string }>();
const emit = defineEmits<{ close: []; created: [] }>();

const phpVersions = ref<string[]>([]);
const name = ref('');
const ws = ref('nginx');
const php = ref('');
const sslKind = ref('none');
const busy = ref(false);

async function loadOptions(): Promise<void> {
  let v: string[] = [];
  try { v = Object.keys((await api('/api/php')).versions || {}).sort().reverse(); }
  catch (e) { v = []; }
  phpVersions.value = v;
  php.value = v[0] || '';
}

watch(() => props.open, (v) => {
  if (v) {
    name.value = ''; ws.value = 'nginx'; sslKind.value = 'none';
    void loadOptions();
  }
});

function fullDomain(): string {
  return (name.value.trim() || '…') + '.' + (props.parentDomain || '');
}

async function create(): Promise<void> {
  const sub = name.value.trim();
  if (!sub) { toast('Укажите имя поддомена', 'warn'); return; }
  busy.value = true;
  try {
    const d = await api('/api/sites');
    const parent = (d.sites || []).find((s: any) => s.id === props.parentId);
    const domain = sub + '.' + (parent ? parent.domain : props.parentDomain);
    const r = await api('/api/sites/create', { method: 'POST', body: {
      domain, parent: props.parentId, webserver: ws.value,
      php: php.value, ssl_kind: sslKind.value } });
    toast(r.message);
    emit('created');
    emit('close');
  } catch (e) { toastErr(e); }
  busy.value = false;
}
</script>

<template>
  <AppModal :open="open" :title="'Новый поддомен' + (parentDomain ? ' для ' + parentDomain : '')"
            @close="emit('close')">
    <div class="notice info">Полное имя поддомена: <b>{{ fullDomain() }}</b>.
      Папка создастся внутри сайта: subdomains/&lt;имя&gt;/public_html. SSL выпускается отдельно.</div>
    <div class="field">
      <label>Имя поддомена (без точки)</label>
      <input v-model="name" type="text" placeholder="например, blog или shop" @keyup.enter="create()">
    </div>
    <div class="field">
      <label>Веб-сервер</label>
      <select v-model="ws">
        <option v-for="w in WEBSERVERS" :key="w[0]" :value="w[0]">{{ w[1] }}</option>
      </select>
    </div>
    <div class="field">
      <label>Версия PHP</label>
      <select v-model="php">
        <option v-for="v in phpVersions" :key="v" :value="v">PHP {{ v }}</option>
      </select>
    </div>
    <div class="field">
      <label>SSL</label>
      <select v-model="sslKind">
        <option value="none">Без SSL</option>
        <option value="letsencrypt">Let's Encrypt</option>
        <option value="selfsigned">Самоподписанный</option>
      </select>
    </div>
    <template #footer>
      <button class="btn primary" :disabled="busy" @click="create()">
        <UiIcon name="check" :size="15" /> Создать поддомен</button>
      <button class="btn" @click="emit('close')">Отмена</button>
    </template>
  </AppModal>
</template>
