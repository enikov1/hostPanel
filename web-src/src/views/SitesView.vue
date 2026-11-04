<script setup lang="ts">
/* ============ Страница: Сайты — список, мастера, pma, заглушка IP ============ */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtSize } from '../lib/format';
import { genPassword } from '../lib/pw';
import { me } from '../stores';
import UiIcon from '../components/UiIcon.vue';
import BrandLogo from '../components/BrandLogo.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';
import CredRow from '../components/CredRow.vue';
import UiCheckbox from '../components/ui/UiCheckbox.vue';
import { pmaApps } from './software/pmaStore';
import DiskCard from './site/DiskCard.vue';
import WizardCreate from './site/WizardCreate.vue';
import WizardSubdomain from './site/WizardSubdomain.vue';
import WizardImport from './site/WizardImport.vue';
import { wsLabel, sslActive, sslDays, type Site } from './site/siteShared';

const route = useRoute();
const router = useRouter();

const loaded = ref(false);
const sites = ref<Site[]>([]);

const roots = computed<Site[]>(() => sites.value.filter((s) => !s.parent));
const subsCount = computed(() => sites.value.filter((s) => s.parent).length);

function children(s: Site): Site[] {
  return sites.value.filter((x) => x.parent === s.id);
}

/* ---------- загрузка ---------- */
async function load(): Promise<void> {
  let d: any, apps: any[];
  try {
    const res = await Promise.all([
      api('/api/sites'),
      api('/api/apps').then((x: any) => x.apps || []).catch(() => [])]);
    d = res[0]; apps = res[1];
  } catch (e) {
    if (!loaded.value) toastErr(e);
    return;
  }
  pmaApps.value = apps || [];
  sites.value = d.sites || [];
  loaded.value = true;
  runDnsPills();
}

/* ---------- плашки DNS у сайтов без SSL ---------- */
const dnsInfo = ref<Record<number, { state: 'loading' | 'ok' | 'fail'; ips: string }>>({});

function runDnsPills(): void {
  roots.value.filter((s) => !sslActive(s)).forEach(async (s) => {
    dnsInfo.value[s.id] = { state: 'loading', ips: '' };
    let r: any = null;
    try { r = await api('/api/site/' + s.id + '/dns_check'); }
    catch (e) { delete dnsInfo.value[s.id]; return; }
    if (!sites.value.some((x) => x.id === s.id)) return;
    const ips = (r.server_ips || []).join(', ');
    dnsInfo.value[s.id] = { state: r.dns_ok ? 'ok' : 'fail', ips };
  });
}

function dnsTitle(s: Site): string {
  const info = dnsInfo.value[s.id];
  if (!info) return 'Проверяю DNS-запись домена…';
  if (info.state === 'ok') return 'Домен указывает на этот сервер — можно выпускать Let\'s Encrypt';
  return 'Домен ' + s.domain + ' пока НЕ указывает на этот сервер. ' +
    'Добавьте у регистратора A-запись: ' + s.domain + ' → ' +
    (info.ips || 'IP сервера (см. «Обзор»)') + '. Изменения DNS применяются до нескольких часов.';
}

/* ---------- тексты ячеек ---------- */
/** бренд логотипа по веб-серверу сайта (nginx+apache → apache, nginx+node → node) */
function wsBrand(ws: string): string {
  if (ws === 'nginx+node') return 'node';
  if (ws === 'nginx+apache') return 'apache';
  return ws || 'static';
}

function phpNodeText(s: Site): string {
  let t = s.php ? 'PHP ' + s.php : '';
  if (s.node && s.node.enabled) t = (t ? t + ' + ' : '') + 'Node ' + s.node.version;
  return t;
}

function sslPillCls(s: Site): string {
  const days = sslDays(s);
  if (days === null) return 'warn';
  return days < 20 ? 'err' : days < 40 ? 'warn' : 'ok';
}

function sslPillText(s: Site): string {
  const kind = s.ssl.kind === 'letsencrypt' ? "Let's Encrypt" : 'самоподписанный';
  const days = sslDays(s);
  return days === null ? kind : kind + ' · ' + days + ' дн.';
}

