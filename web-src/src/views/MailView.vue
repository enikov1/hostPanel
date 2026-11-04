<script setup lang="ts">
/* ============ Страница: Почта — домены и ящики ============ */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { genPassword } from '../lib/pw';
import { copyText } from '../lib/clipboard';
import { fmtDate } from '../lib/format';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';
import UiSelect from '../components/ui/UiSelect.vue';

const loaded = ref(false);
const data = ref<any | null>(null);
const st = computed<any>(() => (data.value || {}).status || {});
const domains = computed<any[]>(() => (data.value || {}).domains || []);
const mailboxes = computed<any[]>(() => (data.value || {}).mailboxes || []);
const hostname = location.hostname;

async function load(): Promise<void> {
  let d: any;
  try { d = await api('/api/mail'); }
  catch (e) { if (!loaded.value) toastErr(e); return; }
  data.value = d;
  loaded.value = true;
}

/* ---------- установка почтового стека ---------- */
let unmounted = false;

function mailInstallAll(): void {
  confirmDlg('Установка почты', 'Установить Postfix, Dovecot и Mailutils? Займёт 1–3 минуты.',
    async () => {
      for (const n of ['postfix', 'dovecot', 'mailutils']) {
        try { await api('/api/software/install', { method: 'POST', body: { name: n } }); }
        catch (e) { toastErr(e); return; }
        for (let i = 0; i < 150; i++) {  // ждём завершения фоновой задачи
          await new Promise((r2) => setTimeout(r2, 2000));
          if (unmounted) return;
          try { const t = await api('/api/packages/task'); if (!t.running) break; } catch (e2) { /* тихо */ }
        }
      }
      toast('Почтовый стек установлен');
      load();
    });
}

/* ---------- домены ---------- */
const domDlgOpen = ref(false);
const domName = ref('');

function mailDomainDlg(): void {
  domName.value = '';
  domDlgOpen.value = true;
}

async function mailDomainAdd(): Promise<void> {
  try {
    const r = await api('/api/mail/domains/add', { method: 'POST',
      body: { domain: domName.value.trim() } });
    toast(r.message);
    domDlgOpen.value = false;
    load();
  } catch (e) { toastErr(e); }
}

