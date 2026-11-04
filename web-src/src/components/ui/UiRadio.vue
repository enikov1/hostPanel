<script setup lang="ts">
/* Кастомный radio. Использовать группой с одинаковым name:
   <UiRadio v-model="x" name="grp" value="a">Вариант A</UiRadio> */
withDefaults(defineProps<{
  modelValue: string | number;
  value: string | number;
  name: string;
  disabled?: boolean;
}>(), { disabled: false });

const emit = defineEmits<{ 'update:modelValue': [string | number] }>();
</script>

<template>
  <label class="uicheck uiradio">
    <input type="radio" :name="name" :value="value" :disabled="disabled"
           :checked="String(modelValue) === String(value)"
           @change="emit('update:modelValue', value)">
    <span class="uicheck-box uiradio-box">
      <i class="uiradio-dot"></i>
    </span>
    <span class="uicheck-txt"><slot /></span>
  </label>
</template>
