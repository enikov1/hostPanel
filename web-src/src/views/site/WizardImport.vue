<script setup lang="ts">
/* ============ Импорт сайта архивом ( importArchiveDlg + importArchiveGo ) ============ */
import { ref, watch } from 'vue';
import { apiForm } from '../../api/client';
import { toast } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import UiCheckbox from '../../components/ui/UiCheckbox.vue';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; imported: [] }>();

const dom = ref('');
const clean = ref(true);
const db = ref('');
const out = ref('');
const busy = ref(false);
const zipEl = ref<HTMLInputElement | null>(null);
const sqlEl = ref<HTMLInputElement | null>(null);

watch(() => props.open, (v) => {
  if (v) {
    dom.value = ''; clean.value = true; db.value = '';
    out.value = ''; busy.value = false;
    if (zipEl.value) zipEl.value.value = '';
    if (sqlEl.value) sqlEl.value.value = '';
  }
});

async function go(): Promise<void> {
  const zip = zipEl.value && zipEl.value.files ? zipEl.value.files[0] : null;
  if (!dom.value.trim()) { toast('Укажите домен', 'warn'); return; }
  if (!zip) { toast('Прикрепите zip-архив', 'warn'); return; }
  out.value = '';
  busy.value = true;
  const fd = new FormData();
  fd.append('domain', dom.value.trim());
  fd.append('clean', clean.value ? '1' : '0');
  fd.append('file', zip);
  const sql = sqlEl.value && sqlEl.value.files ? sqlEl.value.files[0] : null;
  if (sql) {
    fd.append('sql', sql);
    fd.append('db_name', db.value.trim());
    fd.append('engine', 'mysql');
  }
  try {
    const r = await apiForm('/api/sites/import', fd);
    out.value = 'ok:' + (r.message || 'импорт завершён');
    toast(r.message || 'Импорт завершён');
    emit('imported');
    setTimeout(() => { emit('close'); }, 1800);
  } catch (e: any) {
    out.value = 'err:' + (e.message || String(e));
  }
  busy.value = false;
}
</script>

<template>
  <AppModal :open="open" title="Импорт сайта архивом" wide @close="emit('close')">
    <div class="notice info">Переезд с другого хостинга: загрузите zip с файлами сайта
      и при необходимости дамп базы (.sql / .sql.gz / .zip). Файлы распакуются в папку сайта,
      дамп импортируется в указанную базу. Если сайта ещё нет — создадим автоматически.</div>
    <div class="field">
      <label>Домен сайта (существующий или новый)</label>
      <input v-model="dom" type="text" class="mono" placeholder="mysite.ru">
    </div>
    <UiCheckbox v-model="clean">
      Очистить папку сайта перед распаковкой (файлы будут заменены)</UiCheckbox>
    <div class="field">
      <label>Zip с файлами сайта (до 200 МБ)</label>
      <input ref="zipEl" type="file" accept=".zip">
    </div>
    <div class="field">
      <label>Дамп базы (необязательно)</label>
      <input ref="sqlEl" type="file" accept=".sql,.gz,.zip">
    </div>
    <div class="field">
      <label>База для дампа (имя; база должна существовать)</label>
      <input v-model="db" type="text" class="mono" placeholder="mysite_db">
    </div>
    <div v-if="out.startsWith('ok:')" class="notice ok">{{ out.slice(3) }}</div>
    <div v-else-if="out.startsWith('err:')" class="notice err">{{ out.slice(4) }}</div>
    <div v-else-if="busy" class="notice info">Импортирую — не закрывайте окно…</div>
    <template #footer>
      <button class="btn primary" :disabled="busy" @click="go()">
        <UiIcon name="up" :size="15" /> Импортировать</button>
      <button class="btn" :disabled="busy" @click="emit('close')">Отмена</button>
    </template>
  </AppModal>
</template>
