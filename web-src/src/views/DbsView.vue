<script lang="ts">
/* Модульное состояние, живущее между заходами на страницу (как в старом ts-src). */
import { ref as moduleRef } from 'vue';

let dbFilterSaved = 'all';
const sqlHist = moduleRef<string[]>([]);
</script>

<script setup lang="ts">
/* ============ Страница «Базы данных» (старый id 'dbs') ============ */
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { api, apiForm, downloadFile } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtSize } from '../lib/format';
import { genPassword } from '../lib/pw';
import { me } from '../stores';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';
import PwField from '../components/PwField.vue';
import CredRow from '../components/CredRow.vue';
import CodeEditor from '../components/CodeEditor.vue';

const router = useRouter();

interface DbEngine { id: string; name: string; available: boolean }
interface DbRow { name: string; engine?: string; user?: string; tables?: number; size_bytes?: number }

const loading = ref(true);
const failed = ref(false);
const engines = ref<DbEngine[]>([]);
const dbs = ref<DbRow[]>([]);

const dbFilter = ref(dbFilterSaved);

const avail = computed(() => engines.value.filter((e) => e.available));
const filt = computed(() => {
  const f = dbFilter.value;
  return f === 'all' || avail.value.some((e) => e.id === f) ? f : 'all';
});
const filtered = computed(() =>
  dbs.value.filter((x) => filt.value === 'all' || (x.engine || 'mysql') === filt.value));

function engName(id?: string): string {
  const e = engines.value.find((x) => x.id === (id || 'mysql'));
  return e ? e.name : (id || 'mysql');
}

function setFilter(f: string): void {
  dbFilter.value = f;
  dbFilterSaved = f;
}

async function load(): Promise<void> {
  try {
    const d = await api('/api/db');
    engines.value = d.engines || [];
    dbs.value = d.dbs || [];
    failed.value = false;
  } catch (e) {
    failed.value = true;
    toastErr(e);
  }
  loading.value = false;
}

onMounted(() => { void load(); });

/* ---------- создание базы ---------- */
const crtDlg = ref(false);
const crtEngine = ref('mysql');
const crtName = ref('');
const crtUser = ref('');
const crtPass = ref('');
const crtNameEl = ref<HTMLInputElement | null>(null);

function dbCreateDlg(engine?: string): void {
  const av = avail.value;
  if (!av.length) return;
  const cur = engine || dbFilter.value || 'mysql';
  crtEngine.value = av.some((x) => x.id === cur) ? cur : av[0].id;
  const auto = 'db_' + Math.random().toString(36).slice(2, 7);
  crtName.value = auto;
  crtUser.value = auto + '_u';
  crtPass.value = genPassword();
  crtDlg.value = true;
  void nextTick();
  setTimeout(() => { crtNameEl.value?.select(); }, 60);
}

const credsDlg = ref(false);
const creds = ref<{ name: string; user: string; pass: string; engine: string } | null>(null);

async function dbCreate(): Promise<void> {
  const name = crtName.value.trim(), user = crtUser.value.trim(),
        pass = crtPass.value, engine = crtEngine.value;
  try {
    await api('/api/db/create', { method: 'POST', body: { name, user, password: pass, engine } });
    crtDlg.value = false;
    creds.value = { name, user, pass, engine };
    credsDlg.value = true;
    void load();
  } catch (e) { toastErr(e); }
}

function credsDone(): void {
  credsDlg.value = false;
}

function credsToSites(): void {
  credsDlg.value = false;
  router.push('/sites');
}

/* ---------- импорт SQL-дампа в базу ---------- */
const impDlg = ref(false);
const impName = ref('');
const impEngine = ref('mysql');
const impFileEl = ref<HTMLInputElement | null>(null);
const impOut = ref<{ kind: 'ok' | 'err'; msg: string } | null>(null);
const impBusy = ref(false);

