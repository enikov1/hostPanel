<script setup lang="ts">
/* Файловый менеджер в духе проводника: дерево папок, история навигации,
   крошки, выделение (клик/Ctrl/Shift/Ctrl+A), контекстное меню, внутренний
   буфер обмена (вырезать/копировать/вставить), drag&drop (перенос на папку
   и загрузка с компьютера), два режима вида, сортировка, поиск по имени,
   загрузка с журналом, скачивание выбранных (одиночный файл или zip),
   архивы, права, редактор кода. */
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { api, apiForm, downloadFile } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtSize } from '../lib/format';
import { copyText } from '../lib/clipboard';
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
  octal?: string;
  owner?: string;
  target?: string;
  editable?: boolean;
}

interface DirData {
  path: string;
  parent: string;
  items: FileItem[];
}

interface TNode {
  path: string;
  name: string;
  open: boolean;
  loaded: boolean;
  err: string;
  children: TNode[];
}

interface CtxItem {
  label: string;
  icon?: string;
  danger?: boolean;
  sep?: boolean;
  act: () => void;
}

interface UploadLogItem {
  id: number;
  name: string;
  ok: boolean;
  msg: string;
}

const route = useRoute();

/* ---------- состояние списка ---------- */
const fmpath = ref('');
const d = ref<DirData | null>(null);
const loadErr = ref('');
const loading = ref(false);

const histBack = ref<string[]>([]);
const histFwd = ref<string[]>([]);

/* ---------- выделение ---------- */
const sel = ref<Set<string>>(new Set());
let anchor: string | null = null;

/* ---------- поиск / сортировка / вид (настройки в localStorage) ---------- */
const filter = ref('');

function loadPrefs(): { k: string; a: boolean } {
  try {
    const s = JSON.parse(localStorage.getItem('fm_sort') || '');
    if (s && ['name', 'size', 'mtime', 'type'].includes(s.k)) {
      return { k: s.k, a: s.a !== false };
    }
  } catch (e) { /* нет сохранённых настроек */ }
  return { k: 'name', a: true };
}
const prefs = loadPrefs();
const sortKey = ref<string>(prefs.k);
const sortAsc = ref<boolean>(prefs.a);
const viewMode = ref<'list' | 'icons'>((() => {
  try { return localStorage.getItem('fm_view') === 'icons' ? 'icons' : 'list'; }
  catch (e) { return 'list'; }
})());

function savePrefs(): void {
  try {
    localStorage.setItem('fm_sort', JSON.stringify({ k: sortKey.value, a: sortAsc.value }));
    localStorage.setItem('fm_view', viewMode.value);
  } catch (e) { /* приватный режим — не критично */ }
}

/* ---------- внутренний буфер обмена ---------- */
const clipboard = ref<{ mode: 'cut' | 'copy'; paths: string[] } | null>(null);
const cutPaths = computed<Set<string>>(() =>
  new Set(clipboard.value && clipboard.value.mode === 'cut'
    ? clipboard.value.paths : []));

/* ---------- контекстное меню ---------- */
const ctx = ref<{ open: boolean; x: number; y: number; items: CtxItem[] }>(
  { open: false, x: 0, y: 0, items: [] });
const ctxEl = ref<HTMLElement | null>(null);

/* ---------- дерево слева ---------- */
const tree = ref<TNode[]>([]);

/* ---------- drag&drop ---------- */
const dragOver = ref(''); // путь папки-приёмника либо 'body'
let dragPaths: string[] = [];
let dragDepth = 0;

/* ---------- журнал загрузок ---------- */
const uploadLog = ref<UploadLogItem[]>([]);
let logSeq = 0;

/* ---------- модалки ---------- */
const newDlg = ref(false);
const newMode = ref<'dir' | 'file'>('dir');
const newName = ref('');

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

/* ================= утилиты ================= */

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

/* Имя без завершающего слэша (сервер помечает папки «name/»). */
function baseName(name: string): string {
  return name.replace(/\/$/, '');
}

function extOf(name: string): string {
  const b = baseName(name);
  const i = b.lastIndexOf('.');
  return i > 0 ? b.slice(i + 1).toLowerCase() : '';
}

function joinPath(dir: string, name: string): string {
  return (dir === '/' ? '' : dir) + '/' + name;
}

function parentOf(p: string): string {
  const i = p.lastIndexOf('/');
  if (i <= 0) return '/';
  return p.slice(0, i);
}

const curPathC = computed(() => (d.value ? d.value.path : fmpath.value));

/** Полный путь элемента текущей папки. */
function full(e: FileItem): string {
  return joinPath(curPathC.value, baseName(e.name));
}

/** Полный путь по имени (для буфера/выделения). */
function fullByName(name: string): string {
  return joinPath(curPathC.value, baseName(name));
}

function typeLabel(e: FileItem): string {
  if (e.type === 'dir') return 'Папка';
  if (e.type === 'link') return 'Ссылка';
  const x = extOf(e.name);
  return x ? x.toUpperCase() : 'Файл';
}

/* Иконка по типу/расширению + цветовой класс (иконки из набора UiIcon). */
function icoFor(e: FileItem): string {
  if (e.type === 'dir') return 'folder';
  const x = extOf(e.name);
  if (['zip', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'rar', '7z'].includes(x)) return 'archive';
  if (['sql', 'db', 'sqlite', 'sqlite3'].includes(x)) return 'db';
  if (['html', 'htm'].includes(x)) return 'globe';
  if (['php', 'py', 'sh', 'js', 'mjs', 'pl', 'rb'].includes(x)) return 'term';
  if (['conf', 'ini', 'json', 'yml', 'yaml', 'xml', 'env', 'cnf', 'service', 'timer', 'socket'].includes(x)) return 'gear';
  if (['key', 'pem', 'crt', 'htpasswd'].includes(x)) return 'lock';
  return 'file';
}