/* ---------- вкл/выкл, удаление ---------- */
function findSite(id: number): Site | undefined {
  const all = [...sites.value, ...sites.value.flatMap((x) => children(x))];
  return all.find((x) => x.id === id);
}

/** Остановить/запустить сайт — с подтверждением. */
function toggleSite(id: number): void {
  const s = findSite(id);
  if (!s) return;
  const stop = !!s.enabled;
  const what = stop ? 'Остановить сайт' : 'Запустить сайт';
  const detail = stop
    ? 'Сайт ' + s.domain + ' перестанет отвечать на запросы: посетители увидят заглушку «Сайт отключён». Файлы и настройки сохранятся.'
    : 'Сайт ' + s.domain + ' начнёт обслуживать запросы.';
  confirmDlg(what, detail + ' Продолжить?', async () => {
    try {
      const r = await api('/api/sites/toggle', { method: 'POST', body: { id } });
      toast(r.message);
      load();
    } catch (e) { toastErr(e); }
  }, false);
}

function delSite(id: number, domain: string): void {
  confirmDlg('Удалить сайт',
    'Сайт ' + domain + ', его конфиги и поддомены будут удалены. Файлы в папке сайта останутся. Продолжить?',
    async () => {
      try {
        const r = await api('/api/sites/delete', { method: 'POST', body: { id, delete_files: false } });
        toast(r.message);
        load();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- phpMyAdmin в строке сайта ---------- */
const pmaViewOpen = ref(false);
const pmaViewDomain = ref('');
const pmaView = ref<any | null>(null);
const pmaInstOpen = ref(false);
const pmaInstDomain = ref('');
const pmaProtect = ref(true);
const pmaPass = ref('');

let unmounted = false;

function pmaOf(domain: string): any | null {
  return pmaApps.value.find((a: any) => a.domain === domain) || null;
}

function pmaSiteDlg(domain: string): void {
  const a = pmaOf(domain);
  if (a && a.installed) {  // у неустановленного pma нет url — раньше окно
    pmaViewDomain.value = domain;
    pmaView.value = a;
    pmaViewOpen.value = true;
    return;
  }
  pmaInstDomain.value = domain;
  pmaProtect.value = true;
  pmaPass.value = genPassword();
  pmaInstOpen.value = true;
}

function pmaSiteOpen(domain: string): void {
  const a = pmaOf(domain);
  if (a && a.url) window.open(a.url, '_blank', 'noopener');
  else toast('phpMyAdmin ещё не установлен — установите его кнопкой «Установить»', 'warn');
}

async function pmaSiteInstall(): Promise<void> {
  try {
    const r = await api('/api/apps/install', { method: 'POST',
      body: { app: 'pma', site: pmaInstDomain.value, protect: pmaProtect.value, password: pmaPass.value } });
    pmaInstOpen.value = false;
    toast(r.message);
    pmaSiteWait();
  } catch (e) { toastErr(e); }
}

async function pmaSiteWait(): Promise<void> {
  for (let i = 0; i < 180; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    if (unmounted) return;
    try { const t = await api('/api/apps'); if (!t.running) break; }
    catch (e) { return; }
  }
  if (unmounted) return;
  toast('phpMyAdmin готов — кнопка «phpMyAdmin» у сайта покажет адрес и доступы');
  load();
}

function pmaRemove(domain: string): void {
  confirmDlg('Удалить phpMyAdmin',
    'Папка /pma сайта ' + domain + ' будет удалена вместе с настройками. Удалить?',
    async () => {
      try {
        const r = await api('/api/apps/remove', { method: 'POST',
          body: { app: 'pma', site: domain } });
        toast(r.message);
        pmaViewOpen.value = false;
        load();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- заглушка для IP-адреса сервера ---------- */
const defaultOpen = ref(false);
const dsContent = ref('');

async function defaultSiteDlg(): Promise<void> {
  let d: any;
  try { d = await api('/api/default-site'); }
  catch (e) { toastErr(e); return; }
  dsContent.value = d.content || '';
  defaultOpen.value = true;
}

async function defaultSiteSave(): Promise<void> {
  try {
    const r = await api('/api/default-site', { method: 'POST',
      body: { content: dsContent.value } });
    toast(r.message);
    defaultOpen.value = false;
  } catch (e) { toastErr(e); }
}

/* ---------- мастера ---------- */
const wizardOpen = ref(false);
const importOpen = ref(false);
const subOpen = ref(false);
const subParentId = ref(0);
const subParentDomain = ref('');

function wizardSubdomain(parentId: number, parentDomain: string): void {
  subParentId.value = parentId;
  subParentDomain.value = parentDomain;
  subOpen.value = true;
}

onMounted(() => {
  load();
  // обзор ссылается на /sites?wizard=1 — сразу открываем мастер
  if (route.query.wizard === '1') {
    wizardOpen.value = true;
    void router.replace({ path: '/sites' });
  }
});

onBeforeUnmount(() => { unmounted = true; });
</script>

<template>
  <div v-table>
    <div v-if="!loaded" class="empty">Загрузка…</div>

    <!-- нет ни одного сайта -->
    <div v-else-if="!sites.length" class="card" style="text-align:center;padding:54px 20px">
      <div style="max-width:520px;margin:0 auto">
        <div class="empty" style="padding:0 0 8px">Здесь появятся ваши сайты.</div>
        <div class="muted" style="font-size:13.5px;line-height:1.6;margin-bottom:18px">
          Сайт — это ваш адрес в интернете, например <b>mysite.ru</b>. Создайте его здесь,
          затем загрузите файлы и привяжите домен. Если PHP ещё не установлен, мастер подскажет.</div>
        <button class="btn primary" @click="wizardOpen = true">
          <UiIcon name="plus" :size="15" /> Создать первый сайт</button>
      </div>
    </div>

    <template v-else>
      <div class="toolbar">
        <button class="btn primary" @click="wizardOpen = true">
          <UiIcon name="plus" :size="15" />Создать сайт</button>
        <button class="btn" title="Страница, которая открывается по IP-адресу сервера (404, закрыта от индексации)"
                @click="defaultSiteDlg()">
          <UiIcon name="file" :size="15" /> Заглушка для IP</button>
        <button class="btn" title="Переезд с другого хостинга: zip с файлами сайта и дамп базы"
                @click="importOpen = true">
          <UiIcon name="up" :size="15" /> Импорт архивом</button>
        <span class="spacer"></span>
        <span class="muted" style="font-size:13px">Сайтов: {{ sites.length }} · поддоменов: {{ subsCount }}</span>
      </div>

      <DiskCard :sites="sites" />

      <div class="card" style="padding:6px 10px">
        <div class="twrap">
          <table>
            <thead>
              <tr><th>Домен</th><th>Веб-сервер</th><th>PHP / Node</th><th>SSL</th>
                  <th>Фильтры</th><th>Место</th><th>Статус</th><th></th></tr>
            </thead>
            <tbody>
              <template v-for="s in roots" :key="s.id">
                <tr>
                  <td>
                    <b>{{ s.domain }}</b>
                    <span v-if="!s.enabled" class="pill warn">отключён</span>
                    <span v-if="s.maintenance" class="pill warn">обслуживание</span>
                    <span v-if="!sslActive(s) && dnsInfo[s.id]" class="pill"
                          :class="{ gray: dnsInfo[s.id].state === 'loading', ok: dnsInfo[s.id].state === 'ok', warn: dnsInfo[s.id].state === 'fail' }"
                          :title="dnsTitle(s)">
                      {{ dnsInfo[s.id].state === 'loading' ? 'DNS…' : dnsInfo[s.id].state === 'ok' ? 'DNS ок' : 'DNS не настроен' }}
                    </span>
                  </td>
                  <td><BrandLogo :brand="wsBrand(s.webserver)" :size="14" fallback="globe" /> {{ wsLabel(s.webserver) }}</td>
                  <td>
                    <span v-if="phpNodeText(s)">
                      <BrandLogo v-if="s.php" brand="php" :size="14" fallback="pkg" />
                      <BrandLogo v-if="s.node && s.node.enabled" brand="node" :size="14" fallback="pkg" />
                      {{ phpNodeText(s) }}</span>
                    <span v-else class="faint">—</span>
                  </td>
                  <td>
                    <span v-if="sslActive(s)" class="pill" :class="sslPillCls(s)">{{ sslPillText(s) }}</span>
                    <span v-else class="pill gray">нет</span>
                  </td>
                  <td class="muted" style="font-size:12px">{{ s.security_status || 'нет' }}</td>
                  <td>{{ fmtSize(s.disk) }}</td>
                  <td><span class="pill" :class="s.enabled ? 'ok' : 'gray'"><span class="dot"></span>{{ s.enabled ? 'работает' : 'отключён' }}</span></td>
                  <td>
                    <div class="actions-cell">
                      <router-link class="btn sm" :to="'/sites/' + s.id" title="Настройки сайта">
                        <UiIcon name="gear" :size="14" /> Настройки</router-link>
                      <button v-if="s.php" class="btn sm"
                              :title="pmaOf(s.domain) ? 'phpMyAdmin установлен — открыть в новом окне' : 'Установить phpMyAdmin в папку /pma этого сайта'"
                              @click="pmaSiteDlg(s.domain)">
                        <UiIcon :name="pmaOf(s.domain) ? 'ext' : 'down'" :size="14" /> phpMyAdmin</button>
                      <button class="btn sm icon"
                              :class="{ warn: s.enabled }"
                              :title="s.enabled ? 'Остановить сайт' : 'Запустить сайт'"
                              @click="toggleSite(s.id)">
                        <UiIcon :name="s.enabled ? 'pause' : 'play'" :size="14" /></button>
                      <button class="btn sm icon" title="Поддомен" @click="wizardSubdomain(s.id, s.domain)">
                        <UiIcon name="plus" :size="14" /></button>
                      <button class="btn sm icon danger" title="Удалить" @click="delSite(s.id, s.domain)">
                        <UiIcon name="trash" :size="14" /></button>
                    </div>
                  </td>
                </tr>
                <tr v-for="ch in children(s)" :key="ch.id" class="sub-row">
                  <td style="padding-left:26px">
                    <span class="faint">└</span> <b>{{ ch.domain }}</b>
                    <span v-if="!ch.enabled" class="pill warn">отключён</span>
                    <span v-if="ch.maintenance" class="pill warn">обслуж.</span>
                  </td>
                  <td class="muted"><BrandLogo :brand="wsBrand(ch.webserver)" :size="14" fallback="globe" /> {{ wsLabel(ch.webserver) }}</td>
                  <td class="muted">
                    <template v-if="ch.php"><BrandLogo brand="php" :size="14" fallback="pkg" /> PHP {{ ch.php }}</template>
                    <template v-else>—</template>
                  </td>
                  <td>
                    <span v-if="sslActive(ch)" class="pill ok">SSL</span>
                    <span v-else class="pill gray">нет</span>
                  </td>
                  <td class="muted" style="font-size:12px">{{ ch.security_status || 'нет' }}</td>
                  <td class="muted">{{ fmtSize(ch.disk) }}</td>
                  <td><span class="pill" :class="ch.enabled ? 'ok' : 'gray'">{{ ch.enabled ? 'работает' : 'отключён' }}</span></td>
                  <td>
                    <div class="actions-cell">
                      <router-link class="btn sm" :to="'/sites/' + ch.id" title="Настройки сайта">
                        <UiIcon name="gear" :size="14" /></router-link>
                      <button class="btn sm icon"
                              :title="ch.enabled ? 'Остановить сайт' : 'Запустить сайт'"
                              @click="toggleSite(ch.id)">
                        <UiIcon :name="ch.enabled ? 'pause' : 'play'" :size="14" /></button>
                      <button v-if="ch.php" class="btn sm"
                              :title="pmaOf(ch.domain) ? 'phpMyAdmin установлен — открыть в новом окне' : 'Установить phpMyAdmin в папку /pma этого сайта'"
                              @click="pmaSiteDlg(ch.domain)">
                        <UiIcon :name="pmaOf(ch.domain) ? 'ext' : 'down'" :size="14" /> phpMyAdmin</button>
                      <button class="btn sm icon danger" title="Удалить" @click="delSite(ch.id, ch.domain)">
                        <UiIcon name="trash" :size="14" /></button>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <div class="faint" style="font-size:12px;margin-top:10px">SSL — это защита соединения: сайт открывается
        по https:// и браузер показывает замочек. «Настройки» — версия PHP, SSL, безопасность и файлы сайта.</div>
      <div v-if="me.demo" class="notice info" style="margin-top:10px">Демо-режим: конфиги веб-сервера не изменяются, все данные фиктивные.</div>
    </template>

    <!-- мастер создания сайта -->
    <WizardCreate :open="wizardOpen" @close="wizardOpen = false" @created="load()" />

    <!-- мастер поддомена -->
    <WizardSubdomain :open="subOpen" :parent-id="subParentId" :parent-domain="subParentDomain"
                     @close="subOpen = false" @created="load()" />

    <!-- импорт сайта архивом -->
    <WizardImport :open="importOpen" @close="importOpen = false" @imported="load()" />

    <!-- заглушка для IP -->
    <AppModal :open="defaultOpen" title="Заглушка для IP-адреса сервера" wide
              @close="defaultOpen = false">
      <div class="notice info">Эта страница открывается при заходе на <b>IP-адрес сервера</b>
        по http и https. Она отдаётся с кодом <b>404</b> и закрыта от индексации
        (X-Robots-Tag + meta robots) — поисковики и сканеры её не сохранят.
        HTML и стили можно менять свободно.</div>
      <div class="field">
        <label>HTML-разметка страницы (placeholder.html)</label>
        <textarea v-model="dsContent" class="mono" rows="18" spellcheck="false"
                  style="width:100%;resize:vertical;white-space:pre;font-size:12.5px"></textarea>
      </div>
      <template #footer>
        <button class="btn primary" @click="defaultSiteSave()">
          <UiIcon name="check" :size="15" /> Сохранить</button>
        <button class="btn" @click="defaultOpen = false">Закрыть</button>
      </template>
    </AppModal>

    <!-- phpMyAdmin установлен: адрес и доступы -->
    <AppModal :open="pmaViewOpen" :title="'phpMyAdmin — ' + pmaViewDomain" wide
              @close="pmaViewOpen = false">
      <template v-if="pmaView">
        <div class="kv"><b>Адрес</b><span class="mono">{{ pmaView.url }}</span></div>
        <div v-if="pmaView.protected" class="field" style="margin-top:8px">
          <label>Вход в папку (basic auth)</label>
          <CredRow k="логин" :v="String(pmaView.user)" />
          <CredRow k="пароль" :v="String(pmaView.password)" />
          <div class="faint" style="font-size:12px">Затем внутри phpMyAdmin — пользователь и пароль MySQL.</div>
        </div>
        <div v-else class="notice warn" style="margin-top:8px">Папка не закрыта паролем — входите сразу пользователем MySQL.</div>
      </template>
      <template #footer>
        <button class="btn primary" @click="pmaSiteOpen(pmaViewDomain)">
          <UiIcon name="ext" :size="15" /> Открыть в новом окне</button>
        <button class="btn" @click="pmaViewOpen = false; router.push({ path: '/software/settings', query: { open: 'pma' } })">Настройки</button>
        <button class="btn danger" @click="pmaRemove(pmaViewDomain)">Удалить</button>
        <button class="btn" @click="pmaViewOpen = false">Закрыть</button>
      </template>
    </AppModal>

    <!-- phpMyAdmin: установка в сайт -->
    <AppModal :open="pmaInstOpen" :title="'Установить phpMyAdmin — ' + pmaInstDomain" wide
              @close="pmaInstOpen = false">
      <div class="notice info">phpMyAdmin — веб-интерфейс для работы с базами данных.
        Скачивается с официального сайта и ставится в папку <b>/pma</b> этого сайта.</div>
      <UiCheckbox v-model="pmaProtect" style="margin:6px 0 4px">
        Закрыть папку паролем (рекомендуется)</UiCheckbox>
      <div v-if="pmaProtect" class="field">
        <PwField v-model="pmaPass" label="Пароль папки /pma"
                 hint="Понадобится при входе в phpMyAdmin. Сохраните его." />
      </div>
      <div class="notice info">Внутри phpMyAdmin входите пользователем базы —
        реквизиты есть в разделе «Базы данных».</div>
      <template #footer>
        <button class="btn primary" @click="pmaSiteInstall()">
          <UiIcon name="down" :size="15" /> Установить</button>
        <button class="btn" @click="pmaInstOpen = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