function dbImportDlg(name: string, engine: string): void {
  impName.value = name;
  impEngine.value = engine;
  impOut.value = null;
  impDlg.value = true;
}

async function dbImportRun(): Promise<void> {
  const inp = impFileEl.value;
  if (!inp || !inp.files || !inp.files.length) { toast('выберите файл дампа', 'warn'); return; }
  impOut.value = null;
  impBusy.value = true;
  const fd = new FormData();
  fd.append('name', impName.value);
  fd.append('engine', impEngine.value);
  fd.append('file', inp.files[0]);
  try {
    const j = await apiForm('/api/db/import', fd);
    impOut.value = { kind: 'ok', msg: j.message || 'готово' };
    setTimeout(() => { impDlg.value = false; void load(); }, 1500);
  } catch (e: any) {
    impOut.value = { kind: 'err', msg: e.message || String(e) };
  }
  impBusy.value = false;
}

/* ---------- смена пароля пользователя базы ---------- */
const pwDlg = ref(false);
const pwName = ref('');
const pwEngine = ref('mysql');
const pwUsers = ref<string[]>([]);
const pwUser = ref('');
const pwNew = ref('');

const pwDoneDlg = ref(false);
const pwDone = ref<{ name: string; user: string; pass: string } | null>(null);

async function dbPassDlg(name: string, engine?: string): Promise<void> {
  pwEngine.value = engine || 'mysql';
  pwName.value = name;
  let users: string[] = [];
  try {
    users = (await api('/api/db/users?name=' + encodeURIComponent(name) +
      '&engine=' + encodeURIComponent(pwEngine.value))).users || [];
  } catch (e) { /* тихо — как в исходнике */ }
  if (!users.length) users = [name.replace(/[^\w]/g, '').slice(0, 14) + '_u'];
  pwUsers.value = users;
  pwUser.value = users[0];
  pwNew.value = genPassword();
  pwDlg.value = true;
}

async function dbPassSave(): Promise<void> {
  try {
    await api('/api/db/pass', { method: 'POST', body: {
      name: pwName.value,
      user: pwUser.value,
      password: pwNew.value,
      engine: pwEngine.value } });
    pwDone.value = { name: pwName.value, user: pwUser.value, pass: pwNew.value };
    pwDlg.value = false;
    pwDoneDlg.value = true;
  } catch (e) { toastErr(e); }
}

/* ---------- SQL-консоль (MariaDB / PostgreSQL) ---------- */
const sqlDlg = ref(false);
const sqlDbs = ref<DbRow[]>([]);
const sqlDb = ref('');
const sqlEngine = ref('mysql');
const sqlText = ref('');
const sqlHistSel = ref('');
const sqlOut = ref<{ kind: 'busy' | 'ok' | 'err'; info?: string;
  columns?: string[]; rows?: unknown[][] } | null>(null);
let sqlConfirmed = false;

async function dbSqlDlg(db?: string, engine?: string): Promise<void> {
  if (!engine && !db) {
    engine = (avail.value[0] || ({} as DbEngine)).id || 'mysql';
  }
  let all: DbRow[] = [];
  try { all = (await api('/api/db')).dbs || []; } catch (e) { /* тихо */ }
  if (db && !engine) {
    const row = all.find((x) => x.name === db);
    engine = row ? (row.engine || 'mysql') : 'mysql';
  }
  let list: DbRow[] = engine ? all.filter((x) => (x.engine || 'mysql') === engine) : all;
  if (db) list = [{ name: db, engine: engine || 'mysql' } as DbRow].concat(list);
  if (!list.length) { toastErr(new Error('базы данных не найдены')); return; }
  if (!engine) engine = list[0].engine || 'mysql';
  sqlEngine.value = engine;
  sqlDbs.value = list;
  sqlDb.value = db || list[0].name;
  sqlText.value = db
    ? (engine === 'pg'
        ? "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
        : 'SHOW TABLES;')
    : (engine === 'pg' ? 'SELECT version();' : 'SELECT 1;');
  sqlHistSel.value = '';
  sqlOut.value = null;
  sqlDlg.value = true;
}