function icoClass(e: FileItem): string {
  if (e.type === 'dir') return 'ic-dir';
  const x = extOf(e.name);
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'bmp', 'avif'].includes(x)) return 'ic-img';
  if (['zip', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'rar', '7z'].includes(x)) return 'ic-arch';
  if (['sql', 'db', 'sqlite', 'sqlite3'].includes(x)) return 'ic-db';
  if (['html', 'htm', 'php', 'py', 'sh', 'js', 'mjs', 'pl', 'rb'].includes(x)) return 'ic-code';
  if (['conf', 'ini', 'json', 'yml', 'yaml', 'xml', 'env', 'cnf'].includes(x)) return 'ic-cfg';
  return 'ic-file';
}

const crumbs = computed(() => {
  const p = curPathC.value;
  const parts = p === '/' ? [] : p.split('/').filter(Boolean);
  let acc = '';
  return parts.map((x) => {
    acc += '/' + x;
    return { name: x, path: acc };
  });
});

/* ================= загрузка и навигация ================= */

/* Счётчик запросов списка: устаревший ответ не должен перетирать свежий. */
let loadGen = 0;

async function load(): Promise<void> {
  const gen = ++loadGen;
  loading.value = true;
  loadErr.value = '';
  try {
    const data: DirData = await api('/api/files?path=' + encodeURIComponent(fmpath.value));
    if (gen !== loadGen) return; // пока ждали — путь уже сменился
    d.value = data;
    sel.value = new Set();
    anchor = null;
    syncTree(data.path);
  } catch (e: any) {
    if (gen !== loadGen) return;
    d.value = null;
    loadErr.value = e.message || String(e);
  } finally {
    if (gen === loadGen) loading.value = false;
  }
}

/** Пользовательский переход: пишем историю. */
function go(p: string): void {
  if (curPathC.value && curPathC.value !== p) {
    histBack.value.push(curPathC.value);
    if (histBack.value.length > 100) histBack.value.shift();
  }
  histFwd.value = [];
  navTo(p);
}

/** Служебная навигация (история/обновление после операций) — без записи. */
async function navTo(p: string): Promise<void> {
  fmpath.value = p;
  closeCtx();
  await load();
}

function reload(): void {
  navTo(curPathC.value);
}

function goBack(): void {
  const p = histBack.value.pop();
  if (!p) return;
  if (curPathC.value) histFwd.value.push(curPathC.value);
  navTo(p);
}

function goFwd(): void {
  const p = histFwd.value.pop();
  if (!p) return;
  if (curPathC.value) histBack.value.push(curPathC.value);
  navTo(p);
}

function goUp(): void {
  if (d.value && d.value.parent) go(d.value.parent);
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

/* ================= дерево папок ================= */

const treeRoots = computed<string[]>(() => {
  const arr: string[] = [];
  const push = (p: string): void => {
    if (p && !arr.includes(p)) arr.push(p);
  };
  if (me.demo) {
    push(me.home);
  } else {
    push(me.www_root);
    push(me.home);
  }
  // текущий путь, если он не покрыт ни одним из корней
  const cur = curPathC.value;
  if (cur && !arr.some((r) => cur === r || cur.startsWith(r + '/'))) push(cur);
  return arr;
});

function mkNode(path: string): TNode {
  const parts = path.split('/').filter(Boolean);
  return {
    path,
    name: parts.length ? parts[parts.length - 1] : path || '/',
    open: false, loaded: false, err: '', children: [],
  };
}

/* Пересобираем корни, сохраняя раскрытие/детей существующих узлов. */
watch(treeRoots, (roots) => {
  const old = new Map<string, TNode>();
  const walk = (ns: TNode[]): void => {
    ns.forEach((n) => { old.set(n.path, n); walk(n.children); });
  };
  walk(tree.value);
  tree.value = roots.map((r) => old.get(r) || mkNode(r));
}, { immediate: true });

async function loadChildren(n: TNode): Promise<void> {
  n.err = '';
  try {
    const data: DirData = await api('/api/files?path=' + encodeURIComponent(n.path));
    n.children = data.items
      .filter((e) => e.type === 'dir')
      .map((e) => mkNode(joinPath(data.path, baseName(e.name))));
    n.loaded = true;
  } catch (e: any) {
    n.err = e.message || String(e);
    n.loaded = true;
  }
}

async function toggleNode(n: TNode): Promise<void> {
  n.open = !n.open;
  if (n.open && !n.loaded) await loadChildren(n);
}

/** Клик по имени в дереве: раскрыть и перейти. */
async function openNode(n: TNode): Promise<void> {
  if (!n.loaded) await loadChildren(n);
  n.open = true;
  go(n.path);
}

/** Раскрыть цепочку узлов дерева до текущего пути. */
async function syncTree(path: string): Promise<void> {
  let level = tree.value;
  let rest = path;
  for (let guard = 0; guard < 40; guard++) {
    const n = level.find((x) => rest === x.path || rest.startsWith(x.path + '/'));
    if (!n) break;
    n.open = true;
    if (rest === n.path) break;
    if (!n.loaded) await loadChildren(n);
    if (!n.children.length) break;
    level = n.children;
  }
}

interface FlatNode { n: TNode; depth: number }

function walkNodes(ns: TNode[], depth: number, out: FlatNode[]): void {
  ns.forEach((n) => {
    out.push({ n, depth });
    if (n.open && n.children.length) walkNodes(n.children, depth + 1, out);
  });
}

const flatTree = computed<FlatNode[]>(() => {
  const out: FlatNode[] = [];
  walkNodes(tree.value, 0, out);
  return out;
});

/* ================= список: фильтр и сортировка ================= */

const visible = computed<FileItem[]>(() => {
  let items = d.value ? d.value.items : [];
  const q = filter.value.trim().toLowerCase();
  if (q) items = items.filter((e) => baseName(e.name).toLowerCase().includes(q));
  const k = sortKey.value;
  const dir = sortAsc.value ? 1 : -1;
  return [...items].sort((a, b) => {
    if (a.type === 'dir' && b.type !== 'dir') return -1;
    if (b.type === 'dir' && a.type !== 'dir') return 1;
    let r = 0;
    if (k === 'size') r = (a.size || 0) - (b.size || 0);
    else if (k === 'mtime') r = String(a.mtime || '').localeCompare(String(b.mtime || ''));
    else if (k === 'type') {
      r = extOf(a.name).localeCompare(extOf(b.name)) ||
        baseName(a.name).localeCompare(baseName(b.name), undefined, { numeric: true });
    } else {
      r = baseName(a.name).localeCompare(baseName(b.name), undefined, { numeric: true });
    }
    return r * dir;
  });
});

function sortBy(k: string): void {
  if (sortKey.value === k) sortAsc.value = !sortAsc.value;
  else { sortKey.value = k; sortAsc.value = true; }
  savePrefs();
}

function arrowFor(k: string): string {
  if (sortKey.value !== k) return '';
  return sortAsc.value ? '↑' : '↓';
}

const sortOptions = [
  { value: 'name', label: 'по имени' },
  { value: 'size', label: 'по размеру' },
  { value: 'mtime', label: 'по дате' },
  { value: 'type', label: 'по типу' },
];

function onSortSelect(v: string | number): void {
  sortKey.value = String(v);
  sortAsc.value = true;
  savePrefs();
}

/* ================= выделение ================= */

function clickRow(e: MouseEvent, item: FileItem): void {
  if (e.shiftKey && anchor) {
    const names = visible.value.map((x) => x.name);
    const i1 = names.indexOf(anchor);
    const i2 = names.indexOf(item.name);
    if (i1 >= 0 && i2 >= 0) {
      const [a, b] = i1 < i2 ? [i1, i2] : [i2, i1];
      sel.value = new Set(names.slice(a, b + 1));
      return;
    }
  }
  if (e.ctrlKey || e.metaKey) {
    const s = new Set(sel.value);
    if (s.has(item.name)) s.delete(item.name); else s.add(item.name);
    sel.value = s;
    anchor = item.name;
    return;
  }
  sel.value = new Set([item.name]);
  anchor = item.name;
}

function selItems(): FileItem[] {
  if (!d.value) return [];
  const m = new Map<string, FileItem>();
  d.value.items.forEach((e) => m.set(e.name, e));
  return Array.from(sel.value)
    .map((n) => m.get(n))
    .filter((e): e is FileItem => !!e);
}

function selFullPaths(): string[] {
  return Array.from(sel.value).map((n) => fullByName(n));
}

function isCut(e: FileItem): boolean {
  return cutPaths.value.has(full(e));
}

/** Клик по пустому месту списка — сброс выделения. */
function onBodyClick(e: MouseEvent): void {
  const t = e.target as HTMLElement;
  if (!t.closest('.fm-row') && !t.closest('.fm-tile')) {
    sel.value = new Set();
    anchor = null;
  }
}

/* ================= открытие / редактор ================= */

function openItem(e: FileItem): void {
  if (e.type === 'dir') go(full(e));
  else if (e.editable) edit(full(e));
  else download(e);
}

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
    reload();
  } catch (e) { toastErr(e); }
}

