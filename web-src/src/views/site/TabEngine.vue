<script setup lang="ts">
/* ============ Вкладка «Движок» — установка движка Omro (cld) ============
   Для новичка: карточка с описанием, выбор БД (новая/существующая),
   установка с живым журналом, после установки — статус и токен админки. */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import { fmtSize } from '../../lib/format';
import UiIcon from '../../components/UiIcon.vue';
import UiRadio from '../../components/ui/UiRadio.vue';
import { siteState, openSiteUrl } from './siteShared';

const loading = ref(true);
const installed = ref(false);
const cld = ref<any>(null);
const running = ref(false);
const log = ref<string[]>([]);
const error = ref('');
const taskDone = ref(false);

/* форма установки */
const dbMode = ref<'new' | 'existing'>('new');
const dbName = ref('');
const dbPassword = ref('');
const busy = ref(false);

let pollTimer: ReturnType<typeof setInterval> | null = null;

const siteId = computed(() => siteState.site?.id || 0);
const domain = computed(() => siteState.site?.domain || '');

async function load(): Promise<void> {
  if (!siteId.value) return;
  try {
    const d = await api('/api/site/' + siteId.value + '/cld');
    installed.value = !!(d.cld && d.cld.installed_at) || false;
    cld.value = d.cld || {};
    running.value = !!d.running;
    log.value = d.log || [];
    error.value = d.error || '';
    taskDone.value = !!d.task_done;
  } catch (e) { /* тихо */ }
  loading.value = false;
}

function startPolling(): void {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    load().then(() => {
      if (!running.value && pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
        if (installed.value) toast('Движок Omro установлен!');
      }
    });
  }, 2500);
}

function openInstall(): void {
  error.value = '';
  log.value = [];
  busy.value = false;
  installOpen.value = true;
}

async function doInstall(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    const r = await api('/api/site/' + siteId.value + '/cld/install', {
      method: 'POST',
      body: { db_mode: dbMode.value, db_name: dbName.value || undefined,
              db_password: dbPassword.value || undefined,
              confirm_overwrite: true },
    });
    toast(r.message);
    installOpen.value = false;
    running.value = true;
    log.value = [];
    startPolling();
  } catch (e) { toastErr(e); }
  busy.value = false;
}

const installOpen = ref(false);

/* токен админки: показать/скрыть/копировать */
const tokenVisible = ref(false);
const tokenCopied = ref(false);

async function copyToken(): Promise<void> {
  try {
    await navigator.clipboard.writeText(cld.value.admin_token || '');
    tokenCopied.value = true;
    setTimeout(() => { tokenCopied.value = false; }, 1500);
  } catch (e) { /* нет доступа к буферу */ }
}

onMounted(load);
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer); });
</script>