function sqlHistPick(): void {
  sqlText.value = sqlHist.value[+sqlHistSel.value] || '';
}

function sqlKey(e: KeyboardEvent): void {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    void dbSqlRun();
  }
}

async function dbSqlRun(): Promise<void> {
  const db = sqlDb.value;
  const sql = sqlText.value.trim();
  if (!sql) { toast('пустой запрос', 'warn'); return; }
  if (/^\s*(DROP|TRUNCATE|DELETE|UPDATE|ALTER|RENAME)\b/i.test(sql) && !sqlConfirmed) {
    confirmDlg('Опасная операция',
      'Запрос «' + sql.slice(0, 80) + '» изменяет или удаляет данные. Выполнить?',
      () => { sqlConfirmed = true; void dbSqlRun(); setTimeout(() => { sqlConfirmed = false; }, 500); });
    return;
  }
  sqlOut.value = { kind: 'busy' };
  try {
    const r = await api('/api/db/query',
      { method: 'POST', body: { db, sql, engine: sqlEngine.value || 'mysql' } });
    sqlHist.value = [sql].concat(sqlHist.value.filter((q) => q !== sql)).slice(0, 15);
    if (r.columns && r.columns.length) {
      sqlOut.value = { kind: 'ok', info: r.info, columns: r.columns, rows: r.rows };
    } else {
      sqlOut.value = { kind: 'ok', info: r.info || 'выполнено' };
    }
  } catch (e: any) {
    sqlOut.value = { kind: 'err', info: e.message || String(e) };
  }
}

/* ---------- удаление базы ---------- */
function dbDel(name: string, engine: string): void {
  confirmDlg('Удалить базу', 'База «' + name + '» и её данные будут удалены безвозвратно.',
    async () => {
      try {
        const r = await api('/api/db/delete',
          { method: 'POST', body: { name, engine: engine || 'mysql' } });
        toast(r.message || 'готово');
        void load();
      } catch (e) { toastErr(e); }
    });
}
</script>

