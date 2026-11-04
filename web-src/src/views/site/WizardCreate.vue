<script setup lang="ts">
/* ============ Мастер создания сайта ( wizardSite + wizardCreate ) ============ */
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import AppModal from '../../components/AppModal.vue';
import CredRow from '../../components/CredRow.vue';
import UiSelect from '../../components/ui/UiSelect.vue';
import UiCheckbox from '../../components/ui/UiCheckbox.vue';
import { WEBSERVERS, openSiteUrl } from './siteShared';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; created: [siteId: number, domain: string] }>();

const router = useRouter();

/* данные для формы */
const phpVersions = ref<string[]>([]);
const engines = ref<any[]>([]);

/* поля формы */
const domain = ref('');
const www = ref(false);
const ws = ref('nginx');
const php = ref('');
const nodeV = ref('20');
const nodeP = ref(3000);
const nodeS = ref('app.js');
const sslKind = ref('none');
const email = ref('');
const createDb = ref(true);
const dbEng = ref('');

const createdOpen = ref(false);
const createdDomain = ref('');
const createdSiteId = ref(0);
const createdDb = ref<any | null>(null);

const phpBlock = computed(() => ws.value === 'nginx' || ws.value === 'nginx+apache' || ws.value === 'apache');
const nodeBlock = computed(() => ws.value === 'nginx+node');
const engBlock = computed(() => createDb.value && engines.value.length > 1);

async function loadOptions(): Promise<void> {
  let vers: Record<string, string[]> = {}, eng: any[] = [];
  try {
    const res = await Promise.all([
      api('/api/php').catch(() => ({ versions: {} })),
      api('/api/db').then((x: any) => x.engines || []).catch(() => [])]);
    vers = res[0].versions || {}; eng = res[1];
  } catch (e) { vers = {}; eng = []; }
  phpVersions.value = Object.keys(vers).sort().reverse();
  engines.value = (eng || []).filter((e) => e.available);
  php.value = phpVersions.value[0] || '';
  dbEng.value = engines.value[0] ? engines.value[0].id : 'mysql';
}

function resetForm(): void {
  domain.value = ''; www.value = false; ws.value = 'nginx';
  sslKind.value = 'none'; email.value = ''; createDb.value = true;
  nodeV.value = '20'; nodeP.value = 3000; nodeS.value = 'app.js';
  createdOpen.value = false;
  void loadOptions();
}

async function create(): Promise<void> {
  const body = {
    domain: domain.value.trim(),
    webserver: ws.value,
    www: www.value,
    php: php.value,
    ssl_kind: sslKind.value,
    email: email.value,
    create_db: createDb.value,
    db_engine: dbEng.value || (engines.value[0] ? engines.value[0].id : 'mysql'),
    node_version: nodeV.value,
    node_port: Number(nodeP.value) || 3000,
    node_script: nodeS.value,
  };
  let r: any;
  try { r = await api('/api/sites/create', { method: 'POST', body }); }
  catch (e) { toastErr(e); return; }
  createdDomain.value = body.domain;
  createdSiteId.value = r.site_id || 0;
  createdDb.value = r.db || null;
  createdOpen.value = true;
  emit('created', createdSiteId.value, createdDomain.value);
}

watch(() => props.open, (v) => { if (v) resetForm(); });
</script>

