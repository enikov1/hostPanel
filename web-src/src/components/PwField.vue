<script setup lang="ts">
/* Парольное поле: генерация, показ/скрытие, копирование, индикатор силы. */
import { computed, ref } from 'vue';
import UiIcon from './UiIcon.vue';
import { genPassword, pwStrength } from '../lib/pw';
import { copyText } from '../lib/clipboard';
import { toast } from '../lib/toast';

const props = withDefaults(defineProps<{
  modelValue: string;
  label?: string;
  placeholder?: string;
  gen?: boolean;
  hint?: string;
}>(), {
  label: 'Пароль',
  placeholder: 'минимум 8 символов',
  gen: true,
  hint: 'Придумайте пароль или нажмите кнопку генерации — надёжный пароль создастся сам.',
});

const emit = defineEmits<{ 'update:modelValue': [string] }>();

const show = ref(false);
const strength = computed(() => pwStrength(props.modelValue));

function doGen(): void {
  emit('update:modelValue', genPassword());
  toast('Надёжный пароль сгенерирован — не забудьте скопировать его');
}
</script>

<template>
  <div class="field">
    <label>{{ label }}</label>
    <div class="pw-row">
      <input :type="show ? 'text' : 'password'" class="mono"
             :value="modelValue" :placeholder="placeholder"
             autocomplete="new-password"
             @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)">
      <button v-if="gen" class="btn" type="button" title="Сгенерировать надёжный пароль"
              @click="doGen()"><UiIcon name="refresh" :size="14" /></button>
      <button class="btn" type="button" title="Показать/скрыть"
              @click="show = !show"><UiIcon name="lock" :size="14" /></button>
      <button class="btn" type="button" title="Скопировать"
              @click="copyText(modelValue, $event.currentTarget as HTMLElement)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
    </div>
    <div class="pw-strength">
      <i v-for="i in 3" :key="i" :class="i <= strength ? 'f' + strength : ''"></i>
    </div>
    <div class="faint" style="font-size:11.5px;margin-top:4px">{{ hint }}</div>
  </div>
</template>
