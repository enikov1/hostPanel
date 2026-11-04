<script setup lang="ts">
/* Редактор кода с подсветкой (Prism) + поиск по файлу с подсветкой
   совпадений (CSS Custom Highlight API — не ломает Prism-токены),
   навигацией Enter/кнопки и переходом к совпадению.
   Используется всеми редакторами панели: конфиги, файлы, SQL. */
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import Prism from 'prismjs';
import 'prismjs/components/prism-markup-templating';
import 'prismjs/components/prism-php';
import 'prismjs/components/prism-nginx';
import 'prismjs/components/prism-apacheconf';
import 'prismjs/components/prism-ini';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-yaml';
import { esc } from '../lib/format';

const props = withDefaults(defineProps<{
  modelValue: string;
  lang?: string;
}>(), { lang: 'markup' });

const emit = defineEmits<{ 'update:modelValue': [string] }>();

const ta = ref<HTMLTextAreaElement | null>(null);
const hlEl = ref<HTMLElement | null>(null);
const wrap = ref<HTMLElement | null>(null);
const hlCode = ref('');
const gutter = ref('');

/* ---------- поиск ---------- */
const findOpen = ref(false);
const findEl = ref<HTMLInputElement | null>(null);
const query = ref('');
const matchCount = ref(0);
const curMatch = ref(0); // 0-based
const matchLine = ref(0);

interface MatchInfo { start: number; end: number }
let matches: MatchInfo[] = [];

function render(): void {
  const text = ta.value ? ta.value.value : props.modelValue;
  let html: string;
  try {
    html = Prism.highlight(text,
      Prism.languages[props.lang] || Prism.languages.markup, props.lang);
  } catch (e) {
    html = esc(text);
  }
  hlCode.value = html + '\n';
  const n = text.split('\n').length;
  let g = '';
  for (let i = 1; i <= n; i++) g += i + '\n';
  gutter.value = g;
  nextTick(applyFind);
}

function onInput(e: Event): void {
  const v = (e.target as HTMLTextAreaElement).value;
  emit('update:modelValue', v);
  render();
}

function onScroll(): void {
  if (!ta.value) return;
  const hl = ta.value.previousElementSibling as HTMLElement | null;
  if (hl) {
    hl.scrollTop = ta.value.scrollTop;
    hl.scrollLeft = ta.value.scrollLeft;
  }
  const gut = ta.value.closest('.code-wrap')?.querySelector('.code-gutter') as HTMLElement | null;
  if (gut) gut.scrollTop = ta.value.scrollTop;
}

function onKeydown(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
    e.preventDefault();
    openFind();
    return;
  }
  if (e.key === 'Tab' && ta.value) {
    e.preventDefault();
    const t = ta.value;
    const s = t.selectionStart, en = t.selectionEnd;
    t.value = t.value.slice(0, s) + '    ' + t.value.slice(en);
    t.selectionStart = t.selectionEnd = s + 4;
    emit('update:modelValue', t.value);
    render();
  }
}

/* ---------- подсветка совпадений ---------- */
function clearFind(): void {
  matches = [];
  matchCount.value = 0;
  try { (CSS as any).highlights.delete('hp-find'); } catch (e) { /* нет API */ }
  try { (CSS as any).highlights.delete('hp-find-cur'); } catch (e) { /* нет API */ }
}

function applyFind(): void {
  clearFind();
  const q = query.value;
  if (!findOpen.value || !q || !hlEl.value) return;
  const text = ta.value ? ta.value.value : props.modelValue;
  const ql = q.toLowerCase();
  const tl = text.toLowerCase();
  let pos = 0;
  while (matches.length < 2000) {
    const i = tl.indexOf(ql, pos);
    if (i < 0) break;
    matches.push({ start: i, end: i + q.length });
    pos = i + Math.max(1, q.length);
  }
  matchCount.value = matches.length;
  if (!matches.length) return;
  if (curMatch.value >= matches.length) curMatch.value = 0;
  // Ranges по текстовым узлам подсвеченного HTML
  try {
    const walker = document.createTreeWalker(hlEl.value, NodeFilter.SHOW_TEXT);
    const nodes: { node: Text; start: number; end: number }[] = [];
    let off = 0;
    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      nodes.push({ node, start: off, end: off + node.data.length });
      off += node.data.length;
    }
    const all: any[] = [];
    const HighlightCtor = (globalThis as any).Highlight;
    if (!HighlightCtor) return;
    matches.forEach((m, idx) => {
      const r = document.createRange();
      for (const n of nodes) {
        if (m.start >= n.end || m.end <= n.start) continue;
        r.setStart(n.node, Math.max(0, m.start - n.start));
        r.setEnd(n.node, Math.min(n.node.data.length, m.end - n.start));
        break;
      }
      if (idx === curMatch.value) {
        (CSS as any).highlights.set('hp-find-cur', new HighlightCtor(r));
      }
      all.push(r);
    });
    (CSS as any).highlights.set('hp-find', new HighlightCtor(...all));
    scrollToMatch(curMatch.value);
    matchLine.value = text.slice(0, matches[curMatch.value].start)
      .split('\n').length;
  } catch (e) { /* браузер без Highlight API — останется только навигация */ }
}

