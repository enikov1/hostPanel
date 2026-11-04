<script setup lang="ts">
/* Кастомный select (замена нативного <select> везде).
   Клавиатура: Enter/Space — открыть, ↑/↓ — выбор, Enter — принять,
   Esc — закрыть. Значения сравниваются как строки (числа тоже подходят). */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

export interface UiSelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

const props = withDefaults(defineProps<{
  modelValue: string | number;
  options: UiSelectOption[];
  placeholder?: string;
  disabled?: boolean;
}>(), { placeholder: '— выберите —', disabled: false });

const emit = defineEmits<{
  'update:modelValue': [string | number];
  change: [string | number];
}>();

const open = ref(false);
const act = ref(0); // активный индекс в списке
const root = ref<HTMLElement | null>(null);
const listEl = ref<HTMLElement | null>(null);

const selIndex = computed(() => {
  const mv = String(props.modelValue);
  for (let i = 0; i < props.options.length; i++)
    if (String(props.options[i].value) === mv) return i;
  return -1;
});

const selLabel = computed(() =>
  selIndex.value >= 0 ? props.options[selIndex.value].label : props.placeholder);

function toggle(): void {
  if (props.disabled) return;
  open.value = !open.value;
  if (open.value) {
    act.value = selIndex.value >= 0 ? selIndex.value : 0;
    scrollAct();
  }
}

function pick(i: number): void {
  const o = props.options[i];
  if (!o || o.disabled) return;
  emit('update:modelValue', o.value);
  emit('change', o.value);
  open.value = false;
}

function move(d: number): void {
  if (!open.value) { toggle(); return; }
  let i = act.value;
  for (let n = 0; n < props.options.length; n++) {
    i = (i + d + props.options.length) % props.options.length;
    if (!props.options[i].disabled) break;
  }
  act.value = i;
  scrollAct();
}

function scrollAct(): void {
  requestAnimationFrame(() => {
    const el = listEl.value?.children[act.value] as HTMLElement | undefined;
    if (el) el.scrollIntoView({ block: 'nearest' });
  });
}

function onKey(e: KeyboardEvent): void {
  if (props.disabled) return;
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    if (open.value) pick(act.value); else toggle();
  } else if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
  else if (e.key === 'Escape') { open.value = false; }
  else if (e.key === 'Home' && open.value) { e.preventDefault(); act.value = 0; scrollAct(); }
  else if (e.key === 'End' && open.value) { e.preventDefault(); act.value = props.options.length - 1; scrollAct(); }
}

function onDocClick(e: MouseEvent): void {
  if (open.value && root.value && !root.value.contains(e.target as Node))
    open.value = false;
}

onMounted(() => { document.addEventListener('click', onDocClick); });
onBeforeUnmount(() => { document.removeEventListener('click', onDocClick); });
</script>

<template>
  <div ref="root" class="uiselect" :class="{ dis: disabled }">
    <button type="button" class="uiselect-btn"
            :disabled="disabled"
            :aria-expanded="open"
            @click="toggle" @keydown="onKey">
      <span class="uiselect-label" :class="{ ph: selIndex < 0 }">{{ selLabel }}</span>
      <svg class="uiselect-arrow" :class="{ open: open }" width="12" height="12" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
    <div v-if="open" class="uiselect-list" ref="listEl" role="listbox">
      <div v-for="(o, i) in options" :key="String(o.value)" role="option"
           class="uiselect-item"
           :class="{ sel: i === selIndex, act: i === act, dis: o.disabled }"
           @click="pick(i)" @mouseenter="act = i">
        {{ o.label }}
      </div>
      <div v-if="!options.length" class="uiselect-item dis">нет вариантов</div>
    </div>
  </div>
</template>