/* ================= создание / переименование / права ================= */

function newDlgOpen(mode: 'dir' | 'file'): void {
  newMode.value = mode;
  newName.value = '';
  newDlg.value = true;
}

async function newDo(): Promise<void> {
  const name = newName.value.trim();
  if (!name) return;
  try {
    if (newMode.value === 'dir') {
      const r = await api('/api/files/mkdir', { method: 'POST',
        body: { path: joinPath(curPathC.value, name) } });
      toast(r.message);
    } else {
      const r = await api('/api/files/save', { method: 'POST',
        body: { path: joinPath(curPathC.value, name), content: '' } });
      toast(r.message);
    }
    newDlg.value = false;
    reload();
  } catch (e) { toastErr(e); }
}

function renameOpen(path: string, name: string): void {
  renamePath.value = path;
  renameName.value = baseName(name);
  renameDlg.value = true;
}

async function renameDo(): Promise<void> {
  try {
    const r = await api('/api/files/rename', { method: 'POST',
      body: { path: renamePath.value, new_name: renameName.value } });
    toast(r.message);
    renameDlg.value = false;
    reload();
  } catch (err) { toastErr(err); }
}

function chmodOpen(path: string, e?: FileItem): void {
  chmodPath.value = path;
  chmodOctal.value = (e && e.octal) ? String(e.octal) : symToOctal(e ? (e.perms || '') : '');
  chmodDlg.value = true;
}

async function chmodDo(): Promise<void> {
  const octal = chmodOctal.value.trim();
  // валидация: 1–4 цифры 0–7 (папкам разрешают и setgid 2xxx/4xxx)
  if (!/^[0-7]{1,4}$/.test(octal)) {
    toastErr(new Error('неверные права: нужны 3–4 восьмеричные цифры (например 644 или 755)'));
    return;
  }
  try {
    const r = await api('/api/files/chmod', { method: 'POST',
      body: { path: chmodPath.value, octal } });
    toast(r.message);
    chmodDlg.value = false;
    reload();
  } catch (err) { toastErr(err); }
}

/* ================= удаление / скачивание ================= */

function delSelected(): void {
  const items = selItems();
  if (!items.length) return;
  const names = items.map((e) => baseName(e.name));
  const list = names.slice(0, 5).join(', ') + (names.length > 5 ? ' …' : '');
  const what = names.length === 1 ? '«' + names[0] + '»' : names.length + ' объектов';
  confirmDlg('Удалить', 'Удалить ' + what + ': ' + list + '?', async () => {
    try {
      const r = await api('/api/files/delete', { method: 'POST',
        body: { paths: items.map((e) => full(e)) } });
      toast(r.message);
      reload();
    } catch (err) { toastErr(err); }
  });
}

