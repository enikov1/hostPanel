<script setup lang="ts">
/* Модальное окно: телепорт в body, слоты body/footer, ширины и блокировка.
   Закрытие: клик по фону, крестик или Escape (пока окно открыто). */
import { watch, onBeforeUnmount } from 'vue';

const props = withDefaults(defineProps<{
  open: boolean;
  title: string;
  wide?: boolean | 'xwide';
  locked?: boolean;
}>(), { wide: false, locked: false });

import UiIcon from './UiIcon.vue';

const emit = defineEmits<{ close: [] }>();

function close(): void {
  if (props.locked) return;
  emit('close');
}

/* Escape закрывает открытое окно (глобальный слушатель — окно в Teleport,
   фокус может быть где угодно). */
function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    e.stopPropagation();
    close();
  }
}

watch(() => props.open, (v) => {
  if (v) document.addEventListener('keydown', onKey, true);
  else document.removeEventListener('keydown', onKey, true);
}, { immediate: true });

onBeforeUnmount(() => { document.removeEventListener('keydown', onKey, true); });
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modals-root" :class="{ open: open }"
         @mousedown.self="close()">
      <div class="modal" :class="wide === 'xwide' ? 'xwide' : wide ? 'wide' : ''">
        <div class="modal-h">
          {{ title }}
          <button v-if="!locked" class="btn icon modal-x" @click="close()">
            <UiIcon name="x" :size="15" />
          </button>
        </div>
        <!-- тело в форме: браузер не ругается на парольные поля вне формы,
             Enter в поле не приводит к перезагрузке страницы -->
        <div class="modal-b">
          <form class="modal-form" @submit.prevent>
            <slot />
          </form>
        </div>
        <div v-if="$slots.footer" class="modal-f">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style>
/* корневой оверлей — тот же класс, что и в прежней вёрстке */
.modals-root { position: fixed; inset: 0; z-index: 100; display: none;
  align-items: flex-start; justify-content: center;
  background: rgba(20, 30, 45, .45); backdrop-filter: blur(2px);
  overflow-y: auto; padding: 7vh 16px 30px; }
.modals-root.open { display: flex; }
</style>
