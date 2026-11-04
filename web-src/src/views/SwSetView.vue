<script setup lang="ts">
/* ============ Страница: Настройки ПО (пароли, поля, конфиги служб) ============ */
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { copyText } from '../lib/clipboard';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';
import CodeEditor from '../components/CodeEditor.vue';

const SWSET_ICONS: Record<string, string> = {
  nginx: 'globe', apache: 'server', mariadb: 'db',
  postgresql: 'db', redis: 'zap', memcached: 'zap', postfix: 'ext',
  dovecot: 'archive', fail2ban: 'shield', pma: 'db',
};

/** Prism-язык по kind конфига (как в старом code-editor). */
function prismLangFromKind(kind: string): string {
  return ({
    nginx: 'nginx', apache: 'apacheconf', fpm: 'ini', php: 'ini',
    ini: 'ini', conf: 'bash', postfix: 'ini', dovecot: 'bash',
    fail2ban: 'ini',
  } as Record<string, string>)[kind] || 'markup';
}

const route = useRoute();
const router = useRouter();

const loaded = ref(false);
const entries = ref<any[]>([]);

function groupsOf(list: any[]): string[] {
  const g: string[] = [];
  list.forEach((e: any) => {
    const gr = e.group || 'Прочее';
    if (!g.includes(gr)) g.push(gr);
  });
  return g;
}

function tileIcon(e: any): string {
  return SWSET_ICONS[e.id] || (e.id.indexOf('php') === 0 ? 'gear' : 'pkg');
}

function tileCounts(e: any): string {
  const counts: string[] = [];
  if (e.fields.length) counts.push('параметров: ' + e.fields.length);
  if ((e.files || []).filter((f: any) => f.path).length)
    counts.push('конфигов: ' + e.files.filter((f: any) => f.path).length);
  if (e.passwords.length) counts.push('паролей: ' + e.passwords.length);
  return counts.length ? counts.join(' · ') + ' — нажмите, чтобы настроить' : 'нажмите, чтобы настроить';
}

const highlight = ref('');

async function load(): Promise<void> {
  let d: any;
  try { d = await api('/api/swset'); }
  catch (e) { if (!loaded.value) toastErr(e); return; }
  entries.value = d.entries || [];
  loaded.value = true;
  // подсветка/открытие по ?open=<id> (кнопка «Настройки» из каталога ПО)
  const hl = String(route.query.open || '');
  if (hl) {
    router.replace({ path: '/software/settings' });
    const e = entries.value.find((x: any) => x.id === hl);
    if (e) { swsetEntryDlg(hl); return; }
    highlight.value = hl; // запись ещё не установлена — подсветим плитку, когда появится
  }
}

/* ---------- модальное окно настроек модуля ---------- */
const entryOpen = ref(false);
const entry = ref<any | null>(null);
const curFields = ref<any[]>([]);

function swsetEntryDlg(id: string): void {
  const e = entries.value.find((x: any) => x.id === id);
  if (!e) return;
  entry.value = e;
  curFields.value = (e.fields || []).map((f: any) => ({ ...f }));
  entryOpen.value = true;
}

async function swsetSave(): Promise<void> {
  const e = entry.value;
  if (!e) return;
  const fields: Record<string, any> = {};
  curFields.value.forEach((f: any) => { fields[f.key] = f.value; });
  try {
    const r = await api('/api/swset/save', { method: 'POST', body: { id: e.id, fields } });
    toast(r.message);
    entryOpen.value = false;
    load();
  } catch (err) { toastErr(err); }
}

/* ---------- конфигурационные файлы ---------- */
const fileOpen = ref(false);
const filePath = ref('');
const fileLang = ref('markup');
const fileContent = ref('');
const fileBackups = ref<any[]>([]);
let curFile: { id: string; name: string } | null = null;

async function swFileEdit(id: string, name: string): Promise<void> {
  let d: any;
  try {
    d = await api('/api/swset/file?id=' + encodeURIComponent(id) + '&name=' + encodeURIComponent(name));
  } catch (e) { toastErr(e); return; }
  curFile = { id, name };
  filePath.value = d.path;
  fileLang.value = prismLangFromKind(d.kind || '');
  fileContent.value = d.content || '';
  fileBackups.value = (d.backups || []).slice(0, 5);
  entryOpen.value = false;
  fileOpen.value = true;
}

