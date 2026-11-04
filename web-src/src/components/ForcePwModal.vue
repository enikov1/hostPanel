<script setup lang="ts">
/* Принудительная смена стандартного/временного пароля (блокирующее окно). */
import { ref, computed } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { session } from '../stores';
import AppModal from './AppModal.vue';
import PwField from './PwField.vue';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ saved: [] }>();

// реактивно: значение на момент ОТКРЫТИЯ окна (как в исходнике)
const isDefault = computed(() => session.defaultPw === true);
const oldPw = ref('');
const newPw = ref('');
const repeat = ref('');
const busy = ref(false);

async function save(): Promise<void> {
  if (!isDefault.value && !oldPw.value) {
    toast('Введите текущий (временный) пароль', 'warn'); return;
  }
  if (newPw.value.length < 8) {
    toast('Пароль слишком короткий — минимум 8 символов', 'warn'); return;
  }
  if (newPw.value === 'admin') {
    toast('Пароль «admin» использовать нельзя', 'warn'); return;
  }
  if (newPw.value !== repeat.value) {
    toast('Пароли не совпадают', 'warn'); return;
  }
  busy.value = true;
  try {
    await api('/api/password/change', {
      method: 'POST',
      body: { old: isDefault.value ? 'admin' : oldPw.value, new: newPw.value },
    });
    emit('saved');
  } catch (e) { toastErr(e); } finally { busy.value = false; }
}
</script>

<template>
  <AppModal :open="open" title="Смените пароль" :locked="true">
    <div v-if="isDefault" class="notice warn" style="margin-top:2px">
      Вы вошли со стандартным паролем <b class="mono">admin</b>. Это небезопасно —
      панель открыта из интернета. Придумайте свой пароль прямо сейчас.
    </div>
    <div v-else class="notice warn" style="margin-top:2px">
      Пароль был сброшен из консоли. Задайте свой собственный пароль прямо сейчас.
    </div>
    <div v-if="!isDefault" class="field">
      <label>Текущий пароль (временный, из сообщения поддержки)</label>
      <input v-model="oldPw" type="password" autocomplete="current-password">
    </div>
    <PwField v-model="newPw" label="Новый пароль"
             hint="Нажмите «сгенерировать» — создастся надёжный пароль. Скопируйте его и сохраните в надёжном месте." />
    <div class="field">
      <label>Повторите пароль</label>
      <input v-model="repeat" type="text" class="mono" placeholder="введите пароль ещё раз">
    </div>
    <template #footer>
      <button class="btn primary" :disabled="busy" @click="save">
        Сохранить новый пароль
      </button>
    </template>
  </AppModal>
</template>
