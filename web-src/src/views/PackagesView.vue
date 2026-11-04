<script setup lang="ts">
/* ============ Страница: Пакеты и обновления + PHP-модули ============ */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtDate } from '../lib/format';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';

interface Upg { pkg: string; kind: string; cur?: string; new?: string }
interface TaskHistItem { ok: boolean; finished?: string; kind: string; error?: string }

/* ---- данные страницы ---- */
const pageState = ref<'loading' | 'ok' | 'fail'>('loading');
const upgradable = ref<Upg[]>([]);
const aptUpdated = ref('');
const checked = ref<Record<string, boolean>>({});
const kindChecked = ref<Record<string, boolean>>({});
const phpVersions = ref<string[]>([]);
const phpVer = ref('');

const kinds = computed<Record<string, Upg[]>>(() => {
  const res: Record<string, Upg[]> = {};
  (upgradable.value || []).forEach((u) => {
    (res[u.kind] = res[u.kind] || []).push(u);
  });
  return res;
});

async function load(): Promise<void> {
  let d: any;
  try { d = await api('/api/packages'); }
  catch (e) { pageState.value = 'fail'; toastErr(e); return; }
  upgradable.value = d.upgradable || [];
  aptUpdated.value = d.apt_updated || '';
  const chk: Record<string, boolean> = {};
  const kchk: Record<string, boolean> = {};
  upgradable.value.forEach((u) => { chk[u.pkg] = true; kchk[u.kind] = true; });
  checked.value = chk;
  kindChecked.value = kchk;
  // версии PHP грузим до показа страницы — иначе селект «Установки
  // PHP-модулей» рисуется пустым и заполняется только при удачном догружении
  try {
    const php = await api('/api/php');
    phpVersions.value = Object.keys(php.versions || {}).sort().reverse();
  } catch (e) { phpVersions.value = []; }
  phpVer.value = phpVersions.value[0] || '';
  pageState.value = 'ok';
}

/* ---- фоновая задача пакетного менеджера ---- */
const taskRunning = ref<{ kind: string; log: string[] } | null>(null);
const taskHistory = ref<TaskHistItem[]>([]);
let pollTimer: ReturnType<typeof setTimeout> | null = null;

/** Опрос фоновой задачи пакетного менеджера. */
async function pkgTaskPoll(): Promise<void> {
  try {
    const d = await api('/api/packages/task');
    if (d.running) {
      taskRunning.value = { kind: d.kind, log: d.log || [] };
      taskHistory.value = d.history || [];
      pollTimer = setTimeout(pkgTaskPoll, 2000);
    } else {
      taskRunning.value = null;
      taskHistory.value = d.history || [];
    }
  } catch (e) { /* экран уже открыт — тихо */ }
}

function stopPoll(): void {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
}

onMounted(() => { load(); pkgTaskPoll(); });
onBeforeUnmount(stopPoll);

/* ---- обновление индексов и выборочное обновление ---- */
async function aptUpdate(): Promise<void> {
  try {
    const r = await api('/api/packages/update_index', { method: 'POST', body: {} });
    toast(r.message);
    pkgTaskPoll();
  } catch (e) { toastErr(e); }
}

function toggleKind(kind: string, ev: Event): void {
  const on = (ev.target as HTMLInputElement).checked;
  kindChecked.value[kind] = on;
  upgradable.value.forEach((u) => { if (u.kind === kind) checked.value[u.pkg] = on; });
}

function upgradeKind(kind: string): void {
  const names = upgradable.value
    .filter((u) => u.kind === kind && checked.value[u.pkg])
    .map((u) => u.pkg);
  if (!names.length) { toast('ничего не выбрано', 'warn'); return; }
  confirmDlg('Обновить пакеты', 'Обновить ' + names.length + ' пакет(ов) ' + kind + '?',
    async () => {
      try {
        const r = await api('/api/packages/upgrade', { method: 'POST', body: { names } });
        toast(r.message);
        pkgTaskPoll();
      } catch (e) { toastErr(e); }
    });
}

/* ---- установка PHP-модулей ---- */
const modOpen = ref(false);
const modVersion = ref('');
const modAvailable = ref<string[]>([]);
const modInstalled = ref<Set<string>>(new Set());
const modSel = ref<string[]>([]);
const modNames = ref<Record<string, string>>({});

async function openPhpModules(): Promise<void> {
  const version = phpVer.value;
  if (!version) { toast('выберите версию PHP', 'warn'); return; }
  let d: any;
  try { d = await api('/api/php/modules?version=' + encodeURIComponent(version)); }
  catch (e) { toastErr(e); return; }
  modVersion.value = version;
  modAvailable.value = d.available || [];
  modInstalled.value = new Set(d.installed || []);
  modSel.value = [];
  modOpen.value = true;
  // подтягиваем описания модулей
  try {
    const php = await api('/api/php');
    modNames.value = php.module_names || {};
  } catch (e) { /* описания не критичны */ }
}