async function swFileSave(): Promise<void> {
  if (!curFile) return;
  const { id, name } = curFile;
  try {
    const r = await api('/api/swset/file', { method: 'POST',
      body: { id, name, content: fileContent.value } });
    toast(r.message);
    fileOpen.value = false;
    load();
  } catch (e) { toastErr(e); }
}

async function swFileRestore(file: string): Promise<void> {
  if (!curFile) return;
  const { id, name } = curFile;
  confirmDlg('Восстановить копию',
    'Восстановить конфиг ' + name + ' из копии ' + file + '? Служба будет перезагружена с прежними настройками.',
    async () => {
      try {
        const r = await api('/api/swset/restore', { method: 'POST',
          body: { id, name, file } });
        toast(r.message);
        fileOpen.value = false;
        load();
      } catch (e) { toastErr(e); }
    }, false);
}

/* ---------- пароли служб ---------- */
const pwOpen = ref(false);
const pwEntryName = ref('');
const pwHint = ref('');
const pwVal = ref('');
const pwOut = ref('');
let pwId = '';
let pwKey = '';

function swPassDlg(id: string, key: string): void {
  const e = entries.value.find((x: any) => x.id === id);
  const p = e ? (e.passwords.find((x: any) => x.key === key) || {}) : {};
  pwId = id;
  pwKey = key;
  pwEntryName.value = e ? e.name : id;
  pwHint.value = p.hint || 'Пароль будет показан после смены — сохраните его.';
  pwVal.value = '';
  pwOut.value = '';
  entryOpen.value = false;
  pwOpen.value = true;
}

async function swPassDo(): Promise<void> {
  try {
    const r = await api('/api/swset/password', { method: 'POST',
      body: { id: pwId, key: pwKey, password: pwVal.value } });
    pwOut.value = r.password || pwVal.value;
    if (r.message) console.log(r.message);
  } catch (e) { toastErr(e); }
}

async function swPassClear(id: string, key: string): Promise<void> {
  confirmDlg('Убрать пароль',
    'Убрать пароль подключения к Redis? Подключения без пароля станут возможны ' +
    '(следите, чтобы порт слушал только 127.0.0.1).', async () => {
      try {
        const r = await api('/api/swset/password', { method: 'POST',
          body: { id, key, clear: true } });
        toast(r.message);
        load();
      } catch (e) { toastErr(e); }
    });
}

onMounted(load);
</script>