<template>
  <div v-table>
    <div v-if="loading" class="empty">Загрузка…</div>

    <!-- ни одной установленной СУБД -->
    <template v-else-if="!failed && !avail.length">
      <div class="hintbox">
        <UiIcon name="db" :size="16" />
        <div>База данных — это «хранилище», куда сайт складывает свою информацию:
          товары, записи, пользователей. Она нужна большинству сайтов
          (интернет-магазины, блоги, форумы).</div>
      </div>
      <div class="card" style="text-align:center;padding:46px 20px">
        <div class="empty" style="padding:0 0 14px">
          Сервер баз данных (MariaDB или PostgreSQL) ещё не установлен</div>
        <button class="btn primary" @click="router.push('/software')">
          Перейти в «Установка ПО»</button>
      </div>
    </template>

    <template v-else-if="!failed">
      <div class="hintbox">
        <UiIcon name="db" :size="16" />
        <div><b>Что такое база данных?</b> Это хранилище, куда сайт складывает свою
          информацию: товары, записи, пользователей. При установке сайта
          (WordPress, магазин и т.п.) вас попросят указать имя базы, пользователя
          и пароль — они появятся после нажатия кнопки «Создать базу». Здесь можно
          работать и с MariaDB, и с PostgreSQL.</div>
      </div>

      <div class="toolbar">
        <button class="btn primary" @click="dbCreateDlg()">
          <UiIcon name="plus" :size="15" />Создать базу</button>
        <button class="btn" @click="dbSqlDlg()">
          <UiIcon name="term" :size="15" /> SQL-консоль</button>
      </div>

      <div class="row" style="gap:8px;margin:0 0 10px;flex-wrap:wrap">
        <button class="btn sm" :class="{ primary: filt === 'all' }" @click="setFilter('all')">
          Все ({{ dbs.length }})</button>
        <button v-for="e in avail" :key="e.id" class="btn sm"
                :class="{ primary: filt === e.id }" @click="setFilter(e.id)">
          {{ e.name }} ({{ dbs.filter((x) => (x.engine || 'mysql') === e.id).length }})</button>
        <span v-for="e in engines.filter((x) => !x.available)" :key="e.id"
              class="pill warn" style="cursor:pointer"
              title="Установить в разделе «Установка ПО»"
              @click="router.push('/software')">{{ e.name }} не установлен — установить</span>
      </div>

      <template v-if="filtered.length">
        <div class="card" style="padding:6px 10px">
          <div class="twrap"><table>
            <thead><tr>
              <th>Название</th><th>СУБД</th><th>Пользователь</th>
              <th>Таблиц</th><th>Размер</th><th></th>
            </tr></thead>
            <tbody>
              <tr v-for="db in filtered" :key="(db.engine || 'mysql') + ':' + db.name">
                <td><b class="mono">{{ db.name }}</b></td>
                <td><span class="pill" :class="(db.engine || 'mysql') === 'pg' ? 'info' : 'gray'">
                  {{ engName(db.engine || 'mysql') }}</span></td>
                <td>
                  <span v-if="db.user" class="mono">{{ db.user }}</span>
                  <span v-else class="faint">—</span>
                </td>
                <td>{{ db.tables || 0 }}</td>
                <td>{{ fmtSize(db.size_bytes) }}</td>
                <td>
                  <div class="actions-cell">
                    <button class="btn sm" title="Скачать дамп базы (.sql)"
                            @click="downloadFile('/api/db/export?name=' + encodeURIComponent(db.name) +
                              '&engine=' + encodeURIComponent(db.engine || 'mysql'), db.name + '.sql')">
                      <UiIcon name="down" :size="14" /> Экспорт</button>
                    <button class="btn sm" title="Загрузить SQL-файл в базу"
                            @click="dbImportDlg(db.name, db.engine || 'mysql')">
                      <UiIcon name="up" :size="14" /> Импорт</button>
                    <button class="btn sm" title="Изменить пароль"
                            @click="dbPassDlg(db.name, db.engine || 'mysql')">
                      <UiIcon name="lock" :size="14" /> Пароль</button>
                    <button v-if="me.expert" class="btn sm" title="SQL-запросы к базе"
                            @click="dbSqlDlg(db.name, db.engine || 'mysql')">
                      <UiIcon name="term" :size="14" /> SQL</button>
                    <button class="btn sm icon danger" title="Удалить базу"
                            @click="dbDel(db.name, db.engine || 'mysql')">
                      <UiIcon name="trash" :size="14" /></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table></div>
        </div>
        <div class="faint" style="font-size:12px;margin-top:10px">
          Экспорт скачивает дамп базы в файл .sql — его можно отдать разработчику
          или залить на другой сервер. Импорт выполняет SQL-файл (.sql, .sql.gz, .zip)
          в выбранную базу — так переносят сайт с другого хостинга.</div>
      </template>

      <div v-else class="card" style="text-align:center;padding:46px 20px">
        <div class="empty" style="padding:0 0 14px">
          <template v-if="filt === 'all'">Пока нет ни одной базы данных.<br>
            Если вашему сайту нужна база (например, для WordPress) — создайте её здесь.</template>
          <template v-else>Баз {{ engName(filt) }} пока нет.</template>
        </div>
        <button class="btn primary"
                @click="dbCreateDlg(filt === 'all' ? (avail[0] && avail[0].id || 'mysql') : filt)">
          <UiIcon name="plus" :size="15" />Создать базу</button>
      </div>
    </template>

    <!-- ======== новая база данных ======== -->
    <AppModal :open="crtDlg" title="Новая база данных" @close="crtDlg = false">
      <div v-if="avail.length > 1" class="field">
        <label>Тип СУБД</label>
        <label v-for="e in avail" :key="e.id" class="check" style="margin:4px 0">
          <input v-model="crtEngine" type="radio" name="db-eng" :value="e.id"> {{ e.name }}
          <span v-if="e.id === 'pg'" class="faint">— например, для 1С-Битрикс24 или приложений на Django</span>
        </label>
      </div>
      <div v-else class="faint" style="font-size:12px;margin-bottom:8px">
        СУБД: <b>{{ avail[0] ? avail[0].name : 'MariaDB' }}</b>
        <template v-if="avail.length === 1 && avail[0].id === 'mysql'">
          (PostgreSQL можно установить в разделе «Установка ПО»)</template>
      </div>
      <div class="field">
        <label>Название базы (латиница, цифры, _)</label>
        <input ref="crtNameEl" v-model="crtName" type="text" class="mono"
               placeholder="например, shop_db">
      </div>
      <div class="field">
        <label>Пользователь</label>
        <input v-model="crtUser" type="text" class="mono" placeholder="например, shop_user">
      </div>
      <PwField v-model="crtPass" label="Пароль базы"
               hint="Пароль понадобится при установке сайта (например, WordPress). Скопируйте его кнопкой справа." />
      <template #footer>
        <button class="btn primary" @click="dbCreate()">Создать</button>
        <button class="btn" @click="crtDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- ======== реквизиты созданной базы ======== -->
    <AppModal :open="credsDlg"
              :title="'База «' + (creds ? creds.name : '') + '» создана'"
              @close="credsDlg = false">
      <template v-if="creds">
        <div class="notice ok">Готово! Скопируйте эти данные — они нужны при установке сайта.</div>
        <CredRow k="СУБД" :v="engName(creds.engine || 'mysql')" />
        <CredRow k="Сервер (хост)" v="localhost" />
        <CredRow k="Название базы" :v="creds.name" />
        <CredRow k="Пользователь" :v="creds.user" />
        <CredRow k="Пароль" :v="creds.pass" />
        <div class="hintbox" style="margin-top:12px">
          <UiIcon name="check" :size="16" />
          <div><b>Что дальше?</b> Создайте сайт в разделе «Сайты» и при установке
            (например, WordPress) введите эти данные в шаге настройки базы.</div>
        </div>
      </template>
      <template #footer>
        <button class="btn primary" @click="credsDone()">Готово</button>
        <button class="btn" @click="credsToSites()">Создать сайт →</button>
      </template>
    </AppModal>

    <!-- ======== импорт дампа ======== -->
    <AppModal :open="impDlg" :title="'Импорт в базу «' + impName + '»'" :wide="true"
              @close="impDlg = false">
      <div class="notice warn">Содержимое SQL-файла будет выполнено в базе
        «<b>{{ impName }}</b>»: существующие таблицы с теми же именами будут
        перезаписаны. Сначала сделайте экспорт текущей базы.</div>
      <div class="field">
        <label>Файл дампа (.sql, .sql.gz, .zip — до 200 МБ)</label>
        <input ref="impFileEl" type="file" accept=".sql,.gz,.zip">
      </div>
      <div v-if="impBusy" class="empty">Импортирую — не закрывайте окно…</div>
      <div v-else-if="impOut" class="notice" :class="impOut.kind">{{ impOut.msg }}</div>
      <template #footer>
        <button class="btn primary" :disabled="impBusy" @click="dbImportRun()">
          <UiIcon name="up" :size="15" /> Импортировать</button>
        <button class="btn" @click="impDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- ======== пароль базы ======== -->
    <AppModal :open="pwDlg"
              :title="'Пароль базы «' + pwName + '» — ' + engName(pwEngine)"
              @close="pwDlg = false">
      <div class="field">
        <label>Пользователь</label>
        <select v-model="pwUser">
          <option v-for="u in pwUsers" :key="u" :value="u">{{ u }}</option>
        </select>
      </div>
      <PwField v-model="pwNew" label="Новый пароль"
               hint="После смены пароля обновите его в настройках сайта, который использует эту базу — иначе сайт потеряет доступ." />
      <template #footer>
        <button class="btn primary" @click="dbPassSave()">Изменить пароль</button>
        <button class="btn" @click="pwDlg = false">Отмена</button>
      </template>
    </AppModal>

    <!-- ======== пароль изменён ======== -->
    <AppModal :open="pwDoneDlg" title="Пароль изменён" @close="pwDoneDlg = false">
      <template v-if="pwDone">
        <div class="notice ok">Новый пароль для базы
          <b class="mono">{{ pwDone.name }}</b> сохранён.</div>
        <CredRow k="Пользователь" :v="pwDone.user" />
        <CredRow k="Новый пароль" :v="pwDone.pass" />
        <div class="hintbox" style="margin-top:12px">
          <UiIcon name="lock" :size="16" />
          <div>Скопируйте пароль и обновите его в файле конфигурации вашего сайта
            (например, wp-config.php у WordPress).</div>
        </div>
      </template>
      <template #footer>
        <button class="btn primary" @click="pwDoneDlg = false">Готово</button>
      </template>
    </AppModal>

    <!-- ======== SQL-консоль ======== -->
    <AppModal :open="sqlDlg"
              :title="'SQL-консоль — ' + (sqlEngine === 'pg' ? 'PostgreSQL' : 'MySQL')"
              :wide="true" @close="sqlDlg = false">
      <div class="row">
        <div class="field" style="flex:1">
          <label>База данных</label>
          <select v-model="sqlDb">
            <option v-for="x in sqlDbs" :key="(x.engine || 'mysql') + ':' + x.name" :value="x.name">
              {{ x.name }}{{ (x.engine || 'mysql') !== sqlEngine
                ? ' · ' + engName(x.engine || 'mysql') : '' }}</option>
          </select>
        </div>
        <div v-if="sqlHist.length" class="field" style="flex:1">
          <label>История</label>
          <select v-model="sqlHistSel" @change="sqlHistPick()">
            <option value="">—</option>
            <option v-for="(q, i) in sqlHist" :key="i" :value="String(i)">
              {{ q.slice(0, 60) }}{{ q.length > 60 ? '…' : '' }}</option>
          </select>
        </div>
      </div>
      <CodeEditor v-model="sqlText" lang="sql" @keydown="sqlKey" />
      <div class="faint" style="font-size:11.5px;margin-top:6px">
        Ctrl+Enter — выполнить. Запросы выполняются от
        {{ sqlEngine === 'pg' ? 'администратора PostgreSQL (postgres)' : 'root MySQL' }}.</div>
      <div style="margin-top:10px">
        <div v-if="sqlOut && sqlOut.kind === 'busy'" class="empty">Выполняется…</div>
        <template v-else-if="sqlOut && sqlOut.kind === 'ok'">
          <div class="notice ok" style="margin-bottom:8px">{{ sqlOut.info }}</div>
          <div v-if="sqlOut.columns && sqlOut.columns.length"
               class="twrap" style="max-height:300px;overflow:auto">
            <table>
              <thead><tr>
                <th v-for="c in sqlOut.columns" :key="c" class="mono">{{ c }}</th>
              </tr></thead>
              <tbody>
                <tr v-for="(row, ri) in sqlOut.rows" :key="ri">
                  <td v-for="(cell, ci) in row" :key="ci" class="mono">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else-if="sqlOut && sqlOut.kind === 'err'" class="notice err">{{ sqlOut.info }}</div>
      </div>
      <template #footer>
        <button class="btn primary" @click="dbSqlRun()">
          <UiIcon name="check" :size="15" /> Выполнить</button>
        <button class="btn" @click="sqlDlg = false">Закрыть</button>
      </template>
    </AppModal>
  </div>
</template>
