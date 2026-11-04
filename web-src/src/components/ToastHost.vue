<script setup lang="ts">
import { toasts } from '../lib/toast';
</script>

<template>
  <div id="toasts">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">
      <span style="flex:1">{{ t.text }}</span>
    </div>
  </div>
</template>