async function download(e: FileItem): Promise<void> {
  try {
    await downloadFile('/api/files/download?path=' + encodeURIComponent(full(e)),
                       baseName(e.name));
  } catch (err) { toastErr(err); }
}

/** Скачивание выбранных: одиночный файл — как есть, иначе zip во
 *  временное имя + скачивание архива (потом тихо удаляется). */
async function downloadSelected(): Promise<void> {
  const items = selItems();
  if (!items.length) { toastErr(new Error('ничего не выбрано')); return; }
  if (items.length === 1 && items[0].type !== 'dir') return download(items[0]);
  const dest = joinPath(curPathC.value, '.hp-dl-' + Date.now() + '.zip');
  try {
    const r = await api('/api/files/zip', { method: 'POST',
      body: { paths: selFullPaths(), dest } });
    const zpath: string = r.dest || dest;
    await downloadFile('/api/files/download?path=' + encodeURIComponent(zpath),
                       baseName(zpath));
    api('/api/files/delete', { method: 'POST', body: { paths: [zpath] } }).catch(() => { /* временный архив */ });
  } catch (err) { toastErr(err); }
}

/* ================= архивы ================= */

async function extract(e: FileItem): Promise<void> {
  try {
    const r = await api('/api/files/extract', { method: 'POST',
      body: { path: full(e) } });
    toast(r.message);
    reload();
  } catch (err) { toastErr(err); }
}

async function zipSelected(): Promise<void> {
  const items = selItems();
  if (!items.length) return;
  const dest = items.length === 1
    ? full(items[0]) + '.zip'
    : joinPath(curPathC.value, 'archive-' + Date.now() + '.zip');
  try {
    const r = await api('/api/files/zip', { method: 'POST',
      body: { paths: selFullPaths(), dest } });
    toast(r.message);
    reload();
  } catch (err) { toastErr(err); }
}

/* ================= буфер обмена (внутренний) ================= */

function clipCut(): void {
  const paths = selFullPaths();
  if (!paths.length) return;
  clipboard.value = { mode: 'cut', paths };
  toast('к вырезанию: ' + paths.length);
}

function clipCopy(): void {
  const paths = selFullPaths();
  if (!paths.length) return;
  clipboard.value = { mode: 'copy', paths };
  toast('к копированию: ' + paths.length);
}

async function paste(): Promise<void> {
  const cb = clipboard.value;
  if (!cb || !cb.paths.length) return;
  const dest = curPathC.value;
  const paths = cb.paths.filter((p) => {
    if (p === dest || dest.startsWith(p + '/')) {
      toastErr(new Error('нельзя вставить папку внутрь себя: ' + p));
      return false;
    }
    if (parentOf(p) === dest && cb.mode === 'cut') return false; // уже здесь
    return true;
  });
  if (!paths.length) return;
  try {
    const r = await api(cb.mode === 'cut' ? '/api/files/move' : '/api/files/copy',
      { method: 'POST', body: { paths, dest } });
    toast(r.message);
    if (cb.mode === 'cut') clipboard.value = null;
    reload();
  } catch (e) { toastErr(e); }
}

/* ================= перемещение (drag&drop / move) ================= */

async function doMove(paths: string[], dest: string): Promise<void> {
  const ok = paths.filter((p) => p !== dest && !dest.startsWith(p + '/'));
  if (!ok.length) return;
  try {
    const r = await api('/api/files/move', { method: 'POST',
      body: { paths: ok, dest } });
    toast(r.message);
    reload();
  } catch (e) { toastErr(e); }
}

/* ================= загрузка файлов ================= */

async function uploadFiles(files: File[]): Promise<void> {
  if (!files.length) return;
  let okc = 0;
  // фиксируем папку-приёмник ДО цикла: пользователь может уйти в другую
  // папку, пока файлы грузятся — тогда они уедут не туда
  const dest = curPathC.value;
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    try {
      await apiForm('/api/files/upload?dest=' + encodeURIComponent(dest), fd);
      okc++;
      uploadLog.value.push({ id: ++logSeq, name: f.name, ok: true, msg: '' });
    } catch (e: any) {
      uploadLog.value.push({ id: ++logSeq, name: f.name, ok: false,
        msg: e.message || String(e) });
    }
  }
  uploadLog.value = uploadLog.value.slice(-30);
  if (okc === files.length) toast('загружено файлов: ' + okc);
  else toastErr(new Error('загружено ' + okc + ' из ' + files.length +
    ' — подробности в журнале загрузок'));
  reload();
}

async function onUploadInput(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement;
  if (input.files && input.files.length) {
    await uploadFiles(Array.from(input.files));
  }
  input.value = '';
}

/* ================= drag&drop ================= */

function internalDrag(e: DragEvent): boolean {
  return !!(e.dataTransfer &&
    Array.from(e.dataTransfer.types).includes('application/x-fm'));
}

function hasFiles(e: DragEvent): boolean {
  return !!(e.dataTransfer &&
    Array.from(e.dataTransfer.types).includes('Files'));
}

function onDragStart(e: DragEvent, item: FileItem): void {
  const paths = (sel.value.has(item.name) && sel.value.size)
    ? selFullPaths() : [full(item)];
  dragPaths = paths;
  if (e.dataTransfer) {
    e.dataTransfer.setData('application/x-fm', '1');
    e.dataTransfer.setData('text/plain', paths.join('\n'));
    e.dataTransfer.effectAllowed = 'copyMove';
  }
}

function onDragEnd(): void {
  dragPaths = [];
  dragOver.value = '';
  dragDepth = 0;
}

function onDragOverDir(e: DragEvent, item: FileItem): void {
  if (item.type !== 'dir' || !internalDrag(e)) return;
  const dest = full(item);
  if (dragPaths.some((p) => p === dest || dest.startsWith(p + '/'))) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
  dragOver.value = dest;
}

