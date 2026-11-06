<script setup lang="ts">
/* ============ Вкладка «Движки» — каталог установки в один клик ============
   WordPress (полная автоустановка), Joomla, Drupal (распаковка + веб-мастер),
   DLE (свой дистрибутив), Omro (cld) — собственный движок панели. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import UiRadio from '../../components/ui/UiRadio.vue';
import BrandLogo from '../../components/BrandLogo.vue';
import AppModal from '../../components/AppModal.vue';
import { siteState, openSiteUrl } from './siteShared';

const loading = ref(true);
const installed = ref<Record<string, any>>({});
const running = ref(false);
const log = ref<string[]>([]);
const error = ref('');

/* установка конкретного движка */
const installEngine = ref('');
const dbMode = ref<'new' | 'existing'>('new');
const dbName = ref('');
const dbPassword = ref('');
const busy = ref(false);
const dleFile = ref<File | null>(null);
const distName = ref('');

let pollTimer: ReturnType<typeof setInterval> | null = null;

const siteId = computed(() => siteState.site?.id || 0);
const domain = computed(() => siteState.site?.domain || '');

const ENGINE_META: Record<string, { name: string; desc: string }> = {
  omro: { name: 'Omro (движок панели)',
          desc: 'Каталог контента: фильмы, сериалы, аниме, дорамы. Laravel 12 + админка на React.' },
  wordpress: { name: 'WordPress',
          desc: 'Самая популярная CMS: блоги, сайты, магазины (WooCommerce). Полная автоустановка — сайт и админка готовы сразу.' },
  joomla: { name: 'Joomla',
          desc: 'Универсальная CMS с гибкими правами пользователей. После распаковки — быстрый мастер установки в браузере.' },
  drupal: { name: 'Drupal',
          desc: 'Мощная CMS для сложных проектов. После распаковки — мастер установки в браузере.' },
  dle: { name: 'DataLife Engine (DLE)',
          desc: 'Движок новостных сайтов и каталогов. Загрузите свой ZIP-дистрибутив — панель распакует и подготовит конфиг БД.' },
};

function engineName(id: string): string {
  return ENGINE_META[id]?.name || id;
}
function engineDesc(id: string): string {
  return ENGINE_META[id]?.desc || '';
}
function engineLogo(id: string): string {
  const map: Record<string, string> = {
    omro: 'php', wordpress: 'wordpress', joomla: 'joomla',
    drupal: 'drupal', dle: 'archive',
  };
  return map[id] || 'pkg';
}

async function load(): Promise<void> {
  if (!siteId.value) return;
  try {
    const d = await api('/api/site/' + siteId.value + '/engine');
    installed.value = d.engines || {};
    running.value = !!d.running;
    log.value = d.log || [];
    error.value = d.error || '';
  } catch (e) { /* тихо */ }
  loading.value = false;
}

function startPolling(): void {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    load().then(() => {
      if (!running.value && pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    });
  }, 2500);
}

function openInstall(id: string): void {
  installEngine.value = id;
  dbMode.value = 'new';
  dbName.value = '';
  dbPassword.value = '';
  dleFile.value = null;
  distName.value = '';
  error.value = '';
  log.value = [];
}

function closeInstall(): void {
  installEngine.value = '';
}

function onDleFile(ev: Event): void {
  const f = (ev.target as HTMLInputElement).files?.[0];
  dleFile.value = f || null;
  distName.value = f ? f.name : '';
}

function toB64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const rd = new FileReader();
    rd.onload = () => {
      const s = String(rd.result);
      resolve(s.slice(s.indexOf(',') + 1));
    };
    rd.onerror = () => reject(new Error('не удалось прочитать файл'));
    rd.readAsDataURL(file);
  });
}

async function doInstall(): Promise<void> {
  const id = installEngine.value;
  if (!id || busy.value) return;
  busy.value = true;
  try {
    const body: Record<string, unknown> = {
      db_mode: dbMode.value, confirm_overwrite: true,
      confirm_reinstall: true,
    };
    if (dbMode.value === 'existing' && !dbName.value) {
      toast('Укажите имя базы данных', 'warn');
      busy.value = false;
      return;
    }
    if (dbName.value) body.db_name = dbName.value;
    if (dbMode.value === 'existing') body.db_password = dbPassword.value;
    if (id === 'dle') {
      if (!dleFile.value) {
        toast('Загрузите ZIP-дистрибутив DLE', 'warn');
        busy.value = false;
        return;
      }
      body.dist_b64 = await toB64(dleFile.value);
      body.dist_name = distName.value;
    }
    let r;
    if (id === 'omro') {
      // собственный движок панели — отдельный модуль (core/cld)
      r = await api('/api/site/' + siteId.value + '/cld/install', {
        method: 'POST', body: { db_mode: dbMode.value,
          confirm_overwrite: true } });
    } else {
      body.engine = id;
      r = await api('/api/site/' + siteId.value + '/engine/install', {
        method: 'POST', body });
    }
    toast(r.message);
    closeInstall();
    running.value = true;
    log.value = [];
    startPolling();
  } catch (e) { toastErr(e); }
  busy.value = false;
}

onMounted(load);
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer); });
</script>