<template>
  <AppModal :open="open && !createdOpen" title="Новый сайт" wide @close="emit('close')">
    <div class="field">
      <label>Домен (адрес сайта)</label>
      <input v-model="domain" type="text" placeholder="например, mysite.ru" autofocus>
    </div>
    <UiCheckbox v-model="www"> Обслуживать также адрес с www
      (www.домен войдёт в server_name и в сертификат SSL)</UiCheckbox>
    <div class="field">
      <label>На чём работает сайт</label>
      <UiSelect v-model="ws" :options="WEBSERVERS.map(w => ({ value: w[0], label: w[1] }))" />
      <div class="faint" style="font-size:11.5px;margin-top:4px">Если не знаете, что выбрать — оставьте как есть.</div>
    </div>
    <div v-if="phpBlock" class="field">
      <label>Версия PHP</label>
      <UiSelect v-model="php" :options="phpVersions.map(v => ({ value: v, label: 'PHP ' + v }))" />
    </div>
    <div v-if="nodeBlock">
      <div class="row">
        <div class="field" style="flex:1"><label>Версия Node.js</label>
          <UiSelect v-model="nodeV"
                    :options="[{ value: '20', label: '20' }, { value: '18', label: '18' }, { value: '22', label: '22' }]" /></div>
        <div class="field" style="flex:1"><label>Порт приложения</label>
          <input v-model.number="nodeP" type="number"></div>
        <div class="field" style="flex:1"><label>Файл запуска</label>
          <input v-model="nodeS" type="text"></div>
      </div>
    </div>
    <div class="field">
      <label>Защита соединения (SSL)</label>
      <UiSelect v-model="sslKind"
                :options="[{ value: 'none', label: 'Пока без SSL — можно включить позже' },
                  { value: 'letsencrypt', label: 'Бесплатный сертификат Let\'s Encrypt (нужен работающий домен)' },
                  { value: 'selfsigned', label: 'Самоподписанный (для тестов)' }]" />
    </div>
    <div v-if="sslKind === 'letsencrypt'" class="field">
      <label>E-mail для сертификата</label>
      <input v-model="email" type="email" placeholder="admin@example.ru">
    </div>
    <UiCheckbox v-model="createDb">
      Создать базу данных (нужна для WordPress, магазинов и т.п.)</UiCheckbox>
    <div v-if="engBlock" class="field">
      <label>Тип базы</label>
      <UiSelect v-model="dbEng" :options="engines.map(e => ({ value: e.id, label: e.name }))" />
      <div class="faint" style="font-size:11.5px;margin-top:4px">MariaDB подходит большинству сайтов (WordPress, Opencart); PostgreSQL — если приложение требует именно её.</div>
    </div>
    <div class="notice info">Всё остальное — папка сайта, настройки веб-сервера — создастся автоматически.</div>
    <template #footer>
      <button class="btn primary" @click="create()"><UiIcon name="check" :size="15" /> Создать сайт</button>
      <button class="btn" @click="emit('close')">Отмена</button>
    </template>
  </AppModal>

  <!-- сайт создан -->
  <AppModal :open="createdOpen" :title="'Сайт «' + createdDomain + '» создан'" wide
            @close="createdOpen = false; emit('close')">
    <div class="notice ok">Сайт готов и уже работает. Что можно сделать дальше:</div>
    <template v-if="createdDb">
      <div class="notice ok" style="margin-top:8px">Вместе с сайтом создана база данных — сохраните реквизиты:</div>
      <CredRow k="СУБД" :v="createdDb.engine === 'pg' ? 'PostgreSQL' : 'MariaDB / MySQL'" />
      <CredRow k="Название базы" :v="String(createdDb.name)" />
      <CredRow k="Пользователь" :v="String(createdDb.user)" />
      <CredRow k="Пароль" :v="String(createdDb.password)" />
      <div class="faint" style="font-size:12px;margin:4px 0 10px">Сервер (хост): <b class="mono">localhost</b></div>
    </template>
    <div class="kv" style="margin:8px 0 4px">
      <b>Файлы сайта</b><span>раздел «Файловый менеджер» — загрузите туда файлы вашего сайта</span>
      <b>Защита (SSL)</b><span>в настройках сайта включите бесплатный сертификат — тогда сайт будет открываться по https://</span>
      <b>Домен</b><span>настройте у регистратора A-запись домена на IP этого сервера</span>
    </div>
    <template #footer>
      <button class="btn primary" @click="createdOpen = false; emit('close'); openSiteUrl(createdDomain)">
        <UiIcon name="ext" :size="15" /> Открыть сайт</button>
      <button class="btn" @click="createdOpen = false; emit('close'); router.push('/files')">Загрузить файлы</button>
      <button v-if="createdSiteId" class="btn"
              @click="createdOpen = false; emit('close'); router.push('/sites/' + createdSiteId)">Настройки сайта</button>
      <button class="btn" @click="createdOpen = false; emit('close')">Готово</button>
    </template>
  </AppModal>
</template>
