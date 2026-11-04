<script setup lang="ts">
/* Кастомный checkbox (замена <label class="check"><input type="checkbox">…</label>).
   Внутри — настоящий нативный input (скрытый), поэтому v-model, клавиатура
   и доступность работают как у браузерного. Текст/описание — в слоте. */
withDefaults(defineProps<{
  modelValue: boolean;
  disabled?: boolean;
}>(), { disabled: false });

const emit = defineEmits<{ 'update:modelValue': [boolean] }>();
</script>

<template>
  <label class="uicheck">
    <input type="checkbox" :checked="modelValue" :disabled="disabled"
           @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)">
    <span class="uicheck-box">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </span>
    <span class="uicheck-txt"><slot /></span>
  </label>
</template>