function onDragLeaveDir(e: DragEvent, item: FileItem): void {
  if (dragOver.value === full(item)) dragOver.value = '';
}

function onDropDir(e: DragEvent, item: FileItem): void {
  if (item.type !== 'dir') return;
  e.preventDefault();
  const dest = full(item);
  dragOver.value = '';
  if (dragPaths.length) doMove(dragPaths, dest);
  dragPaths = [];
}

/* Перенос строк на папку в левом дереве. */
function onDragOverTree(e: DragEvent, n: TNode): void {
  if (!internalDrag(e)) return;
  if (dragPaths.some((p) => p === n.path || n.path.startsWith(p + '/'))) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
  dragOver.value = n.path;
}

function onDragLeaveTree(e: DragEvent, n: TNode): void {
  if (dragOver.value === n.path) dragOver.value = '';
}

async function onDropTree(e: DragEvent, n: TNode): Promise<void> {
  e.preventDefault();
  dragOver.value = '';
  if (dragPaths.length) {
    doMove(dragPaths, n.path);
    n.open = true;
    if (!n.loaded) await loadChildren(n);
  }
  dragPaths = [];
}

/* Внешние файлы с компьютера: подсветка области и загрузка. */
function onBodyDragOver(e: DragEvent): void {
  if (!hasFiles(e)) return;
  e.preventDefault();
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
  dragOver.value = 'body';
}

function onBodyDragEnter(e: DragEvent): void {
  if (hasFiles(e)) dragDepth++;
}

function onBodyDragLeave(e: DragEvent): void {
  if (!hasFiles(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) dragOver.value = '';
}

async function onBodyDrop(e: DragEvent): Promise<void> {
  dragDepth = 0;
  dragOver.value = '';
  if (!hasFiles(e)) return;
  e.preventDefault();
  const files = Array.from(e.dataTransfer ? e.dataTransfer.files : []);
  await uploadFiles(files);
}

/* ================= контекстное меню ================= */

function closeCtx(): void {
  if (ctx.value.open) ctx.value.open = false;
}

function showCtx(ev: MouseEvent, item: FileItem | null): void {
  ev.preventDefault();
  if (item) {
    if (!sel.value.has(item.name)) {
      sel.value = new Set([item.name]);
      anchor = item.name;
    }
  } else {
    sel.value = new Set();
    anchor = null;
  }
  const items: CtxItem[] = [];
  if (item) {
    const multi = sel.value.size > 1;
    const n = sel.value.size;
    if (!multi && item.type === 'dir') {
      items.push({ label: 'Открыть', icon: 'ext', act: () => openItem(item) });
    }
    if (!multi && item.type !== 'dir' && item.editable) {
      items.push({ label: 'Редактировать', icon: 'edit', act: () => edit(full(item)) });
    }
    if (!multi && item.type !== 'dir') {
      items.push({ label: 'Скачать', icon: 'down', act: () => download(item) });
    }
    if (!multi) {
      items.push({ label: 'Копировать путь', icon: 'file',
        act: () => { copyText(full(item)); toast('путь скопирован'); } });
    }
    items.push({ label: '', sep: true, act: () => { /* разделитель */ } });
    items.push({ label: multi ? 'Вырезать (' + n + ')' : 'Вырезать',
      act: () => clipCut() });
    items.push({ label: multi ? 'Копировать (' + n + ')' : 'Копировать',
      act: () => clipCopy() });
    if (!multi && item.type !== 'dir') {
      items.push({ label: 'Переименовать', icon: 'edit',
        act: () => renameOpen(full(item), item.name) });
    }
    items.push({ label: multi ? 'Архивировать в zip (' + n + ')' : 'Архивировать в zip',
      icon: 'archive', act: () => zipSelected() });
    if (!multi && isArchive(item.name)) {
      items.push({ label: 'Распаковать', icon: 'archive', act: () => extract(item) });
    }
    if (!multi) {
      items.push({ label: 'Права (chmod)', icon: 'wrench',
        act: () => chmodOpen(full(item), item) });
    }
    items.push({ label: '', sep: true, act: () => { /* разделитель */ } });
    items.push({ label: multi ? 'Удалить (' + n + ')' : 'Удалить',
      icon: 'trash', danger: true, act: () => delSelected() });
  } else {
    items.push({ label: 'Обновить', icon: 'refresh', act: () => reload() });
    items.push({ label: 'Новая папка', icon: 'folder', act: () => newDlgOpen('dir') });
    items.push({ label: 'Новый файл', icon: 'file', act: () => newDlgOpen('file') });
    items.push({ label: 'Загрузить файлы', icon: 'up', act: () => uploadEl.value?.click() });
    if (clipboard.value && clipboard.value.paths.length) {
      items.push({ label: '', sep: true, act: () => { /* разделитель */ } });
      items.push({ label: 'Вставить (' + clipboard.value.paths.length + ')',
        icon: 'down', act: () => paste() });
    }
    items.push({ label: 'Выделить всё', act: () =>
      { sel.value = new Set(visible.value.map((x) => x.name)); } });
  }
  ctx.value = { open: true, x: ev.clientX, y: ev.clientY, items };
  nextTick(clampCtx);
}

/** Не давать меню выходить за край окна. */
function clampCtx(): void {
  const el = ctxEl.value;
  if (!el) return;
  const r = el.getBoundingClientRect();
  let x = ctx.value.x;
  let y = ctx.value.y;
  if (x + r.width > window.innerWidth - 6) x = window.innerWidth - r.width - 6;
  if (y + r.height > window.innerHeight - 6) y = window.innerHeight - r.height - 6;
  ctx.value.x = Math.max(6, x);
  ctx.value.y = Math.max(6, y);
}

function onDocClick(e: MouseEvent): void {
  if (ctx.value.open && ctxEl.value &&
      !ctxEl.value.contains(e.target as Node)) closeCtx();
}

/* ================= клавиатура ================= */

function onKey(e: KeyboardEvent): void {
  if (newDlg.value || editDlg.value || renameDlg.value || chmodDlg.value) return;
  const t = e.target as HTMLElement | null;
  const inField = !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' ||
    t.isContentEditable);
  if (e.key === 'Escape') {
    if (ctx.value.open) { closeCtx(); return; }
    if (!inField && sel.value.size) { sel.value = new Set(); anchor = null; }
    return;
  }
  if (inField) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault();
    sel.value = new Set(visible.value.map((x) => x.name));
  } else if (e.key === 'Delete' && sel.value.size) {
    delSelected();
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKey);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick);
  document.removeEventListener('keydown', onKey);
});
</script>

