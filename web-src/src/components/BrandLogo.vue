<script setup lang="ts">
/* Брендовый логотип службы: <BrandLogo brand="nginx" :size="18" />
   Если для бренда есть SVG в /logos/ — рисуем его, иначе feather-иконку. */
import { computed } from 'vue';
import { brandFor } from '../lib/brands';
import UiIcon from './UiIcon.vue';

const props = withDefaults(defineProps<{
  brand: string;
  size?: number;
  fallback?: string;
}>(), { size: 18, fallback: 'pkg' });

const logo = computed(() => brandFor(props.brand));
const src = computed(() => logo.value ? '/logos/' + logo.value + '.svg' : '');
</script>

<template>
  <img v-if="logo" :src="src" :width="size" :height="size"
       style="flex-shrink:0;vertical-align:middle" alt="" loading="lazy">
  <UiIcon v-else :name="fallback" :size="size" style="flex-shrink:0" />
</template>
