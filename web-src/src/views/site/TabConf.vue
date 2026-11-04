<script setup lang="ts">
/* ============ Вкладка «Конфиги» (nginx/apache/fpm/php.ini), только expert ============ */
import { onMounted, ref, watch } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import CodeEditor from '../../components/CodeEditor.vue';
import { siteState } from './siteShared';

type Kind = 'nginx' | 'apache' | 'fpm' | 'php';

const CONF_TABS: [Kind, string][] = [
  ['nginx', 'nginx.conf'], ['apache', 'apache.conf'],
  ['fpm', 'пул FPM'], ['php', 'php.ini сайта'],
];

function prismLangFromKind(kind: string): string {
  return kind === 'nginx' ? 'nginx'
    : kind === 'apache' ? 'apacheconf'
    : (kind === 'fpm' || kind === 'php') ? 'ini' : 'markup';
}

const kind = ref<Kind>('nginx');
const confPath = ref('');
const confText = ref('');
const loading = ref(false);
const loadErr = ref('');
/* «Сохранить» активен, только если редактор загрузился —
   иначе можно перезаписать конфиг старым содержимым */
const editorReady = ref(false);

async function loadConf(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  loadErr.value = '';
  editorReady.value = false;
  try {
    const d = await api('/api/site/' + s.id + '/conf?kind=' + kind.value);
    confPath.value = d.path || '';
    confText.value = d.content || '';
    editorReady.value = true;
  } catch (e: any) {
    confPath.value = '';
    confText.value = '';
    loadErr.value = e.message || String(e);
  }
  loading.value = false;
}

watch(kind, loadConf);
onMounted(loadConf);

async function saveConf(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  if (!editorReady.value) { toast('Редактор не загружен — сохранение отменено', 'warn'); return; }
  try {
    const r = await api('/api/site/' + s.id + '/conf', { method: 'POST',
      body: { kind: kind.value, content: confText.value } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}
</script>

<template>
  <div v-if="siteState.site">
    <div class="row" style="margin-bottom:10px">
      <button v-for="t in CONF_TABS.filter((t) => t[0] !== 'apache' || siteState.site!.webserver.includes('apache'))"
              :key="t[0]" class="btn sm" :class="{ primary: t[0] === kind }" @click="kind = t[0]">
        {{ t[1] }}</button>
    </div>
    <div class="notice info" style="margin-bottom:10px">Перед сохранением панель проверяет конфиг (nginx -t / apachectl configtest / правила php.ini). При ошибке файл откатывается.</div>

    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="loadErr" class="notice err">{{ loadErr }}</div>
    <template v-else>
      <div class="faint mono" style="font-size:11.5px;margin-bottom:6px">{{ confPath }}</div>
      <CodeEditor v-model="confText" :lang="prismLangFromKind(kind)" />
    </template>

    <div class="row" style="margin-top:10px">
      <button class="btn primary" @click="saveConf()">
        <UiIcon name="check" :size="14" /> Сохранить и применить</button>
    </div>
  </div>
</template>
