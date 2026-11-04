<script setup lang="ts">
/* Оболочка панели: сайдбар с группами, топбар с глобальным поиском,
   колокольчиком уведомлений, темой и выходом. */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NAV, navVisible } from '../router';
import { me } from '../stores';
import { api } from '../api/client';
import { toggleTheme, currentTheme } from '../lib/theme';
import UiIcon from '../components/UiIcon.vue';

const emit = defineEmits<{ logout: [] }>();

const route = useRoute();
const router = useRouter();
const theme = ref(currentTheme());
const navOpen = ref(false);
const sidebar = ref<HTMLElement | null>(null);

/** Доступная новая версия панели (проверяется один раз при входе). */
const newVersion = ref('');
async function checkUpdate(): Promise<void> {
  try {
    const d = await api('/api/panel/update');
    if (d && d.update_available) newVersion.value = d.latest;
  } catch (e) { /* демо без сети и прочие ошибки — тихо */ }
}

const cur = computed(() => {
  const n = NAV.find((x) => x.path === route.path);
  return { t: n ? n.t : (route.meta.t || 'Обзор'), d: n ? n.d : (route.meta.d || '') };
});

/** Видимые пункты с флагом «первый в своей группе» — для заголовков. */
const navItems = computed(() => {
  const vis = navVisible();
  return vis.map((n, i) => ({
    ...n,
    firstInGroup: i === 0 || vis[i - 1].g !== n.g,
  }));
});

watch(() => route.path, () => { navOpen.value = false; });

/* ---- колокольчик ---- */
const unread = ref(0);
const bellOpen = ref(false);
const bellList = ref<any[]>([]);

async function refreshBell(): Promise<void> {
  try {
    const d = await api('/api/notifications');
    const list = d.notifications || [];
    bellList.value = list;
    const last = +(localStorage.getItem('hp_last_read') || 0);
    unread.value = list.filter((n: any) => {
      const t = new Date((n.ts || '').replace(' ', 'T')).getTime() || 0;
      return t > last;
    }).length;
  } catch (e) { /* сессия могла истечь */ }
}

const bellBtn = ref<HTMLElement | null>(null);
const bellStyle = ref<Record<string, string>>({});

async function openBell(): Promise<void> {
  if (bellOpen.value) { bellOpen.value = false; return; }
  await refreshBell();
  bellOpen.value = true;
  try { localStorage.setItem('hp_last_read', String(Date.now())); } catch (e) { /* noop */ }
  unread.value = 0;
  // позиционируем панель от кнопки (fixed без координат уезжал за экран)
  const el = bellBtn.value;
  if (el) {
    const r = el.getBoundingClientRect();
    bellStyle.value = {
      position: 'fixed',
      top: Math.min(r.bottom + 8, window.innerHeight - 200) + 'px',
      right: (window.innerWidth - r.right) + 'px',
    };
  }
}

async function bellClear(): Promise<void> {
  try { await api('/api/notifications/read', { method: 'POST', body: {} }); } catch (e) { /* noop */ }
  bellOpen.value = false;
  refreshBell();
}

/* ---- глобальный поиск ---- */
const q = ref('');
const gsItems = ref<any[]>([]);
const gsOpen = ref(false);
let gsTimer: ReturnType<typeof setTimeout> | null = null;
let searchGen = 0; // устаревший ответ не должен перетирать свежий

/** Debounce 300 мс: запрос уходит не на каждый символ. */
function searchGo(): void {
  if (gsTimer) clearTimeout(gsTimer);
  gsTimer = setTimeout(() => { gsTimer = null; searchGoNow(); }, 300);
}

async function searchGoNow(): Promise<void> {
  const gen = ++searchGen;
  const query = q.value.trim();
  if (query.length < 2) { gsOpen.value = false; return; }
  try {
    const d = await api('/api/search?q=' + encodeURIComponent(query));
    if (gen !== searchGen) return; // пока ждали — запрос уже изменился
    gsItems.value = d.results || [];
    gsOpen.value = gsItems.value.length > 0;
  } catch (e) { if (gen === searchGen) gsOpen.value = false; }
}

function gsPick(r: any): void {
  q.value = '';
  gsOpen.value = false;
  if (r.type === 'site') router.push('/sites/' + r.site_id);
  else router.push(r.path || ('/' + r.page).replace('//', '/'));
}

function gsHide(): void { setTimeout(() => { gsOpen.value = false; }, 150); }

function onTheme(): void { theme.value = toggleTheme(); }

function clickOutside(e: MouseEvent): void {
  const t = e.target as HTMLElement;
  if (!t.closest('.bell-wrap')) bellOpen.value = false;
  if (!t.closest('.gs-wrap')) gsOpen.value = false;
}

const bellTimer = ref<ReturnType<typeof setInterval> | null>(null);

