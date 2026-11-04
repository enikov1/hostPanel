<script setup lang="ts">
/* Файловый менеджер: навигация, загрузка, редактор, архивы, права. */
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { api, apiForm, downloadFile } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtSize } from '../lib/format';
import { me } from '../stores';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import CodeEditor from '../components/CodeEditor.vue';

interface FileItem {
  name: string;
  type: string;
  size?: number;
  mtime?: string;
  perms?: string;
  owner?: string;
  target?: string;
  editable?: boolean;
}

const route = useRoute();

const fmpath = ref('');
const d = ref<{ path: string; parent: string; items: FileItem[] } | null>(null);
const loadErr = ref('');
const loading = ref(false);

/* --- модалки --- */
const mkdirDlg = ref(false);
const mkdirName = ref('');

const editDlg = ref(false);
const editPath = ref('');
const editText = ref('');
const editLang = ref('markup');

const renameDlg = ref(false);
const renamePath = ref('');
const renameName = ref('');

const chmodDlg = ref(false);
const chmodPath = ref('');
const chmodOctal = ref('');

const uploadEl = ref<HTMLInputElement | null>(null);

/* Язык Prism по пути файла (как в прежнем редакторе кода). */
function prismLangFromPath(path: string): string {
  const ext = (path.split('.').pop() || '').toLowerCase();
  const map: Record<string, string> = {
    php: 'php', conf: 'nginx', ini: 'ini', sql: 'sql', json: 'json',
    js: 'javascript', mjs: 'javascript', css: 'css', html: 'markup', htm: 'markup',
    py: 'python', sh: 'bash', yml: 'yaml', yaml: 'yaml', htaccess: 'apacheconf',
    htpasswd: 'apacheconf', md: 'markup', xml: 'markup', cnf: 'ini', env: 'bash',
    service: 'ini', timer: 'ini', socket: 'ini',
  };
  if (path.includes('nginx')) return 'nginx';
  if (path.includes('apache') || path.includes('.ht')) return 'apacheconf';
  return map[ext] || 'markup';
}

/* Символьные права (rwxr-xr-x) -> октальная строка (755). */
function symToOctal(perms: string): string {
  const s = String(perms).slice(-9);
  let out = '';
  for (let g = 0; g < 3; g++) {
    let v = 0;
    const seg = s.slice(g * 3, g * 3 + 3);
    if (seg[0] === 'r') v += 4;
    if (seg[1] === 'w') v += 2;
    if (seg[2] === 'x' || seg[2] === 's' || seg[2] === 't') v += 1;
    out += String(v);
  }
  return out || '644';
}

function isArchive(name: string): boolean {
  return /\.(zip|tar|gz|tgz)$/i.test(name);
}

function baseName(e: FileItem): string {
  return e.name.replace(/\/$/, '');
}

/** Полный путь элемента в текущей папке. */
function full(e: FileItem): string {
  const p = d.value ? d.value.path : fmpath.value;
  return (p === '/' ? '' : p) + '/' + baseName(e);
}

const crumbs = computed(() => {
  const p = d.value ? d.value.path : fmpath.value;
  const parts = p === '/' ? [] : p.split('/').filter(Boolean);
  let acc = '';
  return parts.map((x) => {
    acc += '/' + x;
    return { name: x, path: acc };
  });
});