<template>
  <div v-table class="fm">
    <aside class="fm-side">
      <div class="fm-side-h">Папки</div>
      <div class="fm-tree">
        <template v-for="f in flatTree" :key="f.n.path">
          <div class="fm-tree-i"
               :class="{ cur: f.n.path === curPathC, drop: dragOver === f.n.path }"
               :style="{ paddingLeft: (6 + f.depth * 14) + 'px' }"
               @dragover="onDragOverTree($event, f.n)"
               @dragleave="onDragLeaveTree($event, f.n)"
               @drop="onDropTree($event, f.n)">
            <button class="fm-tree-tgl" :title="f.n.open ? 'Свернуть' : 'Развернуть'"
                    @click="toggleNode(f.n)">{{ f.n.open ? '▾' : '▸' }}</button>
            <span class="fm-tree-name" @click="openNode(f.n)">
              <span class="fm-ico ic-dir"><UiIcon name="folder" :size="14" /></span>
              {{ f.n.name }}
            </span>
          </div>
          <div v-if="f.n.err" class="fm-tree-err" :style="{ marginLeft: (30 + f.depth * 14) + 'px' }">
            {{ f.n.err }}
          </div>
        </template>
      </div>
    </aside>

    <div class="fm-main">
      <div class="fm-toolbar">
        <div class="fm-tb-row">
          <button class="btn icon sm" :disabled="!histBack.length"
                  title="Назад" @click="goBack()">←</button>
          <button class="btn icon sm" :disabled="!histFwd.length"
                  title="Вперёд" @click="goFwd()">→</button>
          <button class="btn icon sm" :disabled="!d || !d.parent"
                  title="Вверх" @click="goUp()">↑</button>
          <button class="btn icon sm" title="Обновить" @click="reload()">
            <UiIcon name="refresh" :size="14" />
          </button>
          <div class="bread fm-crumbs">
            <template v-for="(c, i) in crumbs" :key="c.path">
              <span v-if="i" class="sep">›</span>
              <button @click="go(c.path)">{{ c.name }}</button>
            </template>
            <span v-if="!crumbs.length" class="cur">/</span>
          </div>
          <input v-model="filter" type="text" class="fm-search"
                 placeholder="поиск по имени…">
        </div>
        <div class="fm-tb-row">
          <button class="btn sm" @click="newDlgOpen('dir')">
            <UiIcon name="folder" :size="14" /> Папка</button>
          <button class="btn sm" @click="newDlgOpen('file')">
            <UiIcon name="plus" :size="14" /> Файл</button>
          <button class="btn sm" @click="uploadEl?.click()">
            <UiIcon name="up" :size="14" /> Загрузить</button>
          <input ref="uploadEl" type="file" multiple class="hidden" @change="onUploadInput">
          <button class="btn sm" :disabled="!sel.size" @click="downloadSelected()">
            <UiIcon name="down" :size="14" /> Скачать</button>
          <button class="btn sm" :disabled="!clipboard" @click="paste()">
            <UiIcon name="check" :size="14" /> Вставить</button>
          <span class="fm-tb-sp"></span>
          <button class="btn sm" @click="zipSelected()" :disabled="!sel.size">
            <UiIcon name="archive" :size="14" /> В zip</button>
          <button class="btn sm" :title="sortAsc ? 'по возрастанию' : 'по убыванию'"
                  @click="sortAsc = !sortAsc; savePrefs()">
            {{ sortAsc ? '↑' : '↓' }}</button>
          <div class="uiselect fm-sort">
            <UiSelect :model-value="sortKey" :options="sortOptions"
                      @update:model-value="onSortSelect" />
          </div>
          <div class="fm-viewbtns" role="group" aria-label="Вид">
            <button :class="{ on: viewMode === 'list' }" title="Список"
                    @click="viewMode = 'list'; savePrefs()">☰</button>
            <button :class="{ on: viewMode === 'icons' }" title="Крупные значки"
                    @click="viewMode = 'icons'; savePrefs()">▦</button>
          </div>
        </div>
      </div>

      <div class="card fm-body"
           :class="{ drop: dragOver === 'body' }"
           @click="onBodyClick($event)"
           @contextmenu="showCtx($event, null)"
           @dragover="onBodyDragOver($event)"
           @dragenter="onBodyDragEnter($event)"
           @dragleave="onBodyDragLeave($event)"
           @drop="onBodyDrop($event)">
        <div v-if="loading && !d" class="empty">Загрузка…</div>
        <div v-else-if="loadErr" class="notice err">{{ loadErr }}</div>
        <template v-else-if="d">
          <!-- вид: список -->
          <div v-if="viewMode === 'list'" class="twrap">
            <table class="fm-table">
              <thead>
                <tr>
                  <th class="fm-th-click" @click="sortBy('name')">Имя {{ arrowFor('name') }}</th>
                  <th class="fm-th-click" @click="sortBy('size')">Размер {{ arrowFor('size') }}</th>
                  <th class="fm-th-click" @click="sortBy('mtime')">Изменён {{ arrowFor('mtime') }}</th>
                  <th class="fm-th-click" @click="sortBy('type')">Тип {{ arrowFor('type') }}</th>
                  <th>Права</th>
                  <th>Владелец</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="d.parent" class="fm-uprow" @click.stop="goUp()">
                  <td colspan="6"><span class="muted">↑ ..</span></td>
                </tr>
                <tr v-for="e in visible" :key="e.name" class="fm-row"
                    :class="{ sel: sel.has(e.name), cut: isCut(e), drop: dragOver === full(e) }"
                    draggable="true"
                    @click="clickRow($event, e)"
                    @dblclick="openItem(e)"
                    @contextmenu.stop="showCtx($event, e)"
                    @dragstart="onDragStart($event, e)"
                    @dragend="onDragEnd"
                    @dragover="onDragOverDir($event, e)"
                    @dragleave="onDragLeaveDir($event, e)"
                    @drop="onDropDir($event, e)">
                  <td class="fm-name">
                    <span class="fm-ico" :class="icoClass(e)">
                      <UiIcon :name="icoFor(e)" :size="16" />
                    </span>
                    <span class="mono fm-nm">{{ baseName(e.name) }}</span>
                    <span v-if="e.type === 'link'" class="faint mono">→ {{ e.target }}</span>
                  </td>
                  <td>{{ e.type === 'dir' ? '—' : fmtSize(e.size) }}</td>
                  <td class="muted">{{ e.mtime }}</td>
                  <td class="muted">{{ typeLabel(e) }}</td>
                  <td class="mono">{{ e.perms }}</td>
                  <td class="muted">{{ e.owner }}</td>
                </tr>
                <tr v-if="!visible.length">
                  <td colspan="6"><div class="empty">Папка пуста</div></td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- вид: крупные значки -->
          <div v-else class="fm-grid">
            <div v-for="e in visible" :key="e.name" class="fm-tile"
                 :class="{ sel: sel.has(e.name), cut: isCut(e), drop: dragOver === full(e) }"
                 :title="baseName(e.name)"
                 draggable="true"
                 @click="clickRow($event, e)"
                 @dblclick="openItem(e)"
                 @contextmenu.stop="showCtx($event, e)"
                 @dragstart="onDragStart($event, e)"
                 @dragend="onDragEnd"
                 @dragover="onDragOverDir($event, e)"
                 @dragleave="onDragLeaveDir($event, e)"
                 @drop="onDropDir($event, e)">
              <span class="fm-tile-ico" :class="icoClass(e)">
                <UiIcon :name="icoFor(e)" :size="30" />
              </span>
              <span class="fm-tile-name">{{ baseName(e.name) }}</span>
            </div>
            <div v-if="!visible.length" class="empty fm-grid-empty">Папка пуста</div>
          </div>
        </template>
      </div>

      <!-- статусная строка -->
      <div v-if="d" class="fm-status">
        показано {{ visible.length }} из {{ d.items.length }} объектов
        · выбрано {{ sel.size }}
        · <span class="mono">{{ curPathC }}</span>
      </div>

      <!-- журнал загрузок -->
      <div v-if="uploadLog.length" class="card fm-log">
        <div class="fm-log-h">
          Загрузки
          <button class="btn sm icon" title="Очистить" @click="uploadLog = []">
            <UiIcon name="x" :size="13" />
          </button>
        </div>
        <div v-for="l in uploadLog" :key="l.id" class="fm-log-i"
             :class="l.ok ? 'ok' : 'err'">
          <span class="mono">{{ l.name }}</span> — {{ l.ok ? 'ок' : l.msg }}
        </div>
      </div>
    </div>

    <!-- контекстное меню -->
    <div v-if="ctx.open" ref="ctxEl" class="fm-ctx"
         :style="{ left: ctx.x + 'px', top: ctx.y + 'px' }">
      <template v-for="(it, i) in ctx.items" :key="i">
        <div v-if="it.sep" class="fm-ctx-sep"></div>
        <button v-else class="fm-ctx-i" :class="{ danger: it.danger }"
                @click="it.act(); closeCtx()">
          <span v-if="it.icon" class="fm-ctx-ico"><UiIcon :name="it.icon" :size="14" /></span>
          {{ it.label }}
        </button>
      </template>
    </div>

    <!-- новая папка / файл -->
    <AppModal :open="newDlg" :title="newMode === 'dir' ? 'Новая папка' : 'Новый файл'"
              @close="newDlg = false">
      <div class="field">
        <label>Имя {{ newMode === 'dir' ? 'папки' : 'файла' }}</label>
        <input v-model="newName" type="text" @keyup.enter="newDo()">
      </div>
      <template #footer>
        <button class="btn primary" @click="newDo()">Создать</button>
        <button class="btn" @click="newDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- редактор -->
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

    <!-- переименование -->
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

    <!-- права -->
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