onMounted(() => {
  refreshBell();
  bellTimer.value = setInterval(refreshBell, 60000);
  checkUpdate();
  document.addEventListener('click', clickOutside);
});
onBeforeUnmount(() => {
  document.removeEventListener('click', clickOutside);
  if (bellTimer.value) clearInterval(bellTimer.value);
  if (gsTimer) { clearTimeout(gsTimer); gsTimer = null; }
});
</script>

<template>
  <!-- id="app": каркас из app.css (display:flex) — как в исходной вёрстке -->
  <div id="app">
    <aside id="sidebar" ref="sidebar" :class="{ open: navOpen }">
      <div class="sb-head">
        <span class="logo-ico sm"><UiIcon name="zap" :size="18" /></span>
        <div><div class="sb-name">HostPanel</div></div>
        <span class="sb-ver">{{ 'v' + me.version }}</span>
      </div>
      <nav class="sb-nav" id="nav">
        <template v-for="n in navItems" :key="n.path">
          <div v-if="n.firstInGroup" class="sb-group">{{ n.g }}</div>
          <router-link class="sb-item" :to="n.path"
                       :class="{ active: route.path === n.path }" :title="n.d || n.t">
            <UiIcon :name="n.ic" :size="16" /><span>{{ n.t }}</span>
          </router-link>
        </template>
      </nav>
      <div class="sb-foot">
        Сервер работает<br>Версия панели: {{ me.version }}
        <router-link v-if="newVersion" to="/settings" class="sb-upd"
                     title="Доступна новая версия панели — откроются Настройки">
          ⬆ доступна v{{ newVersion }}
        </router-link>
      </div>
    </aside>
    <div id="nav-back" :class="{ on: navOpen }" @click="navOpen = false"></div>
    <div id="main">
      <header id="topbar">
        <button class="btn icon" title="Меню" @click="navOpen = !navOpen">
          <UiIcon name="menu" :size="17" />
        </button>
        <div>
          <div id="tb-title">{{ cur.t }}</div>
          <div id="tb-sub">{{ cur.d }}</div>
        </div>
        <div class="tb-spacer"></div>
        <div class="gs-wrap">
          <input v-model="q" type="text" placeholder="Поиск: сайт, база, раздел…"
                 autocomplete="off" @input="searchGo" @focus="searchGo"
                 @keydown.escape="q = ''; gsOpen = false" @blur="gsHide">
          <div v-if="gsOpen" class="gs-drop">
            <div v-for="(r, i) in gsItems" :key="i" class="gs-item"
                 @mousedown.prevent="gsPick(r)">
              <span class="pill gray">{{ r.hint }}</span> {{ r.title }}
            </div>
          </div>
        </div>
        <button class="btn icon" title="Тема" @click="onTheme">
          <UiIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="17" />
        </button>
        <div class="bell-wrap" style="position:relative">
          <button ref="bellBtn" class="btn icon" title="Уведомления" @click="openBell">
            <UiIcon name="bell" :size="17" />
          </button>
          <span v-if="unread" class="bell-badge">{{ unread > 9 ? '9+' : unread }}</span>
          <div v-if="bellOpen" class="bell-drop" :style="bellStyle">
            <div class="bd-h"><b>Уведомления</b>
              <span style="flex:1"></span>
              <button class="btn sm" @click="bellClear">Очистить</button>
            </div>
            <template v-if="bellList.length">
              <div v-for="(n, i) in bellList.slice(0, 12)" :key="i"
                   class="bell-item" :class="n.level || 'info'">
                <span class="faint" style="width:86px;flex-shrink:0">{{ (n.ts || '').slice(5, 16) }}</span>
                <span>{{ n.text }}</span>
              </div>
            </template>
            <div v-else class="empty" style="padding:14px">уведомлений нет</div>
          </div>
        </div>
        <button class="btn" title="Выход" @click="emit('logout')">Выход</button>
      </header>
      <main id="content" class="page">
        <slot />
      </main>
    </div>
  </div>
</template>

<style>
/* каркас #app/styles приходит из app.css; здесь только добавки к нему */
#nav-back { display: none; }
@media (max-width: 900px) {
  #nav-back.on { display: block; }
}
.bell-badge {
  position: absolute; top: -4px; right: -4px;
  background: var(--err, #d64545); color: #fff; font-size: 10px;
  border-radius: 9px; padding: 1px 5px; font-weight: 600;
}
.gs-wrap { position: relative; }
.gs-drop {
  position: absolute; top: calc(100% + 6px); left: 0; z-index: 60;
  background: var(--card, #fff); border: 1px solid var(--border);
  border-radius: 10px; box-shadow: var(--shadow);
  min-width: 300px; max-height: 320px; overflow: auto;
}
.gs-item { padding: 9px 12px; cursor: pointer; font-size: 13.5px; }
.gs-item:hover { background: var(--hover, rgba(0,0,0,.04)); }
.bell-drop {
  position: fixed; top: 70px; right: 16px; z-index: 60;
  background: var(--card, #fff); border: 1px solid var(--border);
  border-radius: 10px; box-shadow: var(--shadow);
  width: 340px; max-height: 380px; overflow: auto;
}
</style>
