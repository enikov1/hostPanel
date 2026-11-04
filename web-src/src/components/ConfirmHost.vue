<script setup lang="ts">
import { confirmState, confirmAccept, confirmCancel } from '../lib/confirm';
import AppModal from './AppModal.vue';
</script>

<template>
  <AppModal :open="confirmState.open" :title="confirmState.title"
            @close="confirmCancel()">
    <p style="margin:4px 0 6px">{{ confirmState.text }}</p>
    <template #footer>
      <button class="btn" :class="confirmState.danger ? 'danger' : 'primary'"
              @click="confirmAccept()">Подтвердить</button>
      <button class="btn" @click="confirmCancel()">Отмена</button>
    </template>
  </AppModal>
</template>