<template>
  <div>
    <div class="empty" v-if="loaded && !entries.length">Установите службы в разделе «Установка ПО» —
      и здесь появятся их настройки.</div>

    <template v-else-if="entries.length">
      <div class="toolbar">
        <span class="muted" style="font-size:13px">Настройки установленных служб —
          по одному модулю в отдельном окне. Перед каждым изменением панель делает копию конфига;
          если служба с новым конфигом не поднимается — настройки откатываются автоматически.</span>
      </div>

      <template v-for="g in groupsOf(entries)" :key="g">
        <label style="margin-top:14px">{{ g }}</label>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px">
          <div v-for="e in entries.filter((x: any) => (x.group || 'Прочее') === g)" :key="e.id"
               class="card swset-tile" :id="'swset-' + e.id"
               :style="{ cursor: 'pointer', margin: 0,
                         outline: highlight === e.id ? '2px solid var(--accent)' : '' }"
               title="Открыть настройки" @click="swsetEntryDlg(e.id)">
            <div class="card-h">
              <span style="width:26px;display:inline-block">
                <UiIcon :name="tileIcon(e)" :size="18" /></span>
              <span class="card-t">{{ e.name }}</span>
              <span v-if="e.active === true" class="pill ok">работает</span>
              <span v-else-if="e.active === false" class="pill err">остановлен</span>
            </div>
            <div v-if="e.note" class="muted"
                 style="font-size:12px;padding:0 6px 4px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">
              {{ e.note }}</div>
            <div class="faint" style="font-size:11.5px;padding:0 6px 6px">{{ tileCounts(e) }}</div>
          </div>
        </div>
      </template>
    </template>

    <!-- настройки модуля -->
    <AppModal :open="entryOpen" :title="entry ? entry.name : ''" wide @close="entryOpen = false">
      <template v-if="entry">
        <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:6px">
          <div class="muted" style="font-size:12.5px;flex:1">{{ entry.note }}</div>
          <span v-if="entry.active === true" class="pill ok">работает</span>
          <span v-else-if="entry.active === false" class="pill err">остановлен</span>
        </div>

        <template v-if="curFields.length">
          <b style="font-size:13px">Параметры</b>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px 14px;padding:6px 0 2px">
            <div v-for="f in curFields" :key="f.key" class="field" style="margin:0">
              <label>{{ f.label }}</label>
              <select v-if="f.type === 'choice'" v-model="f.value" class="mono">
                <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
              </select>
              <label v-else-if="f.type === 'bool'" style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input v-model="f.value" type="checkbox"> включено</label>
              <input v-else-if="f.type === 'int' || f.type === 'float'" v-model="f.value" type="number"
                     class="mono" :step="f.type === 'float' ? '0.1' : '1'"
                     :min="f.min" :max="f.max">
              <input v-else v-model="f.value" type="text" class="mono">
              <div v-if="f.hint" class="faint" style="font-size:11.5px;margin-top:3px">{{ f.hint }}</div>
            </div>
          </div>
          <div style="padding:4px 0 8px">
            <button class="btn sm primary" @click="swsetSave()">
              <UiIcon name="check" :size="14" /> Сохранить параметры</button>
          </div>
        </template>

        <template v-if="entry.passwords.length">
          <b style="font-size:13px">Пароли</b>
          <div style="padding:4px 0 6px">
            <div v-for="p in entry.passwords" :key="p.key" class="row"
                 style="align-items:center;padding:6px 0;gap:10px">
              <div style="flex:1;min-width:0">
                <b style="font-size:13px">{{ p.label }}</b>
                <div v-if="p.hint" class="muted" style="font-size:12px">{{ p.hint }}</div>
              </div>
              <button class="btn sm" @click="swPassDlg(entry.id, p.key)">Сменить</button>
              <button v-if="entry.id === 'redis'" class="btn sm danger"
                      @click="swPassClear(entry.id, p.key)">Убрать</button>
            </div>
          </div>
        </template>

        <template v-if="(entry.files || []).filter((f: any) => f.path).length">
          <b style="font-size:13px">Конфигурационные файлы</b>
          <div style="padding:4px 0 2px">
            <div v-for="f in (entry.files || []).filter((f: any) => f.path)" :key="f.path" class="row"
                 style="align-items:center;padding:6px 0;gap:10px">
              <div style="flex:1;min-width:0">
                <span class="mono" style="font-size:12.5px">{{ f.path }}</span>
              </div>
              <button class="btn sm" @click="swFileEdit(entry.id, f.name)">
                <UiIcon name="file" :size="14" /> Редактировать</button>
            </div>
          </div>
        </template>
      </template>
      <template #footer>
        <button class="btn primary" @click="entryOpen = false">Закрыть</button>
      </template>
    </AppModal>

    <!-- редактор конфига -->
    <AppModal :open="fileOpen" :title="'Конфиг: ' + filePath" wide="xwide" @close="fileOpen = false">
      <CodeEditor v-model="fileContent" :lang="fileLang" />
      <div class="faint" style="font-size:11.5px;margin-top:6px">
        при сохранении панель делает копию и проверяет синтаксис; при ошибке конфиг откатится</div>
      <div v-if="fileBackups.length" class="faint" style="font-size:11.5px;margin-top:4px">
        Копии:
        <template v-for="(b, i) in fileBackups" :key="b.file"><a href="#" style="text-decoration:underline"
           title="восстановить" @click.prevent="swFileRestore(b.file)">{{ b.file }}</a><span v-if="i < fileBackups.length - 1"> · </span></template>
      </div>
      <template #footer>
        <button class="btn primary" @click="swFileSave()">
          <UiIcon name="check" :size="15" /> Сохранить</button>
        <button class="btn" @click="fileOpen = false">Отмена</button>
      </template>
    </AppModal>

    <!-- смена пароля службы -->
    <AppModal :open="pwOpen" :title="'Сменить пароль — ' + pwEntryName" @close="pwOpen = false">
      <PwField v-model="pwVal" label="Новый пароль (пусто — сгенерировать автоматически)"
               :gen="true" :hint="pwHint" />
      <div v-if="pwOut" class="notice ok" style="margin-top:8px">
        <b>Пароль изменён:</b>
        <span class="mono">{{ pwOut }}</span>
        <button class="btn sm icon" @click="copyText(pwOut, $event.currentTarget as HTMLElement)">
          <UiIcon name="file" :size="13" /></button>
        <div class="faint" style="font-size:11.5px;margin-top:4px">
          скопируйте и сохраните — больше он не покажется</div>
      </div>
      <template #footer>
        <button class="btn primary" @click="swPassDo()">Сменить пароль</button>
        <button class="btn" @click="pwOpen = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