function installPhpModules(): Promise<void> {
  const version = modVersion.value;
  const mods = modSel.value.slice();
  if (!mods.length) { toast('ничего не выбрано', 'warn'); return Promise.resolve(); }
  return new Promise((resolve) => {
    confirmDlg('Установить модули',
      'Установить ' + mods.length + ' PHP-модуль(ей) для PHP ' + version + ' через apt?',
      async () => {
        modOpen.value = false;
        for (const m of mods) {
          try { await api('/api/php/install_module', { method: 'POST', body: { version, module: m } }); }
          catch (e) { toastErr(e); }
        }
        toast('установка запущена (' + mods.length + ' модулей)');
        pkgTaskPoll();
        resolve();
      }, false);
  });
}
</script>

<template>
  <div v-table>
    <div v-if="pageState === 'loading'" class="empty">Загрузка…</div>
    <template v-else-if="pageState === 'ok'">
      <div class="toolbar">
        <button class="btn" @click="aptUpdate()">
          <UiIcon name="refresh" :size="15" /> Обновить индексы apt</button>
        <span class="spacer"></span>
        <span class="muted" style="font-size:13px">Доступно обновлений: {{ upgradable.length }}</span>
      </div>

      <!-- фоновая задача пакетного менеджера -->
      <div v-if="taskRunning" class="notice info">
        <b>Выполняется:</b> {{ taskRunning.kind }} <span class="dot pulse"></span>
        <div class="logbox" style="margin-top:8px;max-height:150px">{{ taskRunning.log.join('\n') }}</div>
      </div>
      <div v-else-if="taskHistory.length" class="card" style="margin-top:12px">
        <div class="card-h">
          <span class="card-t">Последние операции</span>
          <span class="card-spacer"></span>
          <span class="pill gray">{{ taskHistory.length }}</span>
        </div>
        <div v-for="(x, i) in taskHistory.slice(0, 12)" :key="i"
             class="row" style="align-items:center;gap:8px;padding:3px 0">
          <span class="pill" :class="x.ok ? 'ok' : 'err'">{{ x.ok ? 'ок' : 'ошибка' }}</span>
          <span class="faint" style="width:110px">{{ (x.finished || '').slice(0, 16) }}</span>
          <span style="flex:1">{{ x.kind }}{{ x.error ? ' — ' + x.error : '' }}</span>
        </div>
      </div>

      <div v-if="aptUpdated" class="notice info">Индексы apt обновлялись: {{ fmtDate(aptUpdated) }}</div>

      <div v-for="(list, kind) in kinds" :key="kind" class="card" style="padding:6px 10px;margin-bottom:12px">
        <div class="card-h" style="padding:10px 6px 0">
          <span class="card-t">{{ kind }}</span>
          <span class="card-spacer"></span>
          <button class="btn sm primary" @click="upgradeKind(kind)">обновить все {{ kind }}</button>
        </div>
        <div class="twrap"><table>
          <thead><tr>
            <th><input type="checkbox" :checked="kindChecked[kind]" @change="toggleKind(kind, $event)"></th>
            <th>Пакет</th><th>Текущая</th><th>Новая</th>
          </tr></thead>
          <tbody>
            <tr v-for="u in list" :key="u.pkg">
              <td><input v-model="checked[u.pkg]" type="checkbox"></td>
              <td class="mono">{{ u.pkg }}</td>
              <td class="mono muted">{{ u.cur || '—' }}</td>
              <td class="mono">{{ u.new || '—' }}</td>
            </tr>
          </tbody>
        </table></div>
      </div>
      <div v-if="!upgradable.length" class="empty">Всё актуально — обновлений нет.</div>

      <div class="card">
        <div class="card-h"><span class="card-t">Установка PHP-модулей</span></div>
        <div class="row">
          <div style="flex:1">
            <select v-model="phpVer">
              <option v-if="!phpVersions.length" value="">PHP не обнаружен</option>
              <option v-for="v in phpVersions" :key="v" :value="v">PHP {{ v }}</option>
            </select>
          </div>
          <button class="btn" @click="openPhpModules()">Выбрать модули…</button>
        </div>
        <div class="muted" style="font-size:12.5px;margin-top:8px">
          Модули ставятся из репозитория apt (phpX.Y-имя) и сразу подключаются к FPM.
        </div>
      </div>
    </template>
  </div>

  <!-- выбор PHP-модулей -->
  <AppModal :open="modOpen" :title="'PHP-модули для ' + modVersion" wide @close="modOpen = false">
    <div class="notice info">Установленные модули отмечены галочкой и недоступны. Новые ставятся через apt в фоне.</div>
    <div style="max-height:300px;overflow:auto;border:1px solid var(--border);border-radius:10px;padding:10px">
      <label v-for="m in modAvailable" :key="m" class="check"
             :style="{ margin: '4px 0', opacity: modInstalled.has(m) ? 0.5 : 1 }">
        <input v-model="modSel" type="checkbox" :value="m" :disabled="modInstalled.has(m)">
        {{ m }}
        <span v-if="modNames[m]" class="faint">— {{ modNames[m] }}</span>
        <span v-if="modInstalled.has(m)" class="pill ok" style="margin-left:auto">установлен</span>
      </label>
    </div>
    <template #footer>
      <button class="btn primary" @click="installPhpModules()">
        <UiIcon name="down" :size="15" /> Установить выбранные</button>
      <button class="btn" @click="modOpen = false">Отмена</button>
    </template>
  </AppModal>
</template>
