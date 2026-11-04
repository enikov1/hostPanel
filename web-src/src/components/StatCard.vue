<script setup lang="ts">
import UiIcon from './UiIcon.vue';

withDefaults(defineProps<{
  ic: string;
  cls: string;
  val: string | number;
  label: string;
  barPct?: number | null;
  barCls?: string;
}>(), { barPct: null, barCls: '' });
</script>

<template>
  <div class="card" style="margin:0">
    <div class="stat">
      <span class="stat-ico" :class="cls"><UiIcon :name="ic" :size="20" /></span>
      <div style="flex:1">
        <div class="stat-v">{{ val }}</div>
        <div class="stat-l">{{ label }}</div>
        <div v-if="barPct != null" class="bar">
          <i :class="barCls" :style="{ width: barPct + '%' }"></i>
        </div>
      </div>
    </div>
  </div>
</template>