<style scoped>
/* ================= каркас проводника ================= */
.fm{display:flex;gap:14px;align-items:flex-start}
.fm-side{width:230px;flex-shrink:0;background:var(--panel);border:1px solid var(--border);
  border-radius:var(--r-lg);box-shadow:var(--shadow);overflow:hidden}
.fm-side-h{padding:11px 13px;font-size:11.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--border-2)}
.fm-tree{padding:6px;max-height:60vh;overflow-y:auto}
.fm-tree-i{display:flex;align-items:center;gap:2px;border-radius:var(--r);
  cursor:pointer;line-height:1.3;padding:2px 4px}
.fm-tree-i:hover{background:var(--hover)}
.fm-tree-i.cur{background:var(--sel)}
.fm-tree-i.cur .fm-tree-name{color:var(--primary);font-weight:600}
.fm-tree-i.drop{outline:2px solid var(--primary);outline-offset:-2px}
.fm-tree-tgl{background:none;border:0;color:var(--faint);font-size:11px;width:16px;
  padding:0;cursor:pointer;flex-shrink:0}
.fm-tree-tgl:hover{color:var(--primary)}
.fm-tree-name{display:flex;align-items:center;gap:6px;flex:1;min-width:0;
  font-size:13px;padding:4px 4px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;word-break:break-all}
.fm-tree-err{font-size:11px;color:var(--err);padding:2px 0 4px}

