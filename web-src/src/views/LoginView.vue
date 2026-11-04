<script setup lang="ts">
/* Экран входа: логин, пароль, 2FA. Ошибки приносит асинхронный
   callback-проп onLogin (её же выбрасывает App.doLogin). */
import { ref, nextTick } from 'vue';
import UiIcon from '../components/UiIcon.vue';

const props = defineProps<{
  defaultPw?: boolean;
  version?: string;
  onLogin: (login: string, password: string, code?: string) => Promise<void>;
}>();

const login = ref('admin');
const password = ref('');
const code = ref('');
const needCode = ref(false);
const busy = ref(false);
const error = ref('');

async function submit(): Promise<void> {
  error.value = '';
  busy.value = true;
  try {
    await props.onLogin(login.value, password.value,
                        needCode.value ? code.value : undefined);
  } catch (e: any) {
    if (e && e.need_code) needCode.value = true;
    error.value = (e && e.message) || 'Ошибка входа';
    await nextTick();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div id="login">
    <div class="login-card">
      <div class="login-logo">
        <span class="logo-ico"><UiIcon name="zap" :size="22" /></span>
        <div class="login-title">HostPanel
          <span style="font-size:13px;color:var(--muted);font-weight:400">{{ version }}</span>
        </div>
      </div>
      <div class="login-sub">Вход в панель управления</div>
      <form autocomplete="on" @submit.prevent="submit">
        <div class="field"><label>Логин</label>
          <input v-model="login" type="text" name="login" autocomplete="username"></div>
        <div class="field"><label>Пароль</label>
          <input v-model="password" type="password" name="password"
                 autocomplete="current-password"></div>
        <div v-if="needCode" class="field"><label>Код из приложения (2FA)</label>
          <input v-model="code" type="text" class="mono" placeholder="123456"
                 autocomplete="one-time-code" inputmode="numeric" maxlength="6"></div>
        <div v-if="error" class="login-error" role="alert">{{ error }}</div>
        <button type="submit" class="btn primary w100" style="margin-top:14px"
                :disabled="busy">Войти</button>
        <div v-if="defaultPw" class="login-hint">
          Первый вход? Стандартный логин и пароль — <b>admin</b> и <b>admin</b>.
          После входа панель сразу предложит задать надёжный пароль.
        </div>
      </form>
    </div>
  </div>
</template>
