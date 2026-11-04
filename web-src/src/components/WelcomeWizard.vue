<script setup lang="ts">
/* Welcome-мастер первого запуска: 2FA + переход к созданию сайта. */
import { ref, onMounted } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { session } from '../stores';
import AppModal from './AppModal.vue';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const tfa = ref<any>(null);
const qrSvg = ref('');
const code = ref('');
const busy = ref(false);

onMounted(async () => {
  let done2fa = false;
  try { done2fa = (await api('/api/totp/status')).enabled; } catch (e) { /* noop */ }
  if (!done2fa) {
    try {
      session.wizard2fa = await api('/api/totp/setup');
      tfa.value = session.wizard2fa;
    } catch (e) { session.wizard2fa = null; }
  }
  if (tfa.value && tfa.value.qr && tfa.value.uri) {
    api('/api/totp/qr?uri=' + encodeURIComponent(tfa.value.uri))
      .then((q: any) => { if (q.svg) qrSvg.value = q.svg; })
      .catch(() => { /* без QR остаётся ручной ввод ключа */ });
  }
});

async function enable2fa(): Promise<void> {
  const t = tfa.value;
  if (!t) return;
  busy.value = true;
  try {
    await api('/api/totp/enable', {
      method: 'POST', body: { secret: t.secret, code: code.value.trim() },
    });
    toast('Двухфакторная защита включена. При следующем входе нужен код из приложения');
    session.wizard2fa = null;
    emit('close');
  } catch (e) { toastErr(e); } finally { busy.value = false; }
}

function done(createSite?: boolean): void {
  try { localStorage.setItem('hp_wizard_done', '1'); } catch (e) { /* noop */ }
  session.wizard2fa = null;
  emit('close');
  if (createSite) routerToSites();
}

import { useRouter } from 'vue-router';
const router = useRouter();
function routerToSites(): void {
  router.push('/sites?create=1');
}
</script>

<template>
  <AppModal :open="open" title="Добро пожаловать в HostPanel!" :wide="true">
    <div class="notice ok">Панель готова к работе. Два коротких шага — и всё под защитой.</div>
    <template v-if="tfa">
      <div class="kv" style="margin-bottom:6px"><b>Шаг 1</b>
        <span>Включите двухфакторную защиту — даже если пароль утечёт, без кода из приложения в панель не войти.</span></div>
      <div class="row" style="gap:16px;align-items:flex-start">
        <div style="width:170px;min-height:170px;background:#fff;border-radius:10px;padding:6px;text-align:center"
             v-html="qrSvg ? qrSvg.replace('<svg', '<svg style=&quot;width:158px;height:158px&quot;') : ''"></div>
        <div style="flex:1;min-width:220px">
          <div class="muted" style="font-size:13px;line-height:1.55">
            Установите приложение-аутентификатор (Google Authenticator, Яндекс.Ключ и т.п.),
            отсканируйте QR-код или введите ключ вручную:
          </div>
          <div class="mono" style="font-size:14px;margin:8px 0;word-break:break-all;user-select:all">
            {{ tfa.secret }}</div>
          <div class="field">
            <label>Код из приложения (6 цифр)</label>
            <input v-model="code" type="text" class="mono" maxlength="6"
                   inputmode="numeric" autocomplete="one-time-code"
                   @keydown.enter="enable2fa">
          </div>
        </div>
      </div>
    </template>
    <div v-else class="kv" style="margin-bottom:6px"><b>Шаг 1</b>
      <span>Двухфакторная защита уже включена — отлично!</span></div>
    <div class="kv" style="margin-top:14px"><b>Шаг 2</b>
      <span>Создайте первый сайт: домен, версия PHP и база данных — мастер проведёт по шагам.</span></div>
    <template #footer>
      <template v-if="tfa">
        <button class="btn primary" :disabled="busy" @click="enable2fa">Включить 2FA</button>
        <button class="btn" @click="done(true)">Не включать — сразу к сайту</button>
        <button class="btn" @click="done()">Закрыть</button>
      </template>
      <template v-else>
        <button class="btn primary" @click="done(true)">Создать сайт</button>
        <button class="btn" @click="done()">Готово</button>
      </template>
    </template>
  </AppModal>
</template>