async function load(): Promise<void> {
  loading.value = true;
  loadErr.value = '';
  try {
    d.value = await api('/api/files?path=' + encodeURIComponent(fmpath.value));
  } catch (e: any) {
    d.value = null;
    loadErr.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

function go(p: string): void {
  fmpath.value = p;
  load();
}

onMounted(() => {
  const sp = route.query.path;
  if (typeof sp === 'string' && sp) fmpath.value = sp;
  if (!fmpath.value) fmpath.value = me.demo ? '' : me.www_root;
  load();
});

/* Переход из карточки сайта, пока раздел уже открыт. */
watch(() => route.query.path, (v) => {
  if (typeof v === 'string' && v && v !== fmpath.value) go(v);
});

/* --- папка --- */
function mkdirOpen(): void {
  mkdirName.value = '';
  mkdirDlg.value = true;
}

async function mkdir(): Promise<void> {
  const p = d.value ? d.value.path : fmpath.value;
  try {
    const r = await api('/api/files/mkdir', { method: 'POST',
      body: { path: p + '/' + mkdirName.value } });
    toast(r.message);
    mkdirDlg.value = false;
    go(p);
  } catch (e) { toastErr(e); }
}

/* --- редактор --- */
async function edit(path: string): Promise<void> {
  try {
    const resp = await api('/api/files/read?path=' + encodeURIComponent(path));
    editPath.value = path;
    editText.value = resp.content || '';
    editLang.value = prismLangFromPath(path);
    editDlg.value = true;
  } catch (e) { toastErr(e); }
}

async function save(): Promise<void> {
  try {
    const r = await api('/api/files/save', { method: 'POST',
      body: { path: editPath.value, content: editText.value } });
    toast(r.message);
    editDlg.value = false;
    go(fmpath.value);
  } catch (e) { toastErr(e); }
}

/* --- удаление / переименование --- */
function del(e: FileItem): void {
  const path = full(e);
  const name = baseName(e);
  confirmDlg('Удалить', 'Удалить ' + name + '?', async () => {
    try {
      const r = await api('/api/files/delete', { method: 'POST',
        body: { paths: [path] } });
      toast(r.message);
      go(fmpath.value);
    } catch (err) { toastErr(err); }
  });
}

function renameOpen(e: FileItem): void {
  renamePath.value = full(e);
  renameName.value = baseName(e);
  renameDlg.value = true;
}

async function renameDo(): Promise<void> {
  try {
    const r = await api('/api/files/rename', { method: 'POST',
      body: { path: renamePath.value, new_name: renameName.value } });
    toast(r.message);
    renameDlg.value = false;
    go(fmpath.value);
  } catch (err) { toastErr(err); }
}

/* --- загрузка / скачивание --- */
async function upload(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement;
  if (!input.files || !input.files.length) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  try {
    const r = await apiForm('/api/files/upload?dest=' + encodeURIComponent(fmpath.value), fd);
    toast(r.message);
    go(fmpath.value);
  } catch (e) { toastErr(e); }
  input.value = '';
}

async function download(e: FileItem): Promise<void> {
  try {
    await downloadFile('/api/files/download?path=' + encodeURIComponent(full(e)),
                       baseName(e));
  } catch (err) { toastErr(err); }
}

/* --- архивы --- */
async function extract(e: FileItem): Promise<void> {
  try {
    const r = await api('/api/files/extract', { method: 'POST',
      body: { path: full(e) } });
    toast(r.message);
    go(fmpath.value);
  } catch (err) { toastErr(err); }
}

async function zip(e: FileItem): Promise<void> {
  try {
    const r = await api('/api/files/zip', { method: 'POST',
      body: { paths: [full(e)], dest: full(e) + '.zip' } });
    toast(r.message);
    go(fmpath.value);
  } catch (err) { toastErr(err); }
}

/* --- права --- */
function chmodOpen(e: FileItem): void {
  chmodPath.value = full(e);
  chmodOctal.value = symToOctal(e.perms || '');
  chmodDlg.value = true;
}

async function chmodDo(): Promise<void> {
  try {
    const r = await api('/api/files/chmod', { method: 'POST',
      body: { path: chmodPath.value, octal: chmodOctal.value.trim() } });
    toast(r.message);
    chmodDlg.value = false;
    go(fmpath.value);
  } catch (err) { toastErr(err); }
}
</script>

<template>
  <div v-table>
    <div v-if="loading && !d" class="empty">Загрузка…</div>
    <div v-else-if="loadErr" class="notice err">{{ loadErr }}</div>
    <template v-else-if="d">
      <div class="toolbar">
        <button class="btn" @click="mkdirOpen()"><UiIcon name="plus" :size="15" /> Папка</button>
        <button class="btn" @click="uploadEl?.click()"><UiIcon name="up" :size="15" /> Загрузить</button>
        <input ref="uploadEl" type="file" class="hidden" @change="upload">
        <button class="btn" @click="go(fmpath)"><UiIcon name="refresh" :size="15" /> Обновить</button>
        <span class="spacer"></span>
        <span class="muted" style="font-size:12.5px">Объектов: {{ d.items.length }}</span>
      </div>
      <div class="card" style="padding:10px">
        <div class="bread" style="margin-bottom:10px">
          <button @click="go('/')">/ корень</button>
          <template v-for="c in crumbs" :key="c.path">
            <span class="sep">›</span>
            <button @click="go(c.path)">{{ c.name }}</button>
          </template>
        </div>
        <div class="twrap">
          <table>
            <thead>
              <tr><th>Имя</th><th>Размер</th><th>Изменён</th><th>Права</th><th>Владелец</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-if="d.parent">
                <td colspan="6">
                  <button class="btn sm" @click="go(d.parent)">← вверх</button>
                </td>
              </tr>
              <tr v-for="e in d.items" :key="e.name">
                <td>
                  <span class="row" style="gap:8px;flex-wrap:nowrap">
                    <span class="muted"><UiIcon :name="e.type === 'dir' ? 'folder' : 'file'" :size="15" /></span>
                    <span class="mono" style="word-break:break-all">{{ e.name }}</span>
                    <span v-if="e.type === 'link'" class="faint mono">→ {{ e.target }}</span>
                  </span>
                </td>
                <td>{{ e.type === 'dir' ? '—' : fmtSize(e.size) }}</td>
                <td class="muted">{{ e.mtime }}</td>
                <td class="mono">{{ e.perms }}</td>
                <td class="muted">{{ e.owner }}</td>
                <td>
                  <div class="actions-cell">
                    <button v-if="e.type === 'dir'" class="btn sm icon" title="Открыть"
                            @click="go(full(e))"><UiIcon name="ext" :size="13" /></button>
                    <button v-if="e.type !== 'dir' && e.editable" class="btn sm icon" title="Редактировать"
                            @click="edit(full(e))"><UiIcon name="edit" :size="13" /></button>
                    <button v-if="e.type !== 'dir'" class="btn sm icon" title="Скачать"
                            @click="download(e)"><UiIcon name="down" :size="13" /></button>
                    <button v-if="isArchive(e.name)" class="btn sm icon" title="Распаковать"
                            @click="extract(e)"><UiIcon name="archive" :size="13" /></button>
                    <button class="btn sm icon" title="Права (chmod)"
                            @click="chmodOpen(e)"><UiIcon name="wrench" :size="13" /></button>
                    <button class="btn sm icon" title="В zip-архив"
                            @click="zip(e)"><UiIcon name="archive" :size="13" /></button>
                    <button class="btn sm icon" title="Переименовать"
                            @click="renameOpen(e)"><UiIcon name="edit" :size="13" /></button>
                    <button class="btn sm icon danger" title="Удалить"
                            @click="del(e)"><UiIcon name="trash" :size="13" /></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <AppModal :open="mkdirDlg" title="Новая папка" @close="mkdirDlg = false">
      <div class="field">
        <label>Имя папки</label>
        <input v-model="mkdirName" type="text" @keyup.enter="mkdir()">
      </div>
      <template #footer>
        <button class="btn primary" @click="mkdir()">Создать</button>
        <button class="btn" @click="mkdirDlg = false">Отмена</button>
      </template>
    </AppModal>

    <AppModal :open="editDlg" :title="'Файл: ' + editPath" wide @close="editDlg = false">
      <CodeEditor v-model="editText" :lang="editLang" />
      <div class="faint" style="font-size:11.5px;margin-top:6px">
        подсветка: {{ editLang }} · Tab — отступ
      </div>
      <template #footer>
        <button class="btn primary" @click="save()"><UiIcon name="check" :size="15" /> Сохранить</button>
        <button class="btn" @click="editDlg = false">Отмена</button>
      </template>
    </AppModal>

    <AppModal :open="renameDlg" title="Переименовать" @close="renameDlg = false">
      <div class="field">
        <label>Новое имя</label>
        <input v-model="renameName" type="text" @keyup.enter="renameDo()">
      </div>
      <template #footer>
        <button class="btn primary" @click="renameDo()">OK</button>
        <button class="btn" @click="renameDlg = false">Отмена</button>
      </template>
    </AppModal>

    <AppModal :open="chmodDlg" title="Права доступа" @close="chmodDlg = false">
      <div class="field">
        <label>Права (окталы, например 644)</label>
        <input v-model="chmodOctal" type="text" class="mono" maxlength="4" @keyup.enter="chmodDo()">
      </div>
      <template #footer>
        <button class="btn primary" @click="chmodDo()">Применить</button>
        <button class="btn" @click="chmodDlg = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
