<script setup lang="ts">
/* ============ Карточка сайта: отдельная страница /sites/:id ============
   В старой версии карточка была модалкой siteDlg(site_id) — теперь реальный
   URL; вкладки — локальное состояние (дублируется query ?tab=). */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { me } from '../stores';
import UiIcon from '../components/UiIcon.vue';
import TabOverview from './site/TabOverview.vue';
import TabPhp from './site/TabPhp.vue';
import TabNode from './site/TabNode.vue';
import TabSsl from './site/TabSsl.vue';
import TabSecurity from './site/TabSecurity.vue';
import TabConf from './site/TabConf.vue';
import TabStats from './site/TabStats.vue';
import TabLoad from './site/TabLoad.vue';
import TabHealth from './site/TabHealth.vue';
import TabLogs from './site/TabLogs.vue';
import { fillSiteState, buildSaveBody, siteState, type Site } from './site/siteShared';

const route = useRoute();
const router = useRouter();

const loaded = ref(false);
const loadErr = ref('');

const TABS: { id: string; t: string; expert?: boolean }[] = [
  { id: 'main', t: 'Основное' },
  { id: 'php', t: 'PHP и FPM' },
  { id: 'node', t: 'Node.js' },
  { id: 'ssl', t: 'SSL' },
  { id: 'sec', t: 'Фильтры' },
  { id: 'conf', t: 'Конфиги', expert: true },
  { id: 'stats', t: 'Статистика' },
  { id: 'load', t: 'Нагрузка' },
  { id: 'health', t: 'Живучесть' },
  { id: 'logs', t: 'Логи' },
];

const visibleTabs = computed(() => TABS.filter((t) => !t.expert || me.expert));

const activeTab = ref('main');

function setTab(t: string): void {
  activeTab.value = t;
  void router.replace({ query: { ...route.query, tab: t } });
}

const siteId = computed(() => Number(route.params.id));

async function load(): Promise<void> {
  loaded.value = false;
  loadErr.value = '';
  let d: any, phpData: any;
  try {
    d = await api('/api/sites');
    phpData = await api('/api/php');
  } catch (e) {
    loadErr.value = (e as Error).message || String(e);
    toastErr(e);
    return;
  }
  const found = (d.sites || []).find((s: Site) => s.id === siteId.value);
  if (!found) {
    toast('Сайт не найден — обновите список сайтов', 'warn');
    void router.replace('/sites');
    return;
  }
  fillSiteState(found, phpData);
  loaded.value = true;
}

/* сохранение: собирает поля всех вкладок, как прежний siteSave */
const saving = ref(false);

async function siteSave(): Promise<void> {
  saving.value = true;
  try {
    const r = await api('/api/sites/update', { method: 'POST', body: buildSaveBody() });
    toast(r.message);
    await load();
  } catch (e) { toastErr(e); }
  saving.value = false;
}

onMounted(() => {
  const q = route.query.tab;
  if (typeof q === 'string' && visibleTabs.value.some((t) => t.id === q)) activeTab.value = q;
  load();
});

/* переход между карточками сайтов (/sites/1 → /sites/2) */
watch(() => route.params.id, (v, old) => {
  if (v && v !== old && route.name === 'site') {
    const q = route.query.tab;
    if (typeof q === 'string' && visibleTabs.value.some((t) => t.id === q)) activeTab.value = q;
    load();
  }
});
</script>

<template>
  <div v-table>
    <div v-if="loadErr" class="notice err">{{ loadErr }}</div>
    <div v-else-if="!loaded" class="empty">Загрузка…</div>

    <template v-else-if="siteState.site">
      <!-- хлебные крошки + заголовок -->
      <div class="bread" style="margin-bottom:6px">
        <router-link to="/sites" class="btn sm">← Сайты</router-link>
        <span class="sep">›</span>
        <span class="cur">{{ siteState.site.domain }}</span>
        <span v-if="!siteState.site.enabled" class="pill warn">отключён</span>
        <span v-if="siteState.site.maintenance" class="pill warn">обслуживание</span>
        <span class="spacer"></span>
        <button class="btn" @click="router.push('/sites')">Закрыть</button>
        <button class="btn primary" :disabled="saving" @click="siteSave()">
          <UiIcon name="check" :size="15" /> Сохранить</button>
      </div>

      <!-- вкладки -->
      <div class="tabs" style="margin-bottom:12px">
        <button v-for="t in visibleTabs" :key="t.id" class="tab"
                :class="{ active: activeTab === t.id }" @click="setTab(t.id)">{{ t.t }}</button>
      </div>

      <TabOverview v-if="activeTab === 'main'" />
      <TabPhp v-else-if="activeTab === 'php'" />
      <TabNode v-else-if="activeTab === 'node'" />
      <TabSsl v-else-if="activeTab === 'ssl'" />
      <TabSecurity v-else-if="activeTab === 'sec'" />
      <TabConf v-else-if="activeTab === 'conf' && me.expert" />
      <TabStats v-else-if="activeTab === 'stats'" />
      <TabLoad v-else-if="activeTab === 'load'" />
      <TabHealth v-else-if="activeTab === 'health'" />
      <TabLogs v-else-if="activeTab === 'logs'" />
    </template>
  </div>
</template>
