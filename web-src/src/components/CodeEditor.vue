<script setup lang="ts">
/* Редактор кода с подсветкой (Prism): гуттер, слой подсветки, textarea. */
import { ref, watch, onMounted } from 'vue';
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
const hlCode = ref('');
const lines = ref(1);
const gutter = ref('');

function render(): void {
  const text = ta.value ? ta.value.value : props.modelValue;
  let html: string;
  try {
    html = Prism.highlight(text, Prism.languages[props.lang] || Prism.languages.markup, props.lang);
  } catch (e) {
    html = esc(text);
  }
  hlCode.value = html + '\n';
  const n = text.split('\n').length;
  lines.value = n;
  let g = '';
  for (let i = 1; i <= n; i++) g += i + '\n';
  gutter.value = g;
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

watch(() => props.modelValue, (v) => {
  if (ta.value && ta.value.value !== v) { ta.value.value = v; render(); }
});

onMounted(() => { if (ta.value) ta.value.value = props.modelValue; render(); });
</script>

<template>
  <div class="code-wrap">
    <div class="code-gutter mono">{{ gutter }}</div>
    <div class="code-scroll">
      <pre :class="'code-hl language-' + lang"><code :class="'language-' + lang" v-html="hlCode"></code></pre>
      <textarea ref="ta" class="code-input mono" spellcheck="false" autocomplete="off"
                @input="onInput" @scroll="onScroll" @keydown="onKeydown"></textarea>
    </div>
  </div>
</template>