<template>
  <div>
    <div v-if="loading" class="empty">Загрузка…</div>

    <!-- установка идёт -->
    <div v-else-if="running" class="card">
      <div class="card-h">
        <span class="card-t">Установка движка</span>
        <span class="pill warn" style="margin-left:auto">
          <span class="dot"></span>выполняется</span>
      </div>
      <div class="notice info" style="margin:0 0 8px">
        Это может занять несколько минут. Журнал обновляется автоматически —
        не закрывайте страницу.
      </div>
      <div class="logbox" style="max-height:360px">{{ log.join('\n') || '…' }}</div>
    </div>

    <!-- ошибка -->
    <div v-else-if="error" class="card">
      <div class="card-h"><span class="card-t">Ошибка установки</span></div>
      <div class="notice err">{{ error }}</div>
      <div v-if="log.length" class="logbox" style="max-height:240px;margin-top:8px">{{ log.join('\n') }}</div>
      <button class="btn" style="margin-top:10px" @click="load()">
        <UiIcon name="refresh" :size="14" /> Обновить</button>
    </div>

    <template v-else>
      <div class="notice info" style="margin-bottom:12px">
        Каталог движков: выбор — установка в один клик. Движок займёт
        корневую папку сайта; база данных создаётся автоматически или
        используется существующая. Установленные движки отмечены пилюлей.
      </div>

      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px">
        <div v-for="id in ['omro', 'wordpress', 'joomla', 'drupal', 'dle']"
             :key="id" class="card" style="margin:0">
          <div class="card-h">
            <BrandLogo :brand="id" :size="20" :fallback="engineLogo(id)" />
            <span class="card-t" style="margin-left:6px">{{ engineName(id) }}</span>
            <span v-if="installed[id]" class="pill ok" style="margin-left:auto">установлен</span>
          </div>
          <div class="faint" style="font-size:12px;line-height:1.55;padding:0 6px 10px">
            {{ engineDesc(id) }}
          </div>
          <div class="row" style="padding:0 6px 6px;flex-wrap:wrap;gap:6px">
            <button class="btn sm" :class="installed[id] ? '' : 'primary'"
                    @click="openInstall(id)">
              <UiIcon :name="installed[id] ? 'refresh' : 'down'" :size="13" />
              {{ installed[id] ? 'Переустановить' : 'Установить' }}</button>
            <button v-if="id === 'omro' && installed['omro']" class="btn sm"
                    @click="openSiteUrl(domain)">
              <UiIcon name="ext" :size="13" /> Открыть сайт</button>
          </div>
        </div>
      </div>
    </template>

    <!-- форма установки выбранного движка -->
    <AppModal :open="!!installEngine"
              :title="'Установка: ' + (installEngine ? engineName(installEngine) : '')"
              wide @close="closeInstall">
      <template v-if="installEngine">
        <div class="notice warn">
          Корневая папка сайта будет <b>очищена</b> и занята движком —
          существующие файлы будут удалены. Продолжайте, только если это
          новый сайт или вы сделали резервную копию.
        </div>

        <div class="g-title">База данных</div>
        <UiRadio v-model="dbMode" name="eng-db" value="new">
          Создать новую базу (рекомендуется) — панель создаст базу,
          пользователя и надёжный пароль</UiRadio>
        <UiRadio v-model="dbMode" name="eng-db" value="existing">
          Использовать существующую базу</UiRadio>

        <div v-if="dbMode === 'new'" class="field" style="margin-top:8px">
          <label>Имя новой базы (можно оставить как есть)</label>
          <input v-model="dbName" type="text" class="mono"
                 :placeholder="'eng_' + (domain.split('.')[0] || 'site')">
        </div>
        <template v-else>
          <div class="field">
            <label>Имя существующей базы</label>
            <input v-model="dbName" type="text" class="mono">
          </div>
          <div class="field">
            <label>Пароль пользователя базы</label>
            <input v-model="dbPassword" type="password"
                   autocomplete="new-password">
          </div>
        </template>

        <!-- специфичное для DLE -->
        <template v-if="installEngine === 'dle'">
          <div class="g-title">Дистрибутив DLE</div>
          <div class="faint" style="font-size:12px;margin-bottom:8px">
            Панель не поставляет дистрибутив DLE — загрузите ZIP-архив
            своей версии. Панель распакует его в корень сайта: далее мастер
            DLE доведёт установку (реквизиты БД — из этой вкладки).</div>
          <div class="field">
            <label>ZIP-дистрибутив (до 200 МБ)</label>
            <input ref="fileInput" type="file" accept=".zip"
                   @change="onDleFile">
          </div>
        </template>

        <!-- WordPress: доп. поля -->
        <template v-if="installEngine === 'wordpress'">
          <div class="g-title">Администратор WordPress</div>
          <div class="faint" style="font-size:12px">
            Логин: <span class="mono">admin</span>, надёжный пароль
            сгенерируется автоматически и будет показан после установки.
            E-mail: <span class="mono">admin@{{ domain }}</span> (можно
            сменить позже в админке WordPress).</div>
        </template>

        <div class="notice info" style="margin-top:10px">
          Всё применяется автоматически: панель очистит корневую папку,
          установит движок и перечитает nginx. Кнопка «Сохранить» в шапке
          к установке движков не относится.
        </div>
      </template>
      <template #footer>
        <button class="btn primary" :disabled="busy" @click="doInstall()">
          <UiIcon name="down" :size="15" />
          {{ busy ? 'Запускаю…' : 'Установить' }}</button>
        <button class="btn" @click="closeInstall()">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