function mailDomainDel(domain: string): void {
  confirmDlg('Удалить домен', 'Удалить почтовый домен ' + domain + '? Сначала нужно удалить все его ящики.',
    async () => {
      try {
        const r = await api('/api/mail/domains/remove', { method: 'POST', body: { domain } });
        toast(r.message);
        load();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- ящики ---------- */
const boxDlgOpen = ref(false);
const boxLocal = ref('');
const boxDomain = ref('');
const boxPass = ref('');

function mailBoxDlg(domain?: string): void {
  boxLocal.value = '';
  boxDomain.value = domain || (domains.value.length ? domains.value[0].domain : '');
  boxPass.value = genPassword();
  boxDlgOpen.value = true;
}

const boxCreatedOpen = ref(false);
const boxCreatedEmail = ref('');
const boxCreatedPass = ref('');

async function mailBoxAdd(): Promise<void> {
  const email = boxLocal.value.trim() + '@' + boxDomain.value;
  try {
    const r = await api('/api/mail/boxes/add', { method: 'POST',
      body: { email, password: boxPass.value } });
    boxDlgOpen.value = false;
    boxCreatedEmail.value = email;
    boxCreatedPass.value = (r.data && r.data.password) || '';
    boxCreatedOpen.value = true;
  } catch (e) { toastErr(e); }
}

const boxPwOpen = ref(false);
const boxPwEmail = ref('');
const boxPwVal = ref('');

function mailBoxPwDlg(email: string): void {
  boxPwEmail.value = email;
  boxPwVal.value = genPassword();
  boxPwOpen.value = true;
}

async function mailBoxPw(): Promise<void> {
  try {
    const r = await api('/api/mail/boxes/password', { method: 'POST',
      body: { email: boxPwEmail.value, password: boxPwVal.value } });
    toast(r.message);
    boxPwOpen.value = false;
  } catch (e) { toastErr(e); }
}

function mailBoxDel(email: string): void {
  confirmDlg('Удалить ящик', 'Удалить ящик ' + email + ' вместе со всеми письмами?',
    async () => {
      try {
        const r = await api('/api/mail/boxes/remove', { method: 'POST', body: { email } });
        toast(r.message);
        load();
      } catch (e) { toastErr(e); }
    });
}

async function mailBoxTest(email: string): Promise<void> {
  toast('Отправляю тестовое письмо…');
  try {
    const r = await api('/api/mail/boxes/test', { method: 'POST', body: { email } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}

/* ---------- DNS-записи почты: SPF/DKIM/DMARC ---------- */
const dnsOpen = ref(false);
const dnsLoading = ref(false);
const dnsDomain = ref('');
const dnsData = ref<any | null>(null);

async function mailDnsDlg(domain: string): Promise<void> {
  dnsDomain.value = domain;
  dnsData.value = null;
  dnsLoading.value = true;
  dnsOpen.value = true;
  let d: any;
  try { d = await api('/api/mail/dns?domain=' + encodeURIComponent(domain)); }
  catch (e) { dnsOpen.value = false; toastErr(e); return; }
  dnsData.value = d;
  dnsLoading.value = false;
}

async function mailDkimGen(): Promise<void> {
  try {
    const r = await api('/api/mail/dkim/generate', { method: 'POST', body: { domain: dnsDomain.value } });
    toast(r.message);
    mailDnsDlg(dnsDomain.value);
  } catch (e) { toastErr(e); }
}

onMounted(load);
onBeforeUnmount(() => { unmounted = true; });
</script>

<template>
  <div v-table>
    <div class="empty" v-if="!loaded">Загрузка…</div>

    <template v-else>
      <!-- статус почтового сервера -->
      <div class="card" style="padding:14px">
        <div class="row" style="align-items:center;flex-wrap:wrap;gap:8px">
          <div class="row" style="align-items:center;gap:8px;flex-wrap:wrap">
            <b>Почтовый сервер</b>
            <span class="pill" :class="st.postfix_active ? 'ok' : 'err'"><span class="dot"></span>{{ st.postfix_active ? 'Postfix работает' : 'Postfix остановлен' }}</span>
            <span class="pill" :class="st.dovecot_active ? 'ok' : 'err'"><span class="dot"></span>{{ st.dovecot_active ? 'Dovecot работает' : 'Dovecot остановлен' }}</span>
          </div>
          <span class="spacer"></span>
          <span class="muted" style="font-size:13px">доменов: <b>{{ st.domains }}</b> · ящиков: <b>{{ st.mailboxes }}</b></span>
        </div>
        <div class="notice info" style="margin-top:10px">
          SMTP: порт 25 и 587 (авторизация) · IMAP: 143/993 · POP3: 110/995.
          Для приёма внешней почты добавьте у регистратора MX-запись домена на этот сервер
          (A-запись: {{ (st.server_ips || []).join(', ') || 'IP сервера' }}).</div>
      </div>

      <template v-if="!st.postfix_installed || !st.dovecot_installed">
        <div class="notice warn" style="margin-top:12px">Почтовые службы ещё не установлены.</div>
        <div class="row" style="margin-top:10px">
          <button class="btn primary" @click="mailInstallAll()">
            <UiIcon name="down" :size="15" /> Установить Postfix + Dovecot + Mailutils</button>
        </div>
      </template>

      <template v-else>
        <!-- почтовые домены -->
        <div class="card" style="margin-top:12px;padding:6px 10px">
          <div class="card-h" style="padding:10px 6px 0">
            <span class="card-t">Почтовые домены</span><span class="card-spacer"></span>
            <button class="btn sm primary" @click="mailDomainDlg()">
              <UiIcon name="plus" :size="14" /> Добавить домен</button>
            <span class="faint" style="font-size:11.5px">у каждого домена кнопка «DNS» — готовые SPF/DKIM/DMARC записи для регистратора</span>
          </div>
          <div class="twrap">
            <table>
              <thead><tr><th>Домен</th><th>Добавлен</th><th>Ящиков</th><th></th></tr></thead>
              <tbody>
                <tr v-if="!domains.length"><td colspan="4" class="muted">доменов нет</td></tr>
                <tr v-for="dm in domains" :key="dm.domain">
                  <td class="mono"><b>{{ dm.domain }}</b></td>
                  <td class="muted">{{ fmtDate(dm.created) }}</td>
                  <td>{{ mailboxes.filter((m: any) => m.domain === dm.domain).length }}</td>
                  <td>
                    <div class="actions-cell">
                      <button class="btn sm" @click="mailBoxDlg(dm.domain)">
                        <UiIcon name="plus" :size="13" /> Ящик</button>
                      <button class="btn sm" @click="mailDnsDlg(dm.domain)">DNS (SPF/DKIM)</button>
                      <button class="btn sm icon danger" @click="mailDomainDel(dm.domain)">
                        <UiIcon name="trash" :size="14" /></button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ящики -->
        <div class="card" style="margin-top:12px;padding:6px 10px">
          <div class="card-h" style="padding:10px 6px 0">
            <span class="card-t">Ящики</span><span class="card-spacer"></span>
            <button class="btn sm primary" @click="mailBoxDlg()">
              <UiIcon name="plus" :size="14" /> Создать ящик</button>
          </div>
          <div class="twrap">
            <table>
              <thead><tr><th>Ящик</th><th>Домен</th><th>Создан</th><th></th></tr></thead>
              <tbody>
                <tr v-if="!mailboxes.length"><td colspan="4" class="muted">ящиков нет</td></tr>
                <tr v-for="m in mailboxes" :key="m.email">
                  <td class="mono"><b>{{ m.email }}</b></td>
                  <td class="muted">{{ m.domain }}</td>
                  <td class="muted">{{ fmtDate(m.created) }}</td>
                  <td>
                    <div class="actions-cell">
                      <button class="btn sm" @click="mailBoxTest(m.email)">Тест доставки</button>
                      <button class="btn sm" @click="mailBoxPwDlg(m.email)">Пароль</button>
                      <button class="btn sm icon danger" @click="mailBoxDel(m.email)">
                        <UiIcon name="trash" :size="14" /></button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="muted" style="font-size:12.5px;padding:8px 6px">
            Настройки почтового клиента: сервер входящей почты IMAP — {{ hostname }},
            порт 143 (SSL 993); SMTP — порт 587; логин и пароль — как у ящика.</div>
        </div>
      </template>
    </template>

    <!-- добавление домена -->
    <AppModal :open="domDlgOpen" title="Почтовый домен" @close="domDlgOpen = false">
      <div class="field">
        <label>Домен (MX-запись должна указывать на этот сервер)</label>
        <input v-model="domName" type="text" placeholder="example.ru">
      </div>
      <div class="notice info">Панель пропишет домен в Postfix; ящики создаются на следующем шаге.</div>
      <template #footer>
        <button class="btn primary" @click="mailDomainAdd()">Добавить</button>
        <button class="btn" @click="domDlgOpen = false">Отмена</button>
      </template>
    </AppModal>

    <!-- создание ящика -->
    <AppModal :open="boxDlgOpen" title="Новый ящик" @close="boxDlgOpen = false">
      <div class="field">
        <label>Локальная часть (до @)</label>
        <input v-model="boxLocal" type="text" placeholder="info">
      </div>
      <div class="field">
        <label>Домен</label>
        <UiSelect v-model="boxDomain"
                  :options="!domains.length
                    ? [{ value: '', label: '— сначала добавьте домен —' }]
                    : domains.map((x: any) => ({ value: x.domain, label: x.domain }))" />
      </div>
      <PwField v-model="boxPass" label="Пароль (мин. 6 символов)" :gen="true"
               hint="Этот пароль вводится в почтовом клиенте. Скопируйте его кнопкой справа." />
      <template #footer>
        <button class="btn primary" @click="mailBoxAdd()">Создать</button>
        <button class="btn" @click="boxDlgOpen = false">Отмена</button>
      </template>
    </AppModal>

    <!-- ящик создан -->
    <AppModal :open="boxCreatedOpen" title="Ящик создан" @close="boxCreatedOpen = false">
      <div class="notice ok">Ящик <b>{{ boxCreatedEmail }}</b> создан.</div>
      <div class="field" style="margin-top:10px">
        <label>Пароль (сохраните — повторно не показывается)</label>
        <input type="text" class="mono" :value="boxCreatedPass" readonly>
      </div>
      <template #footer>
        <button class="btn primary" @click="boxCreatedOpen = false; load()">Готово</button>
      </template>
    </AppModal>

    <!-- смена пароля ящика -->
    <AppModal :open="boxPwOpen" :title="'Смена пароля: ' + boxPwEmail" @close="boxPwOpen = false">
      <div class="field">
        <label>Новый пароль (мин. 6 символов)</label>
        <div class="row">
          <input v-model="boxPwVal" type="text">
          <button class="btn" @click="boxPwVal = genPassword()">Сгенерировать</button>
        </div>
      </div>
      <template #footer>
        <button class="btn primary" @click="mailBoxPw()">Сменить</button>
        <button class="btn" @click="boxPwOpen = false">Отмена</button>
      </template>
    </AppModal>

    <!-- DNS-записи почты -->
    <AppModal :open="dnsOpen" :title="'DNS-записи почты — ' + dnsDomain" wide @close="dnsOpen = false">
      <div v-if="dnsLoading" class="empty">Загрузка…</div>
      <template v-else-if="dnsData">
        <div class="notice info">
          Добавьте эти записи у регистратора домена.
          Без SPF/DKIM/DMARC письма с вашего сервера почти наверняка попадают в спам.
          IP сервера: <b class="mono">{{ dnsData.server_ip || '—' }}</b>.
          Изменения DNS применяются до нескольких часов.</div>

        <template v-for="(rec, key) in { spf: dnsData.records.spf, dmarc: dnsData.records.dmarc, dkim: dnsData.records.dkim }" :key="key">
          <div class="kv">
            <b>{{ rec.type }} · <span class="mono">{{ rec.name }}</span></b>
            <span class="mono" style="word-break:break-all">{{ rec.value }}</span>
          </div>
          <div class="row" style="align-items:center;gap:8px;margin-bottom:8px">
            <span v-if="rec.ok" class="pill ok">запись есть в DNS</span>
            <span v-else class="pill warn">записи нет — добавьте у регистратора</span>
            <button class="btn sm" @click="copyText(rec.value, $event.currentTarget as HTMLElement)">
              <UiIcon name="file" :size="13" /> копировать</button>
          </div>
        </template>

        <div v-if="!dnsData.dkim_generated" class="row" style="margin-top:10px">
          <button class="btn" @click="mailDkimGen()">
            <UiIcon name="zap" :size="14" /> Сгенерировать DKIM-ключ</button>
          <span class="faint" style="font-size:11.5px">подпись писем DKIM требует также настройки opendkim в postfix — ключи сохранятся в панели</span>
        </div>
        <div v-if="dnsData.demo" class="notice info">демо-данные</div>
      </template>
      <template #footer>
        <button class="btn primary" @click="dnsOpen = false">Готово</button>
      </template>
    </AppModal>
  </div>
</template>
