<script setup lang="ts">
/* ============ Страница: Установка ПО, ionCube, приложения (phpMyAdmin) ============ */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { genPassword } from '../lib/pw';
import { copyText } from '../lib/clipboard';
import UiIcon from '../components/UiIcon.vue';
import BrandLogo from '../components/BrandLogo.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';
import UiSelect from '../components/ui/UiSelect.vue';
import UiCheckbox from '../components/ui/UiCheckbox.vue';
import { SWSET_IDS } from './swset/swsetShared';
import { pmaApps } from './software/pmaStore';

const SW_ICONS: Record<string, string> = {
  nginx: 'globe', apache: 'server', php74: 'file', php80: 'file',
  php81: 'file', php82: 'file', php83: 'file', php84: 'file', php85: 'file',
  composer: 'pkg', mariadb: 'db', postgresql: 'db', redis: 'zap', memcached: 'zap',
  postfix: 'ext', dovecot: 'archive', mailutils: 'file',
  certbot: 'shield', fail2ban: 'shield', nodejs: 'file', git: 'folder', unzip: 'folder',
};

const router = useRouter();

const loaded = ref(false);
const catalog = ref<any[]>([]);
const groups = computed<Record<string, any[]>>(() => {
  const g: Record<string, any[]> = {};
  (catalog.value || []).forEach((s: any) => {
    (g[s.group] = g[s.group] || []).push(s);
  });
  return g;
});

/* ---------- фоновая задача установки/удаления ---------- */
const taskRunning = ref<any | null>(null);
const taskHistory = ref<any | null>(null);
let wasRunning = false;
let pollTimer: ReturnType<typeof setTimeout> | null = null;

function schedulePoll(): void {
  if (pollTimer) clearTimeout(pollTimer);
  pollTimer = setTimeout(pollSw, 2000);
}

async function pollSw(): Promise<void> {
  try {
    const d = await api('/api/packages/task');
    if (d.running) {
      wasRunning = true;
      taskRunning.value = d;
      schedulePoll();
    } else {
      taskRunning.value = null;
      if (wasRunning) {
        wasRunning = false;
        taskHistory.value = d;
        // в старом коде здесь go('software') — перерисовка всей страницы
        loadSoftware();
        loadIoncube();
        appsLoad();
      }
    }
  } catch (e) { /* тихо */ }
}

function swName(id: string): string {
  const map: Record<string, string> = {
    nginx: 'nginx', apache: 'Apache 2.4', php74: 'PHP 7.4', php80: 'PHP 8.0',
    php81: 'PHP 8.1', php82: 'PHP 8.2', php83: 'PHP 8.3', php84: 'PHP 8.4',
    php85: 'PHP 8.5', composer: 'Composer', mariadb: 'MariaDB', postgresql: 'PostgreSQL',
    redis: 'Redis', memcached: 'Memcached', certbot: 'Certbot', fail2ban: 'Fail2ban',
    postfix: 'Postfix', dovecot: 'Dovecot', mailutils: 'Mailutils',
    nodejs: 'Node.js + npm', git: 'Git', unzip: 'Архиваторы',
  };
  return map[id] || id;
}

function swInstall(id: string): void {
  confirmDlg('Установить службу',
    'Установить ' + swName(id) + ' через apt? Операция выполнится в фоне.',
    async () => {
      try {
        const r = await api('/api/software/install', { method: 'POST', body: { name: id } });
        toast(r.message);
        wasRunning = true;
        pollSw();
      } catch (e) { toastErr(e); }
    });
}

