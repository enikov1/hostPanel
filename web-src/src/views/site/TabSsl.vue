<script setup lang="ts">
/* ============ Вкладка «SSL» карточки сайта (sslBlockHtml, dns, issue/del) ============ */
import { ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import { confirmDlg } from '../../lib/confirm';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import { siteState, sslActive, sslDays, type Site } from './siteShared';

const s = () => siteState.site;

/* ---------- проверка DNS домена (внутри вкладки) ---------- */
const dnsChecking = ref(false);
const dnsResult = ref<any | null>(null);
const dnsError = ref('');

async function sslDnsCheck(): Promise<void> {
  if (!s()) return;
  dnsChecking.value = true;
  dnsResult.value = null;
  dnsError.value = '';
  try {
    dnsResult.value = await api('/api/site/' + s()!.id + '/dns_check');
  } catch (e: any) {
    dnsError.value = e.message || String(e);
  }
  dnsChecking.value = false;
}

/* ---------- выпуск / удаление сертификата ---------- */
async function refreshSite(): Promise<void> {
  const cur = s();
  if (!cur) return;
  try {
    const d = await api('/api/sites');
    const updated = (d.sites || []).find((x: any) => x.id === cur.id);
    if (updated) siteState.site = updated;
  } catch (e) { /* тихо */ }
}

async function sslIssueGo(kind: string): Promise<void> {
  const email = kind === 'letsencrypt' ? (window.prompt('E-mail для уведомлений Let\'s Encrypt (можно пропустить):') || '') : '';
  try {
    const r = await api('/api/sites/ssl', { method: 'POST', body: { id: s()!.id, kind, email } });
    toast(r.message);
    refreshSite();
  } catch (e) { toastErr(e); }
}

async function sslIssue(kind: string): Promise<void> {
  if (kind === 'letsencrypt') {
    let dns: any = null;
    try { dns = await api('/api/site/' + s()!.id + '/dns_check'); }
    catch (e) { /* игнорируем — попробуем выпустить */ }
    if (dns && !dns.dns_ok) {
      const serverIp = (dns.server_ips || []).join(', ') || 'см. «Обзор»';
      confirmDlg('Домен ещё не указывает на сервер',
        'A-запись домена ' + s()!.domain + ' пока не указывает ' +
        'на IP этого сервера (' + serverIp + '). Выпуск Let\'s Encrypt почти наверняка ' +
        'провалится. Сначала настройте DNS у регистратора (изменения применяются ' +
        'до нескольких часов). Всё равно попробовать?',
        () => { void sslIssueGo(kind); }, false);
      return;
    }
  }
  sslIssueGo(kind);
}

function sslDel(): void {
  confirmDlg('Удалить сертификат', 'Сертификат сайта ' + s()!.domain + ' будет удалён.',
    async () => {
      try {
        const r = await api('/api/sites/ssl_delete', { method: 'POST', body: { id: s()!.id } });
        toast(r.message);
        refreshSite();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- полная диагностика DNS ---------- */
const dnsFullOpen = ref(false);
const dnsFullLoading = ref(false);
const dnsFull = ref<any | null>(null);

async function siteDnsFullDlg(): Promise<void> {
  dnsFull.value = null;
  dnsFullLoading.value = true;
  dnsFullOpen.value = true;
  let r: any;
  try { r = await api('/api/site/' + s()!.id + '/dns_full'); }
  catch (e) { dnsFullOpen.value = false; dnsFullLoading.value = false; toastErr(e); return; }
  dnsFull.value = r;
  dnsFullLoading.value = false;
}

function arr(a: string[] | undefined): string {
  return a && a.length ? a.join(', ') : '—';
}

function sslKindText(kind: string): string {
  return kind === 'letsencrypt' ? "Let's Encrypt" : 'Самоподписанный';
}

/* ---------- пилюля дней до конца сертификата ---------- */
function daysLeft(site: Site): number | null {
  return sslDays(site);
}

function daysPillCls(site: Site): string {
  const d = sslDays(site);
  if (d === null) return 'pill err';
  if (d < 14) return 'pill err';
  if (d < 30) return 'pill warn';
  return 'pill ok';
}

function daysPillText(site: Site): string {
  const d = sslDays(site);
  return d === null ? 'истекает' : d + ' дн.';
}

/** владелец/issuer — если сервер их отдал */
function issuerText(site: Site): string {
  const ssl = site.ssl || {};
  const owner = ssl.owner || ssl.subject || '';
  const issuer = ssl.issuer || '';
  return [owner, issuer].filter(Boolean).join(' · ');
}
</script>

<template>
  <div v-if="s()">
    <!-- SSL не настроен: состояние-приглашение -->
    <template v-if="!sslActive(s()!)">
      <div class="card" style="padding:16px 18px">
        <div class="card-h" style="margin-bottom:8px">
          <UiIcon name="lock" :size="18" />
          <span class="card-t">Сайт работает по HTTP</span>
          <span class="pill warn">без SSL</span>
        </div>
        <div class="notice warn" style="margin-bottom:8px">
          SSL не настроен — соединение с сайтом не шифруется.
          Рекомендуется Let's Encrypt — бесплатный сертификат с автопродлением.</div>
        <div class="faint" style="font-size:12px;margin:-2px 0 10px">Сертификат выпускается для домена<template v-if="s()!.www"> и для www.{{ s()!.domain }}.</template><template v-else> (www отключён — включите галочку «Обслуживать www.домен» во вкладке «Основное», если он нужен).</template></div>
        <div class="row">
          <button class="btn primary" @click="sslIssue('letsencrypt')">
            <UiIcon name="shield" :size="15" /> Выпустить Let's Encrypt</button>
          <button class="btn" @click="sslIssue('selfsigned')">
            <UiIcon name="lock" :size="15" /> Самоподписанный</button>
        </div>
      </div>
    </template>

    <!-- сертификат есть: карточка с информацией -->
    <template v-else>
      <div class="card" style="padding:14px 18px">
        <div class="card-h" style="margin-bottom:10px">
          <UiIcon name="lock" :size="18" />
          <span class="card-t">Сертификат</span>
          <span :class="daysPillCls(s()!)">{{ daysPillText(s()!) }}</span>
        </div>
        <div class="kv">
          <b>Тип</b><span>{{ sslKindText(s()!.ssl.kind) }}</span>
          <b>Домены</b><span class="mono" style="word-break:break-all">{{ (s()!.ssl.domains || []).join(', ') }}</span>
          <b>Действует до</b><span>{{ s()!.ssl.expires }} <span :class="daysPillCls(s()!)">{{ daysPillText(s()!) }}</span></span>
          <template v-if="issuerText(s()!)">
            <b>Владелец / issuer</b><span>{{ issuerText(s()!) }}</span>
          </template>
        </div>
        <div class="row" style="margin-top:14px">
          <button class="btn primary" @click="sslIssue('letsencrypt')">
            <UiIcon name="refresh" :size="15" /> Перевыпустить</button>
          <button class="btn danger" @click="sslDel()">
            <UiIcon name="trash" :size="15" /> Удалить сертификат</button>
        </div>
      </div>
    </template>

    <!-- диагностика: отдельная группа -->
    <div class="row" style="margin-top:12px">
      <button class="btn" @click="sslDnsCheck()">
        <UiIcon name="globe" :size="15" /> Проверить DNS домена</button>
      <button class="btn" @click="siteDnsFullDlg()">
        <UiIcon name="shield" :size="15" /> Полная диагностика DNS</button>
    </div>

    <!-- результат проверки DNS -->
    <div style="margin-top:10px">
      <div v-if="dnsChecking" class="empty">Проверяю DNS…</div>
      <div v-else-if="dnsError" class="notice err">{{ dnsError }}</div>
      <template v-else-if="dnsResult">
        <div class="kv">
          <b>Домен</b><span class="mono">{{ dnsResult.domain }}
            <span :class="dnsResult.dns_ok ? 'pill ok' : 'pill err'">{{ dnsResult.dns_ok ? 'указывает на этот сервер' : 'не указывает на этот сервер' }}</span></span>
          <b>A-записи</b><span class="mono">{{ (dnsResult.ipv4 || []).join(', ') || '—' }}</span>
          <b>AAAA-записи</b><span class="mono">{{ (dnsResult.ipv6 || []).join(', ') || '—' }}</span>
          <b>IP сервера</b><span class="mono">{{ (dnsResult.server_ips || []).join(', ') || '—' }}</span>
        </div>
        <div v-if="!dnsResult.dns_ok" class="notice warn" style="margin-top:8px">
          Для Let's Encrypt домен должен указывать на IP этого сервера: измените A-запись в панели регистратора домена и повторите проверку.</div>
      </template>
    </div>

    <!-- полная диагностика DNS -->
    <AppModal :open="dnsFullOpen" :title="'Диагностика DNS: ' + (dnsFull ? dnsFull.domain : s()!.domain)" wide
              @close="dnsFullOpen = false">
      <div v-if="dnsFullLoading" class="empty">Смотрю записи…</div>
      <template v-else-if="dnsFull">
        <div class="notice info">Записи настраиваются у регистратора домена.
          A-записи должны указывать на IP сервера: <b class="mono">{{ (dnsFull.server_ips || []).join(', ') }}</b>.
          Изменения DNS применяются до нескольких часов.</div>
        <div class="kv">
          <b>A (домен → IP) <span :class="dnsFull.a.ok ? 'pill ok' : 'pill warn'">{{ dnsFull.a.ok ? 'ок' : 'проверить' }}</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.a.current) }}</span>
          <b>A (www) <span :class="dnsFull.www.ok ? 'pill ok' : 'pill warn'">{{ dnsFull.www.ok ? 'ок' : 'проверить' }}</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.www.current) }}</span>
          <b>AAAA (IPv6) <span class="pill ok">ок</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.aaaa.current) }}</span>
          <b>MX (почта) <span class="pill ok">ок</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.mx.current) }}</span>
          <b>NS (серверы имён) <span class="pill ok">ок</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.ns.current) }}</span>
          <b>SPF <span :class="dnsFull.spf.ok ? 'pill ok' : 'pill warn'">{{ dnsFull.spf.ok ? 'ок' : 'проверить' }}</span></b>
          <span class="mono" style="word-break:break-all">{{ arr(dnsFull.spf.current) }}</span>
        </div>
        <div v-if="!dnsFull.spf.ok" class="notice warn" style="margin-top:8px">
          SPF-записи нет — письма с сайта могут попадать в спам.
          Рекомендуемая запись: <b class="mono">{{ dnsFull.spf.recommended }}</b> (TXT, имя {{ dnsFull.domain }})</div>
        <div v-if="dnsFull.demo" class="notice info">демо-данные</div>
      </template>
      <template #footer>
        <button class="btn primary" @click="dnsFullOpen = false">Понятно</button>
      </template>
    </AppModal>
  </div>
</template>
