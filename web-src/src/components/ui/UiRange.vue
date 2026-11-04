<script setup lang="ts">
/* Кастомный range-слайдер: скрытый нативный input + закрашенный трек.
   props: min, max, step; слот #suffix — текст справа от значения. */
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  modelValue: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
}>(), { min: 0, max: 100, step: 1, disabled: false });

const emit = defineEmits<{ 'update:modelValue': [number] }>();

const pct = computed(() => {
  const span = props.max - props.min || 1;
  return Math.min(100, Math.max(0,
    ((props.modelValue - props.min) / span) * 100));
});
</script>

<template>
  <label class="uirange" :class="{ dis: disabled }">
    <input type="range" :min="min" :max="max" :step="step"
           :value="modelValue" :disabled="disabled"
           @input="emit('update:modelValue', Number(($event.target as HTMLInputElement).value))">
    <span class="uirange-track">
      <i class="uirange-fill" :style="{ width: pct + '%' }"></i>
      <i class="uirange-thumb" :style="{ left: pct + '%' }"></i>
    </span>
    <span class="uirange-val mono">{{ modelValue }}</span>
    <slot name="suffix"></slot>
  </label>
</template>