function scrollToMatch(idx: number): void {
  try {
    const m = matches[idx];
    if (!m || !hlEl.value || !ta.value) return;
    const walker = document.createTreeWalker(hlEl.value, NodeFilter.SHOW_TEXT);
    let off = 0;
    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      const nStart = off, nEnd = off + node.data.length;
      off = nEnd;
      if (m.start >= nEnd || m.end <= nStart) continue;
      const r = document.createRange();
      r.setStart(node, Math.max(0, m.start - nStart));
      r.setEnd(node, Math.min(node.data.length, m.end - nStart));
      const rect = r.getBoundingClientRect();
      const contRect = ta.value.getBoundingClientRect();
      const delta = rect.top - (contRect.top + ta.value.clientHeight / 2);
      if (Math.abs(delta) > 4) ta.value.scrollTop += delta;
      onScroll();
      break;
    }
  } catch (e) { /* noop */ }
}

function goTo(i: number): void {
  if (!matches.length) return;
  curMatch.value = ((i % matches.length) + matches.length) % matches.length;
  applyFind();
}

function openFind(): void {
  findOpen.value = true;
  nextTick(() => { findEl.value?.focus(); findEl.value?.select(); });
}

function closeFind(): void {
  findOpen.value = false;
  query.value = '';
  curMatch.value = 0;
  clearFind();
}

function onFindEnter(ev: KeyboardEvent): void {
  if (ev.shiftKey) goTo(curMatch.value - 1);
  else goTo(curMatch.value + 1);
}

watch(query, () => { curMatch.value = 0; nextTick(applyFind); });
watch(() => props.lang, () => render());

onMounted(() => {
  if (ta.value) ta.value.value = props.modelValue;
  render();
});

onBeforeUnmount(() => { clearFind(); });
</script>

<template>
  <div ref="wrap" class="code-editor-root" @keydown="onKeydown">
    <div v-if="findOpen" class="find-bar">
      <input ref="findEl" v-model="query" type="text" class="mono"
             placeholder="поиск по файлу… (Enter — дальше, Shift+Enter — назад)"
             @keydown.enter="onFindEnter" @keydown.esc="closeFind">
      <span class="faint" style="font-size:12px;white-space:nowrap">
        {{ matchCount ? (curMatch + 1) + ' из ' + matchCount +
          (matchLine ? ' · строка ' + matchLine : '')
          : (query ? 'не найдено' : '') }}</span>
      <button class="btn sm" title="Предыдущее (Shift+Enter)" @click="goTo(curMatch - 1)">↑</button>
      <button class="btn sm" title="Следующее (Enter)" @click="goTo(curMatch + 1)">↓</button>
      <button class="btn sm" title="Закрыть (Esc)" @click="closeFind()">✕</button>
    </div>
    <div class="code-wrap">
      <button v-if="!findOpen" class="btn sm find-toggle"
              title="Поиск по файлу (Ctrl+F)" @click="openFind()">🔍</button>
      <div class="code-gutter mono">{{ gutter }}</div>
      <div class="code-scroll">
        <pre :class="'code-hl language-' + lang"><code :ref="el => hlEl = (el as HTMLElement)" :class="'language-' + lang" v-html="hlCode"></code></pre>
        <textarea ref="ta" class="code-input mono" spellcheck="false" autocomplete="off"
                  @input="onInput" @scroll="onScroll"></textarea>
      </div>
    </div>
  </div>
</template>

<style>
.code-editor-root { position: relative; }
.find-toggle { position: absolute; top: 8px; right: 12px; z-index: 9; }
.find-bar {
  position: absolute; top: 8px; right: 12px; z-index: 10;
  display: flex; align-items: center; gap: 6px;
  background: var(--panel); border: 1px solid var(--primary);
  border-radius: 8px; box-shadow: var(--shadow-lg);
  padding: 6px 8px; width: min(420px, 90%);
}
.find-bar input { padding: 4px 8px; font-size: 12.5px; flex: 1; }
/* подсветка совпадений поверх Prism-токенов (Chromium 105+) */
::highlight(hp-find) {
  background-color: rgba(255, 200, 60, .55);
  color: inherit;
}
::highlight(hp-find-cur) {
  background-color: var(--warn-br);
  color: #141e2d;
}
</style>