<template>
  <div>
    <div v-if="loading" class="empty">Загрузка…</div>

    <template v-else>
      <!-- установка идёт -->
      <div v-if="running" class="card">
        <div class="card-h">
          <span class="card-t">Установка движка Omro</span>
          <span class="pill warn" style="margin-left:auto">
            <span class="dot"></span>выполняется</span>
        </div>
        <div class="notice info" style="margin:0 0 8px">
          Установка занимает несколько минут: ставятся зависимости, применяются
          миграции, собираются интерфейсы. Не закрывайте страницу — журнал
          обновляется автоматически.
        </div>
        <div class="logbox" style="max-height:340px">{{ log.join('\n') || '…' }}</div>
      </div>

      <!-- ошибка установки -->
      <div v-else-if="error" class="card">
        <div class="card-h"><span class="card-t">Ошибка установки</span></div>
        <div class="notice err">{{ error }}</div>
        <div class="logbox" style="max-height:240px;margin-top:8px">{{ log.join('\n') }}</div>
        <button class="btn" style="margin-top:10px" @click="load()">
          <UiIcon name="refresh" :size="14" /> Проверить статус</button>
      </div>

      <!-- движок установлен -->
      <div v-else-if="installed" class="card">
        <div class="card-h">
          <span class="card-t">Движок Omro — установлен</span>
          <span class="pill ok" style="margin-left:auto">работает</span>
        </div>
        <div class="kv">
          <b>Сайт</b><span class="mono">{{ domain }}</span>
          <b>Админка</b><span class="mono">https://{{ domain }}/admin/</span>
          <b>База данных</b><span class="mono">{{ cld.db_name }}</span>
          <b>Установлен</b><span>{{ cld.installed_at }}</span>
        </div>
        <div class="field" style="margin-top:10px">
          <label>Токен входа в админку</label>
          <div class="row" style="align-items:center;gap:8px">
            <b class="mono" style="flex:1;word-break:break-all">
              {{ tokenVisible ? (cld.admin_token || '') : '••••••••••••••••' }}</b>
            <button class="btn sm" @click="tokenVisible = !tokenVisible">
              <UiIcon :name="tokenVisible ? 'lock' : 'file'" :size="13" />
              {{ tokenVisible ? 'Скрыть' : 'Показать' }}</button>
            <button class="btn sm" @click="copyToken()">
              <UiIcon :name="tokenCopied ? 'check' : 'file'" :size="13" />
              {{ tokenCopied ? 'Скопировано' : 'Скопировать' }}</button>
          </div>
          <div class="faint" style="font-size:11.5px;margin-top:4px">
            Токен нужен для входа в админку сайта по адресу /admin/.
          </div>
        </div>
        <div class="row" style="flex-wrap:wrap;gap:8px;margin-top:10px">
          <button class="btn" @click="openInstall(); dbMode = 'existing'">
            <UiIcon name="refresh" :size="14" /> Переустановить / обновить</button>
          <button class="btn" @click="openSiteUrl(domain)">
            <UiIcon name="ext" :size="14" /> Открыть сайт</button>
        </div>
        <div class="faint" style="font-size:11.5px;margin-top:8px">
          Обновление движка: переустановка поверх — скрипт подтянет свежую
          версию, данные в базе не пострадают.
        </div>
      </div>

      <!-- не установлен: приглашение + форма -->
      <template v-else>
        <div class="card" style="margin:0 0 12px">
          <div class="card-h">
            <span class="card-t">Движок Omro</span>
            <span class="pill gray" style="margin-left:auto">не установлен</span>
          </div>
          <div style="font-size:13px;line-height:1.65;color:var(--muted)">
            <b style="color:var(--text)">Готовый движок онлайн-каталога:</b>
            фильмы, сериалы, мультфильмы, аниме, дорамы, ТВ-шоу — 7 типов
            контента из коробки. Laravel 12, быстрая тема, админка на React.
            <br><br>
            Установка автоматическая: панель создаст базу данных, передаст
            её движку и переключит сайт на новую веб-корень. Займёт
            несколько минут.
          </div>
          <div class="row" style="margin-top:12px">
            <button class="btn primary" @click="openInstall()">
              <UiIcon name="down" :size="15" /> Установить движок</button>
          </div>
          <div class="faint" style="font-size:11.5px;margin-top:8px">
            Требования: PHP и база данных на сайте (есть у большинства
            сайтов панели). Корневая папка сайта будет занята движком.
          </div>
        </div>

        <!-- форма установки -->
        <div class="card">
          <div class="card-h"><span class="card-t">Установка на сайт {{ domain }}</span></div>

          <div class="g-title">База данных</div>
          <div class="row" style="gap:8px;margin-bottom:8px">
            <UiRadio v-model="dbMode" name="cld-db" value="new">
              Создать новую базу (рекомендуется)</UiRadio>
          </div>
          <div class="row" style="gap:8px;margin-bottom:10px">
            <UiRadio v-model="dbMode" name="cld-db" value="existing">
              Использовать существующую базу</UiRadio>
          </div>

          <template v-if="dbMode === 'new'">
            <div class="field">
              <label>Имя новой базы (можно оставить как есть)</label>
              <input v-model="dbName" type="text" class="mono"
                     :placeholder="'cld_' + (domain.split('.')[0] || 'site')">
              <div class="faint" style="font-size:11.5px;margin-top:4px">
                Панель создаст базу и пользователя с надёжным паролем —
                он сохранится в панели.</div>
            </div>
          </template>
          <template v-else>
            <div class="field">
              <label>Имя существующей базы</label>
              <input v-model="dbName" type="text" class="mono"
                     placeholder="my_database">
            </div>
            <div class="field">
              <label>Пароль пользователя этой базы</label>
              <input v-model="dbPassword" type="password"
                     autocomplete="new-password">
            </div>
          </template>

          <div class="g-title">Важно знать</div>
          <div class="notice warn" style="margin:0 0 10px">
            Корневая папка сайта будет занята движком: скрипт разместит в ней
            файлы Omro (существующие файлы корня могут быть перезаписаны).
            База данных будет заполнена таблицами движка.
          </div>
          <div class="faint" style="font-size:12px;margin-bottom:10px">
            После установки панель переключит сайт на веб-корень движка
            (папка <span class="mono">public/</span>) и перечитает nginx.
            Админка будет доступна по адресу
            <span class="mono">https://{{ domain }}/admin/</span>.
          </div>

          <div class="row">
            <button class="btn primary" :disabled="busy" @click="doInstall()">
              <UiIcon name="down" :size="15" />
              {{ busy ? 'Запускаю…' : 'Установить движок' }}</button>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
