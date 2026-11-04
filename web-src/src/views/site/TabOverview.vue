<script setup lang="ts">
/* ============ Вкладка «Основное» карточки сайта (stMainHtml) ============ */
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import WizardSubdomain from './WizardSubdomain.vue';
import { siteState, openSiteUrl, WEBSERVERS } from './siteShared';

const router = useRouter();

const subOpen = ref(false);

/* режим обслуживания */
async function toggleMaintenance(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  try {
    const r = await api('/api/sites/maintenance', { method: 'POST',
      body: { id: s.id, enabled: !s.maintenance } });
    toast(r.message);
    const d = await api('/api/sites');
    const updated = (d.sites || []).find((x: any) => x.id === s.id);
    if (updated) siteState.site = updated;
  } catch (e) { toastErr(e); }
}

/* проверка здоровья сайта (аудит) */
const auditOpen = ref(false);
const auditLoading = ref(false);
const audit = ref<any | null>(null);

async function siteAuditDlg(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  audit.value = null;
  auditLoading.value = true;
  auditOpen.value = true;
  let r: any;
  try { r = await api('/api/site/' + s.id + '/audit'); }
  catch (e) { auditOpen.value = false; auditLoading.value = false; toastErr(e); return; }
  audit.value = r;
  auditLoading.value = false;
}

function auditPillCls(st: string): string {
  return st === 'ok' ? 'ok' : st === 'warn' ? 'warn' : st === 'fail' ? 'err' : 'gray';
}
function auditPillText(st: string): string {
  return st === 'ok' ? 'ок' : st === 'warn' ? 'внимание' : st === 'fail' ? 'исправить' : '—';
}
</script>

<template>
  <div v-if="siteState.site">
    <div class="field">
      <label>Домен</label>
      <input type="text" :value="siteState.site.domain" disabled>
    </div>
    <div class="field">
      <label>Корневая папка</label>
      <input type="text" :value="siteState.site.docroot || ''" disabled>
    </div>
    <div class="field">
      <label>Веб-сервер</label>
      <select v-model="siteState.f_webserver">
        <option v-for="w in WEBSERVERS" :key="w[0]" :value="w[0]">{{ w[1] }}</option>
      </select>
    </div>
    <label class="check">
      <input v-model="siteState.f_enabled" type="checkbox">
      Сайт включён (при выключении показывает заглушку «Сайт отключён»)</label>
    <label class="check">
      <input v-model="siteState.f_www" type="checkbox">
      Обслуживать www.домен — имя www войдёт в server_name и будет выпрашиваться в сертификате SSL</label>

    <div class="row">
      <button class="btn" @click="router.push({ path: '/files', query: { path: siteState.site.docroot || '' } })">
        <UiIcon name="folder" :size="15" /> Файлы сайта</button>
      <button class="btn" @click="subOpen = true">
        <UiIcon name="plus" :size="15" /> Добавить поддомен</button>
      <button class="btn" @click="openSiteUrl(siteState.site.domain)">
        <UiIcon name="ext" :size="15" /> Открыть сайт</button>
    </div>

    <div class="row" style="margin-top:14px">
      <button class="btn" :class="siteState.site.maintenance ? 'danger' : ''" @click="toggleMaintenance()">
        <UiIcon name="wrench" :size="15" />
        {{ siteState.site.maintenance ? 'Выключить обслуживание' : 'Режим обслуживания (503)' }}</button>
      <button class="btn" @click="siteAuditDlg()">
        <UiIcon name="shield" :size="15" /> Проверка здоровья сайта</button>
    </div>
    <div v-if="siteState.site.maintenance" class="notice warn" style="margin-top:10px">
      Сайт сейчас отдаёт HTTP 503 и страницу «ведутся работы».</div>

    <div class="g-title">Производительность (настройки nginx)</div>
    <label class="check">
      <input v-model="siteState.f_perf.gzip" type="checkbox">
      Сжатие ответов (gzip) — страницы отдаются быстрее</label>
    <label v-if="siteState.origWs !== 'nginx+node'" class="check">
      <input v-model="siteState.f_perf.static_cache" type="checkbox">
      Кэш картинок и стилей в браузере (30 дней)</label>
    <template v-if="siteState.origHasSsl">
      <label class="check">
        <input v-model="siteState.f_perf.hsts" type="checkbox">
        HSTS — браузер будет ходить на сайт только по HTTPS</label>
      <label class="check">
        <input v-model="siteState.f_perf.http2" type="checkbox">
        HTTP/2 — ускорение загрузки при HTTPS</label>
    </template>
    <div class="faint" style="font-size:11.5px;margin-top:4px">Применится после «Сохранить». Конфиг проверяется nginx -t — при ошибке панель откатит изменения сама.</div>

    <div class="g-title">Библиотека сниппетов (nginx)</div>
    <label class="check">
      <input v-model="siteState.f_snippets.www_redirect" type="checkbox"> Редирект www → без www</label>
    <div class="field" style="margin:6px 0 0">
      <label>Закрыть /admin по IP (через запятую, пусто — выключено)</label>
      <input v-model="siteState.f_snippets.admin_ip" type="text" class="mono" placeholder="1.2.3.4, 5.6.7.8">
    </div>
    <div class="field" style="margin:6px 0 0">
      <label>Максимум загрузки файлов (client_max_body_size)</label>
      <select v-model="siteState.f_snippets.upload_size">
        <option v-for="v in ['', '64m', '128m', '256m', '512m', '1g', '2g']" :key="v" :value="v">
          {{ v || 'по умолчанию (64m)' }}</option>
      </select>
    </div>

    <!-- мастер поддомена -->
    <WizardSubdomain :open="subOpen" :parent-id="siteState.site.id" :parent-domain="siteState.site.domain"
                     @close="subOpen = false" />

    <!-- проверка здоровья -->
    <AppModal :open="auditOpen" :title="'Проверка здоровья: ' + siteState.site.domain" wide
              @close="auditOpen = false">
      <div v-if="auditLoading" class="empty">Проверяю: HTTPS, редирект, сжатие, кэш, PHP…</div>
      <template v-else-if="audit">
        <div class="row" style="align-items:center;gap:12px;margin-bottom:6px">
          <span class="pill" :class="audit.score >= 80 ? 'ok' : audit.score >= 50 ? 'warn' : 'err'"
                style="font-size:14px">оценка: {{ audit.score }}/100</span>
          <span v-if="audit.demo" class="pill gray">демо-режим</span>
          <span class="muted" style="font-size:12.5px">проверено: {{ audit.checks.length }}</span>
        </div>
        <div v-for="(c, i) in audit.checks" :key="i" class="row"
             style="align-items:flex-start;gap:12px;padding:9px 0;border-bottom:1px solid var(--border)">
          <div style="width:96px;flex-shrink:0">
            <span class="pill" :class="auditPillCls(c.status)">{{ auditPillText(c.status) }}</span>
          </div>
          <div style="flex:1">
            <b>{{ c.name }}</b>
            <div v-if="c.detail" class="muted" style="font-size:12.5px">{{ c.detail }}</div>
            <div v-if="c.hint" class="notice info" style="margin-top:6px;font-size:12.5px">{{ c.hint }}</div>
          </div>
        </div>
      </template>
      <template #footer>
        <button class="btn primary" @click="auditOpen = false">Понятно</button>
      </template>
    </AppModal>
  </div>
</template>