.fm-main{flex:1;min-width:0}

/* ================= панель инструментов ================= */
.fm-toolbar{display:flex;flex-direction:column;gap:8px;margin-bottom:12px}
.fm-tb-row{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.fm-crumbs{flex:1;min-width:160px;overflow:hidden}
.fm-crumbs button{word-break:break-all}
.fm-search{width:200px;padding:7px 11px;border:1px solid var(--border);
  border-radius:var(--r-md);background:var(--input);color:var(--text);font-size:13px}
.fm-search:focus{outline:none;border-color:var(--primary)}
.fm-tb-sp{flex:1}
.fm-sort{width:150px}
.fm-viewbtns{display:inline-flex;border:1px solid var(--border);border-radius:var(--r);
  overflow:hidden}
.fm-viewbtns button{background:var(--panel);border:0;color:var(--muted);font-size:13px;
  padding:6px 10px;cursor:pointer;line-height:1}
.fm-viewbtns button+button{border-left:1px solid var(--border)}
.fm-viewbtns button:hover{background:var(--hover)}
.fm-viewbtns button.on{background:var(--sel);color:var(--primary);font-weight:700}

/* ================= область списка ================= */
.fm-body{padding:6px;min-height:260px;transition:outline .1s}
.fm-body.drop{outline:2px dashed var(--primary);outline-offset:-4px;
  background:var(--info-s)}
.fm-table{width:100%}
.fm-th-click{cursor:pointer;user-select:none;white-space:nowrap}
.fm-th-click:hover{color:var(--primary)}
.fm-table th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);text-align:left;padding:8px 9px;border-bottom:1px solid var(--border)}
.fm-table td{padding:7px 9px;border-bottom:1px solid var(--border-2);font-size:13px;
  vertical-align:middle}
.fm-row{cursor:default;user-select:none}
.fm-row:hover{background:var(--hover)}
.fm-row.sel{background:var(--sel)}
.fm-row.cut{opacity:.55}
.fm-row.drop{outline:2px solid var(--primary);outline-offset:-2px}
.fm-uprow{cursor:pointer}
.fm-uprow:hover{background:var(--hover)}
.fm-name{display:flex;align-items:center;gap:8px;min-width:0;max-width:420px}
.fm-nm{word-break:break-all}
.fm-ico{display:inline-flex;flex-shrink:0}
.fm-ico.ic-dir{color:var(--primary)}
.fm-ico.ic-img{color:var(--ok-d)}
.fm-ico.ic-arch{color:var(--warn)}
.fm-ico.ic-db{color:var(--info)}
.fm-ico.ic-code{color:#b3569d}
.fm-ico.ic-cfg{color:var(--muted)}
.fm-ico.ic-file{color:var(--faint)}

/* вид: крупные значки */
.fm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(108px,1fr));gap:8px;
  padding:6px}
.fm-grid-empty{grid-column:1/-1}
.fm-tile{display:flex;flex-direction:column;align-items:center;gap:7px;padding:12px 6px 9px;
  border:1px solid transparent;border-radius:var(--r-md);cursor:default;user-select:none;
  text-align:center}
.fm-tile:hover{background:var(--hover)}
.fm-tile.sel{background:var(--sel);border-color:var(--primary)}
.fm-tile.cut{opacity:.55}
.fm-tile.drop{outline:2px solid var(--primary);outline-offset:-2px}
.fm-tile-ico{display:flex}
.fm-tile-ico.ic-dir{color:var(--primary)}
.fm-tile-ico.ic-img{color:var(--ok-d)}
.fm-tile-ico.ic-arch{color:var(--warn)}
.fm-tile-ico.ic-db{color:var(--info)}
.fm-tile-ico.ic-code{color:#b3569d}
.fm-tile-ico.ic-cfg{color:var(--muted)}
.fm-tile-ico.ic-file{color:var(--faint)}
.fm-tile-name{font-size:12px;line-height:1.3;word-break:break-all;max-height:3.9em;
  overflow:hidden}

/* ================= статусная строка / журнал ================= */
.fm-status{margin-top:10px;padding:7px 12px;border:1px solid var(--border);
  border-radius:var(--r-md);background:var(--panel);font-size:12.5px;color:var(--muted);
  display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.fm-log{margin-top:10px;padding:10px 12px}
.fm-log-h{display:flex;align-items:center;justify-content:space-between;font-weight:600;
  font-size:13px;margin-bottom:6px}
.fm-log-i{font-size:12.5px;padding:2px 0;word-break:break-all}
.fm-log-i.ok{color:var(--ok-d)}
.fm-log-i.err{color:var(--err)}

/* ================= контекстное меню ================= */
.fm-ctx{position:fixed;z-index:90;min-width:210px;background:var(--panel);
  border:1px solid var(--border);border-radius:var(--r-md);box-shadow:var(--shadow-lg);
  padding:4px;display:flex;flex-direction:column}
.fm-ctx-i{display:flex;align-items:center;gap:9px;background:none;border:0;
  color:var(--text);font:inherit;font-size:13px;text-align:left;padding:7px 10px;
  border-radius:var(--r);cursor:pointer;white-space:nowrap}
.fm-ctx-i:hover{background:var(--hover)}
.fm-ctx-i.danger{color:var(--err)}
.fm-ctx-i.danger:hover{background:var(--err-s)}
.fm-ctx-ico{display:inline-flex;color:var(--muted)}
.fm-ctx-i.danger .fm-ctx-ico{color:var(--err)}
.fm-ctx-sep{height:1px;background:var(--border-2);margin:3px 6px}

/* ================= мобильная адаптация ================= */
@media (max-width:860px){
  .fm{flex-direction:column}
  .fm-side{width:100%}
  .fm-tree{max-height:180px}
  .fm-search{width:150px;flex:1}
  .fm-name{max-width:none}
  .fm-ctx{min-width:180px}
}
</style>
