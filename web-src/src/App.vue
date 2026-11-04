<script setup lang="ts">
/* Корневой компонент: загрузка сессии, экран входа или оболочка панели,
   принудительная смена пароля, welcome-мастер. */
import { ref, onMounted, provide, watch } from 'vue';
import { useRouter } from 'vue-router';
import { api, setUnauthorizedHook } from './api/client';
import { me, session } from './stores';
import { toast, toastErr } from './lib/toast';
import Shell from './layouts/Shell.vue';
import LoginView from './views/LoginView.vue';
import ConfirmHost from './components/ConfirmHost.vue';
import ForcePwModal from './components/ForcePwModal.vue';
import WelcomeWizard from './components/WelcomeWizard.vue';
import ToastHost from './components/ToastHost.vue';
import { navPath } from './router';

const authed = ref<boolean | null>(null); // null = ещё проверяем
const showForcePw = ref(false);
const showWizard = ref(false);
const router = useRouter();

function enterApp(): void {
  authed.value = true;
  document.title = 'HostPanel — панель управления сервером';
}

function exitToLogin(): void {
  authed.value = false;
  router.push('/');
}

/** Открыть раздел по прежнему строковому id (для поиска). */
function gotoSection(id: string, siteId?: number): void {
  if (id === 'site' && siteId) {
    router.push('/sites/' + siteId);
    return;
  }
  router.push(navPath(id));
}
provide('gotoSection', gotoSection);

onMounted(async () => {
  setUnauthorizedHook(exitToLogin);
  try { applyThemeFromStorage(); } catch (e) { /* noop */ }
  // статус сессии спрашиваем у /api/login-state — он ВСЕГДА отвечает 200,
  // поэтому до входа в консоли нет ни одного 401
  const st = await fetch('/api/login-state').then((r) => r.json()).catch(() => null);
  session.defaultPw = !!(st && st.default_password);
  session.version = st && st.version ? 'v' + st.version : '';
  if (!st || !st.auth) { authed.value = false; return; }
  try {
    Object.assign(me, await api('/api/me'));
    me.ok = true;
  } catch (e) { authed.value = false; return; }
  enterApp();
  if (me.must_change_password) setTimeout(() => { showForcePw.value = true; }, 400);
  else maybeWizard();
});

function maybeWizard(): void {
  let done = false;
  try { done = localStorage.getItem('hp_wizard_done') === '1'; } catch (e) { /* noop */ }
  if (!done && me.demo !== true) setTimeout(() => { showWizard.value = true; }, 400);
}

async function doLogin(login: string, password: string, code?: string): Promise<void> {
  const r = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password, code: code || undefined }),
  });
  let j: any = {};
  try { j = await r.json(); } catch (e) { /* пустое тело */ }
  if (r.status === 429) {
    throw new Error('Слишком много неудачных попыток входа — вход заблокирован на 5 минут. ' +
      'Если пароль потерян, сбросьте его на сервере командой hcp reset-password.');
  }
  if (j.need_code) {
    const err = new Error(j.error || 'Введите код из приложения-аутентификатора') as any;
    err.need_code = true;
    if (j.attempts_left === 0) err.message += '. Попытки исчерпаны — вход заблокирован на 5 минут';
    else if (typeof j.attempts_left === 'number') err.message += '. Осталось попыток: ' + j.attempts_left;
    throw err;
  }
  if (!j.ok) {
    let msg: string = j.error || 'Неверный логин или пароль.';
    if (j.attempts_left === 0)
      msg += ' Попытки исчерпаны — вход заблокирован на 5 минут (сброс: hcp reset-password на сервере).';
    else if (typeof j.attempts_left === 'number')
      msg += ' Осталось попыток: ' + j.attempts_left + ' — потом блокировка на 5 минут.';
    throw new Error(msg);
  }
  // вход выполнен — загружаем профиль без перезагрузки страницы
  try {
    Object.assign(me, await api('/api/me'));
    me.ok = true;
  } catch (e) { throw new Error('вход выполнен, но профиль не загрузился'); }
  enterApp();
  if (me.must_change_password) setTimeout(() => { showForcePw.value = true; }, 400);
  else maybeWizard();
}

async function doLogout(): Promise<void> {
  try { await api('/api/logout', { method: 'POST', body: {} }); } catch (e) { /* noop */ }
  exitToLogin();
}

function onForcePwSaved(): void {
  showForcePw.value = false;
  me.must_change_password = false;
  session.defaultPw = false;
  toast('Пароль изменён — старый больше не работает');
  router.push('/');
  maybeWizard();
}

function applyThemeFromStorage(): void { /* тема применена в main.ts */ }
</script>

<template>
  <!-- экран загрузки: пока сессия проверяется -->
  <div v-if="authed === null" class="boot-loading">Загрузка…</div>

  <LoginView v-else-if="!authed" :default-pw="session.defaultPw"
             :version="session.version" @login="doLogin" />

  <Shell v-else @logout="doLogout">
    <router-view />
  </Shell>

  <ForcePwModal :open="showForcePw" @saved="onForcePwSaved" />
  <WelcomeWizard :open="showWizard" @close="showWizard = false" />
  <ConfirmHost />
  <ToastHost />
</template>

<style>
.boot-loading {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 14px;
}
</style>
