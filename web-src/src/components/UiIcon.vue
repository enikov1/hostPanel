<script setup lang="ts">
import { computed } from 'vue';
import { ICONS } from '../lib/icons';

const props = withDefaults(defineProps<{ name: string; size?: number }>(), {
  size: 17,
});
const body = computed(() => ICONS[props.name] || '');
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" stroke-width="2" stroke-linecap="round"
       stroke-linejoin="round" v-html="body"></svg>
</template>
