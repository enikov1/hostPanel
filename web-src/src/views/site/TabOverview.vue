<script setup lang="ts">
/* ============ Вкладка «Основное» карточки сайта ============
   Настройки сгруппированы в карточки: Основное / Статус и обслуживание /
   Домены и www / Скорость и кеш / Защита админки / Загрузки. */
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
const maintBusy = ref(false);

async function toggleMaintenance(): Promise<void> {
  const s = siteState.site;
  if (!s || maintBusy.value) return; // защита от двойного клика
  maintBusy.value = true;
  try {
    const r = await api('/api/sites/maintenance', { method: 'POST',
      body: { id: s.id, enabled: !s.maintenance } });
    toast(r.message);
    const d = await api('/api/sites');
    const updated = (d.sites || []).find((x: any) => x.id === s.id);
    if (updated) siteState.site = updated;
  } catch (e) { toastErr(e); }
  maintBusy.value = false;
}

/* проверка здоровья сайта (аудит) */
const auditOpen = ref(false);
const auditLoading = ref(false);
const audit = ref<any | null>(null);

async function siteAuditDlg(): Promise<void> {
  const s = siteState.site;
  if (!s || auditLoading.value) return; // защита от двойного клика
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
    <div class="split">
      <!-- Основные -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Основные</span></div>
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
          <UiSelect v-model="siteState.f_webserver"
                    :options="WEBSERVERS.map(w => ({ value: w[0], label: w[1] }))" />
        </div>
        <div class="row" style="flex-wrap:wrap;gap:8px;padding-top:4px">
          <button class="btn" @click="router.push({ path: '/files', query: { path: siteState.site.docroot || '' } })">
            <UiIcon name="folder" :size="15" /> Файлы сайта</button>
          <button class="btn" @click="openSiteUrl(siteState.site.domain)">
            <UiIcon name="ext" :size="15" /> Открыть сайт</button>
        </div>
        <div class="faint" style="font-size:11.5px;margin-top:8px">
          Смена веб-сервера и применение настроек — кнопкой «Сохранить» в шапке.
        </div>
      </div>

      <!-- Статус и обслуживание -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Статус и обслуживание</span></div>
        <UiCheckbox v-model="siteState.f_enabled">
          Сайт включён
          <span class="faint" style="display:block;font-size:12px;margin-top:2px">
            Выключенный сайт показывает посетителям заглушку «Сайт отключён»
            (HTTP 503). Файлы и настройки сохраняются.</span>
        </UiCheckbox>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:10px">
          <button class="btn" :disabled="maintBusy"
                  :class="siteState.site.maintenance ? 'danger' : ''" @click="toggleMaintenance()">
            <UiIcon name="wrench" :size="15" />
            {{ siteState.site.maintenance ? 'Выключить обслуживание' : 'Режим обслуживания (503)' }}</button>
          <button class="btn" :disabled="auditLoading" @click="siteAuditDlg()">
            <UiIcon name="shield" :size="15" /> Проверка здоровья сайта</button>
        </div>
        <div v-if="siteState.site.maintenance" class="notice warn" style="margin-top:10px">
          Сайт сейчас отдаёт HTTP 503 и страницу «ведутся работы».</div>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:10px">
          <button class="btn" @click="subOpen = true">
            <UiIcon name="plus" :size="15" /> Добавить поддомен</button>
        </div>
      </div>
    </div>

    <div class="split" style="margin-top:12px">
      <!-- Домены и www -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Домены и www</span></div>
        <UiCheckbox v-model="siteState.f_www">
          <b>Включить www</b>
          <span class="faint" style="display:block;font-size:12px;margin-top:2px">
            Сайт будет открываться и по www-имени (www.ваш-домен). При сохранении панель
            сама перевыпустит SSL-сертификат с www-именем (Let's Encrypt) —
            придёт уведомление.</span>
        </UiCheckbox>
        <UiCheckbox v-model="siteState.f_snippets.www_redirect">
          <b>Редирект www → без www</b>
          <span class="faint" style="display:block;font-size:12px;margin-top:2px">
            Посетители с www. автоматически попадают на основной домен.</span>
        </UiCheckbox>
        <div class="faint" style="font-size:11.5px;margin-top:6px">
          Для SSL www-имя выдаётся только при включённом «www» выше (для
          поддоменов www не выпускается).
        </div>
      </div>

      <!-- Скорость и кеш -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Скорость и кеш (nginx)</span></div>
        <UiCheckbox v-model="siteState.f_perf.gzip">
          <b>Сжатие ответов (gzip)</b>
          <span class="faint" style="display:block;font-size:12px;margin-top:2px">
            Текстовые страницы и стили отдаются сжатыми — быстрее загрузка.</span>
        </UiCheckbox>
        <UiCheckbox v-if="siteState.origWs !== 'nginx+node'" v-model="siteState.f_perf.static_cache">
          <b>Кеш статики в браузере (30 дней)</b>
          <span class="faint" style="display:block;font-size:12px;margin-top:2px">
            Картинки, стили и скрипты сохраняются в браузере посетителя и не
            качаются повторно.</span>
        </UiCheckbox>
        <template v-if="siteState.origHasSsl">
          <UiCheckbox v-model="siteState.f_perf.hsts">
            <b>HSTS</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Браузер будет ходить на сайт только по HTTPS (включать, когда
              сертификат работает стабильно).</span>
          </UiCheckbox>
          <UiCheckbox v-model="siteState.f_perf.http2">
            <b>HTTP/2</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Ускоряет загрузку современных сайтов при HTTPS.</span>
          </UiCheckbox>
        </template>
      </div>
    </div>

    <div class="split" style="margin-top:12px">
      <!-- Защита админки -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Защита админки по IP</span></div>
        <div class="faint" style="font-size:12px;margin-bottom:8px">
          Панель входа сайта (например /admin или /wp-admin) будет доступна
          только с перечисленных IP-адресов, остальные получат 403.
        </div>
        <div class="field">
          <label>Путь к админке (без слэшей по краям)</label>
          <input v-model="siteState.f_snippets.admin_path" type="text" class="mono"
                 placeholder="admin">
        </div>
        <div class="field">
          <label>Разрешённые IP (через запятую, пусто — защита выключена)</label>
          <input v-model="siteState.f_snippets.admin_ip" type="text" class="mono"
                 placeholder="1.2.3.4, 5.6.7.8">
        </div>
      </div>

      <!-- Загрузки -->
      <div class="card" style="margin:0">
        <div class="card-h"><span class="card-t">Загрузка файлов (nginx)</span></div>
        <div class="field">
          <label>Максимум загрузки файлов (client_max_body_size)</label>
          <UiSelect v-model="siteState.f_snippets.upload_size"
                    :options="['', '64m', '128m', '256m', '512m', '1g', '2g']
                      .map(v => ({ value: v, label: v || 'по умолчанию (64m)' }))" />
          <div class="faint" style="font-size:11.5px;margin-top:4px">
            Ограничение на размер одного загружаемого файла: влияет на загрузку картинок, архивов и импорт дампов.
          </div>
        </div>
        <div class="notice info" style="margin-top:8px">
          Все настройки этой вкладки применяются кнопкой «Сохранить» в шапке:
          конфиг проверяется nginx -t, при ошибке панель откатит изменения сама.
        </div>
      </div>
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
