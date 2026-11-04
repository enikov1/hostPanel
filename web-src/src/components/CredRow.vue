<script setup lang="ts">
/* Строка «ключ — значение» с кнопкой копирования. */
import { ref } from 'vue';
import { copyText } from '../lib/clipboard';

const props = defineProps<{ k: string; v: string }>();
const btn = ref<HTMLElement | null>(null);
</script>

<template>
  <div class="cred-row">
    <span class="k">{{ k }}</span>
    <span class="v">{{ v }}</span>
    <button ref="btn" class="btn sm icon" type="button" title="Скопировать"
            @click="copyText(v, btn!)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
    </button>
  </div>
</template>