function swRemove(id: string): void {
  confirmDlg('Удалить службу',
    'Удалить ' + swName(id) + ' с сервера? Сайты, использующие её, перестанут работать.',
    async () => {
      try {
        const r = await api('/api/software/remove', { method: 'POST', body: { name: id } });
        toast(r.message);
        wasRunning = true;
        pollSw();
        loadSoftware();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- данные страницы ---------- */
async function loadSoftware(): Promise<void> {
  try {
    const d = await api('/api/software');
    catalog.value = d.catalog || [];
    loaded.value = true;
  } catch (e) {
    if (!loaded.value) toastErr(e);
  }
}

/* ---------- ionCube Loader ---------- */
const ioncube = ref<any | null>(null);

async function loadIoncube(): Promise<void> {
  try {
    ioncube.value = await api('/api/ioncube/status');
  } catch (e) { ioncube.value = null; }
}

function ioncubeGo(action: string, version: string): void {
  const what = action === 'remove' ? 'Удалить' : 'Установить/обновить';
  confirmDlg('ionCube Loader', what + ' ionCube для PHP ' + version + '? ' +
    (action === 'remove'
      ? 'Скрипты, требующие ionCube, перестанут работать.'
      : 'php-fpm будет перезапущен.'),
    async () => {
      try {
        const r = await api('/api/ioncube/' + action, { method: 'POST', body: { version } });
        toast(r.message);
        wasRunning = true;
        pollSw();
      } catch (e) { toastErr(e); }
    }, action === 'remove');
}

/* ---------- приложения: phpMyAdmin в 1 клик ---------- */
const appsErr = ref('');

async function appsLoad(): Promise<void> {
  appsErr.value = '';
  try {
    const d = await api('/api/apps');
    pmaApps.value = d.apps || [];
  } catch (e: any) {
    pmaApps.value = [];
    appsErr.value = (e && e.message) || 'Ошибка загрузки';
  }
}

const pmaInstalled = () => pmaApps.value.filter((a: any) => a.installed);

/* --- установка phpMyAdmin --- */
const pmaDlgOpen = ref(false);
const pmaSites = ref<any[]>([]);
const pmaSite = ref('');
const pmaProtect = ref(true);
const pmaPass = ref('');

async function pmaDlg(): Promise<void> {
  let d: any;
  try { d = await api('/api/sites'); } catch (e) { toastErr(e); return; }
  const sites = (d.sites || []).filter((x: any) => x.php);
  if (!sites.length) { toast('Сначала создайте сайт с PHP', 'warn'); return; }
  pmaSites.value = sites;
  pmaSite.value = sites[0].domain;
  pmaProtect.value = true;
  pmaPass.value = genPassword();
  pmaDlgOpen.value = true;
}

async function pmaInstall(): Promise<void> {
  try {
    const r = await api('/api/apps/install', { method: 'POST', body: {
      app: 'pma', site: pmaSite.value, protect: pmaProtect.value, password: pmaPass.value } });
    pmaDlgOpen.value = false;
    toast(r.message);
    pollSw();
  } catch (e) { toastErr(e); }
}

/* --- доступы phpMyAdmin --- */
const pmaAccessOpen = ref(false);
const pmaAccessRow = ref<any | null>(null);
const pmaAccessDomain = ref('');

function pmaAccessDlg(domain: string): void {
  const row = pmaApps.value.find((a: any) => a.domain === domain);
  if (!row) return;
  pmaAccessDomain.value = domain;
  pmaAccessRow.value = row;
  pmaAccessOpen.value = true;
}

/* --- удаление phpMyAdmin --- */
function pmaRemoveDlg(domain: string): void {
  confirmDlg('Удалить phpMyAdmin',
    'Папка /pma сайта ' + domain + ' будет удалена вместе с настройками. Удалить?',
    async () => {
      try {
        const r = await api('/api/apps/remove', { method: 'POST',
          body: { app: 'pma', site: domain } });
        toast(r.message);
        pollSw();
      } catch (e) { toastErr(e); }
    });
}

function swsetGo(id: string): void {
  router.push({ path: '/software/settings', query: { open: id } });
}

onMounted(() => {
  loadSoftware();
  pollSw();
  loadIoncube();
  appsLoad();
});

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer);
});
</script>

<template>
  <div>
    <div class="toolbar">
      <span class="muted" style="font-size:13px">Установка и удаление служб сервера.
        Операции идут в фоне — прогресс виден под списком.</span>
    </div>

    <!-- фоновая задача: прогресс / история последних операций -->
    <div v-if="taskRunning" class="notice info">
      <b>Выполняется:</b> {{ taskRunning.kind }} <span class="dot pulse"></span>
      <div class="logbox" style="margin-top:8px;max-height:180px">{{ (taskRunning.log || []).join('\n') }}</div>
    </div>
    <div v-else-if="taskHistory && (taskHistory.history || []).length" class="card" style="margin-top:12px">
      <div class="card-h">
        <span class="card-t">Последние операции</span><span class="card-spacer"></span>
        <span class="pill gray">{{ (taskHistory.history || []).length }}</span>
      </div>
      <div v-for="(x, i) in (taskHistory.history || []).slice(0, 12)" :key="i"
           class="row" style="align-items:center;gap:8px;padding:3px 0">
        <span class="pill" :class="x.ok ? 'ok' : 'err'">{{ x.ok ? 'ок' : 'ошибка' }}</span>
        <span class="faint" style="width:110px">{{ (x.finished || '').slice(0, 16) }}</span>
        <span style="flex:1">{{ x.kind }}{{ x.error ? ' — ' + x.error : '' }}</span>
      </div>
    </div>

    <!-- приложения: phpMyAdmin -->
    <div class="card">
      <div class="card-h">
        <span class="card-t">Приложения</span><span class="card-spacer"></span>
        <button class="btn sm primary" @click="pmaDlg()">
          <UiIcon name="down" :size="14" /> Установить phpMyAdmin</button>
      </div>
      <template v-if="pmaInstalled().length">
        <div v-for="a in pmaInstalled()" :key="a.domain" class="row"
             style="align-items:center;padding:10px 6px;flex-wrap:wrap;border-top:1px solid var(--border)">
          <span style="width:26px"><BrandLogo brand="pma" :size="18" fallback="ext" /></span>
          <div style="flex:1;min-width:180px">
            <b>{{ a.domain }}/pma</b>
            <div class="muted" style="font-size:12.5px">phpMyAdmin {{ a.version || '5.2.2' }}{{ a.protected
              ? ' — вход: логин pma + пароль папки, затем пользователь MySQL'
              : ' — вход пользователем MySQL' }}</div>
          </div>
          <span v-if="a.protected" class="pill ok" title="Папка закрыта паролем">с паролем</span>
          <span v-else class="pill warn" title="Папка открыта — вход по паролю MySQL">без пароля</span>
          <a class="btn sm" style="text-decoration:none" target="_blank" :href="a.url">открыть</a>
          <button class="btn sm" @click="pmaAccessDlg(a.domain)">доступы</button>
          <button class="btn sm" @click="swsetGo('pma')">настройки</button>
          <button class="btn sm icon danger" title="Удалить" @click="pmaRemoveDlg(a.domain)">
            <UiIcon name="trash" :size="13" /></button>
        </div>
      </template>
      <div v-else-if="appsErr" class="empty">{{ appsErr }}</div>
      <div v-else class="empty">Нет PHP-сайтов — создайте сайт с PHP,
        и phpMyAdmin можно будет поставить в 1 клик.</div>
      <div class="muted" style="font-size:12.5px;padding:4px 6px 8px">
        phpMyAdmin скачивается с официального сайта и ставится в папку /pma выбранного сайта;
        папка закрывается отдельным паролем. К базам подключайтесь своими пользователями MySQL.</div>
    </div>

    <!-- каталог служб по группам -->
    <div v-for="(list, g) in groups" :key="g" class="card" style="padding:6px 10px;margin-bottom:12px">
      <div class="card-h" style="padding:10px 6px 0"><span class="card-t">{{ g }}</span></div>
      <div v-for="s in list" :key="s.id" class="row"
           style="align-items:center;padding:10px 6px;border-top:1px solid var(--border)">
        <span style="width:26px"><BrandLogo :brand="s.id" :size="18" :fallback="SW_ICONS[s.id] || 'pkg'" /></span>
        <div style="flex:1;min-width:0">
          <b>{{ s.name }}</b>
          <div class="muted" style="font-size:12.5px">{{ s.desc }}</div>
        </div>
        <span v-if="s.status === 'active'" class="pill ok">работает</span>
        <span v-else-if="s.status === 'installed'" class="pill warn">установлен</span>
        <span v-else class="pill gray">не установлен</span>
        <span style="width:10px"></span>
        <button v-if="s.status !== 'missing' && SWSET_IDS[s.id]" class="btn sm" @click="swsetGo(s.id)">
          <UiIcon name="gear" :size="14" /> Настройки</button>
        <span style="width:6px"></span>
        <button v-if="s.status === 'missing'" class="btn sm primary" @click="swInstall(s.id)">
          <UiIcon name="down" :size="14" /> Установить</button>
        <button v-else class="btn sm" @click="swRemove(s.id)">Удалить</button>
      </div>
    </div>

    <div class="muted" style="font-size:12.5px">
      Перед удалением панель проверяет, не используют ли службу существующие сайты.</div>

    <!-- ionCube Loader -->
    <div id="ioncube-block" style="margin-top:12px">
      <div v-if="ioncube" class="card" style="padding:6px 10px">
        <div class="card-h" style="padding:10px 6px 0">
          <span class="card-t">ionCube Loader</span><span class="card-spacer"></span>
          <span class="muted" style="font-size:12px">официальные загрузчики ioncube.com · обновление = повторная установка</span>
        </div>
        <div v-if="(ioncube.versions || []).length === 0" class="empty">
          Установите любую версию PHP — она появится здесь</div>
        <div v-for="v in (ioncube.versions || [])" :key="v.version" class="row"
             style="align-items:center;padding:10px 6px;border-top:1px solid var(--border)">
          <span style="width:26px"><BrandLogo brand="ioncube" :size="18" fallback="term" /></span>
          <div style="flex:1"><b>PHP {{ v.version }}</b></div>
          <span v-if="v.installed" class="pill ok">ionCube {{ v.loader }}</span>
          <span v-else class="pill gray">не установлен</span>
          <span style="width:10px"></span>
          <template v-if="v.installed">
            <button class="btn sm" @click="ioncubeGo('install', v.version)">
              <UiIcon name="refresh" :size="13" /> Обновить</button>
            <button class="btn sm danger" @click="ioncubeGo('remove', v.version)">Удалить</button>
          </template>
          <button v-else class="btn sm primary" @click="ioncubeGo('install', v.version)">
            <UiIcon name="down" :size="13" /> Установить</button>
        </div>
      </div>
    </div>

    <!-- Установка phpMyAdmin -->
    <AppModal :open="pmaDlgOpen" title="Установка phpMyAdmin" wide @close="pmaDlgOpen = false">
      <div class="field">
        <label>Сайт — куда установить (папка /pma)</label>
        <UiSelect v-model="pmaSite"
                  :options="pmaSites.map((x: any) => ({ value: x.domain,
                    label: x.domain + ((x.ssl || {}).kind !== 'none' ? ' (SSL)' : '') }))" />
      </div>
      <div style="margin:6px 0 4px">
        <UiCheckbox v-model="pmaProtect">Закрыть папку паролем (рекомендуется)</UiCheckbox>
      </div>
      <div v-show="pmaProtect" class="field">
        <PwField v-model="pmaPass" label="Пароль папки /pma" :gen="true"
                 hint="Появится в браузере при входе в phpMyAdmin. Сохраните — увидите его в «доступах»." />
      </div>
      <div class="notice info">Внутри phpMyAdmin входите пользователем MySQL —
        его можно создать в разделе «Базы данных».</div>
      <template #footer>
        <button class="btn primary" @click="pmaInstall()">
          <UiIcon name="down" :size="15" /> Установить</button>
        <button class="btn" @click="pmaDlgOpen = false">Отмена</button>
      </template>
    </AppModal>

    <!-- Доступы phpMyAdmin -->
    <AppModal :open="pmaAccessOpen" :title="'Доступы phpMyAdmin — ' + pmaAccessDomain" wide
              @close="pmaAccessOpen = false">
      <div class="field">
        <label>Адрес</label>
        <div class="row" style="justify-content:space-between;align-items:center;gap:8px;padding:3px 0">
          <span class="muted">открыть в браузере</span>
          <b class="mono" style="flex:1;text-align:right">{{ pmaAccessRow?.url }}</b>
          <button class="btn sm" @click="copyText(pmaAccessRow?.url || '', $event.currentTarget as HTMLElement)">
            <UiIcon name="file" :size="13" /></button>
        </div>
      </div>
      <template v-if="pmaAccessRow?.protected">
        <div class="field">
          <label>Вход в папку (basic auth)</label>
          <div class="row" style="justify-content:space-between;align-items:center;gap:8px;padding:3px 0">
            <span class="muted">логин</span>
            <b class="mono" style="flex:1;text-align:right">{{ pmaAccessRow?.user }}</b>
            <button class="btn sm" @click="copyText(pmaAccessRow?.user || '', $event.currentTarget as HTMLElement)">
              <UiIcon name="file" :size="13" /></button>
          </div>
          <div class="row" style="justify-content:space-between;align-items:center;gap:8px;padding:3px 0">
            <span class="muted">пароль</span>
            <b class="mono" style="flex:1;text-align:right">{{ pmaAccessRow?.password }}</b>
            <button class="btn sm" @click="copyText(pmaAccessRow?.password || '', $event.currentTarget as HTMLElement)">
              <UiIcon name="file" :size="13" /></button>
          </div>
        </div>
        <div class="faint" style="font-size:12px">Затем — пользователь и пароль MySQL.</div>
      </template>
      <div v-else class="notice warn">Папка не закрыта паролем. Входите сразу пользователем MySQL.</div>
      <template #footer>
        <button class="btn" @click="pmaAccessOpen = false">Закрыть</button>
      </template>
    </AppModal>
  </div>
</template>
