<script setup lang="ts">
/* ============ Мини-проводник по файлам сервера (выбор файла/папки) ============ */
import { ref, computed, watch } from 'vue';
import { api } from '../../api/client';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';

const props = defineProps<{
  open: boolean;
  /** путь, с которого начинается обзор */
  start: string;
}>();

const emit = defineEmits<{ close: []; pick: [path: string] }>();

interface FileItem { name: string; type: string }

const path = ref('/');
const filter = ref('');
const items = ref<FileItem[]>([]);
const curPath = ref('/');
const state = ref<'loading' | 'ok' | 'fail'>('loading');
const errMsg = ref('');

const crumbs = computed<[string, string][]>(() => {
  const parts: string[] = curPath.value.split('/').filter(Boolean);
  const res: [string, string][] = [];
  let acc = '';
  parts.forEach((p) => { acc += '/' + p; res.push([p, acc]); });
  return res;
});

const filtered = computed<FileItem[]>(() => {
  const f = filter.value.toLowerCase();
  return items.value.filter((x) => x.name.toLowerCase().includes(f));
});

function fullPath(it: FileItem): string {
  return (curPath.value === '/' ? '' : curPath.value) + '/' + it.name;
}

async function go(p: string): Promise<void> {
  state.value = 'loading';
  path.value = p;
  let d: any;
  try { d = await api('/api/files?path=' + encodeURIComponent(p)); }
  catch (e: any) {
    state.value = 'fail';
    errMsg.value = (e && e.message) || 'папка недоступна';
    return;
  }
  curPath.value = d.path;
  items.value = d.items || [];
  filter.value = '';
  state.value = 'ok';
}

watch(() => props.open, (o) => { if (o) { filter.value = ''; go(props.start || '/var/www'); } });
</script>

<template>
  <AppModal :open="open" title="Найти файл" wide @close="emit('close')">
    <div class="bread">
      <button @click="go('/')">корень</button>
      <template v-for="(c, i) in crumbs" :key="c[1]">
        <span class="sep">/</span><button @click="go(c[1])">{{ c[0] }}</button>
      </template>
    </div>
    <div class="row" style="margin:8px 0">
      <input v-model="filter" type="text" placeholder="фильтр: часть имени файла…" style="flex:1">
      <button class="btn" type="button" title="Вставить в команду путь к текущей папке"
              @click="emit('pick', path)">Выбрать папку</button>
    </div>
    <div style="max-height:44vh;overflow:auto">
      <div v-if="state === 'loading'" class="empty">Загрузка…</div>
      <div v-else-if="state === 'fail'" class="empty">{{ errMsg }}</div>
      <div v-else-if="filtered.length" class="twrap">
        <table><tbody>
          <tr v-for="(it, i) in filtered" :key="it.name">
            <template v-if="it.type === 'dir'">
              <td style="cursor:pointer" @click="go(fullPath(it))">
                <UiIcon name="folder" :size="15" /> <b>{{ it.name }}</b>
              </td>
              <td style="width:96px"></td>
            </template>
            <template v-else>
              <td><UiIcon name="file" :size="15" /> {{ it.name }}</td>
              <td style="width:96px">
                <button class="btn sm" @click="emit('pick', filtered[i] ? fullPath(filtered[i]) : '')">Выбрать</button>
              </td>
            </template>
          </tr>
        </tbody></table>
      </div>
      <div v-else class="empty">Папка пуста или фильтр ничего не нашёл</div>
    </div>
    <template #footer>
      <button class="btn" @click="emit('close')">Отмена</button>
    </template>
  </AppModal>
</template>
