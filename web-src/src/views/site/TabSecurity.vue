<script setup lang="ts">
/* ============ Вкладка «Фильтры» (WAF-модуль) карточки сайта ============
   Полноценный фильтр трафика на уровне nginx:
   гео-страны (два независимых списка с поиском и флагами),
   чёрный/белый список IP, боты (категории + свои UA-правила),
   источники (Referer), анализ из логов, WAF и rate-limit. */
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import type { PropType, VNode } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import UiSelect from '../../components/ui/UiSelect.vue';
import UiCheckbox from '../../components/ui/UiCheckbox.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const secTab = ref('geo');
const err = ref('');
const geoAvailable = ref(true);
const countries = ref<Record<string, string>>({});
const botCats = ref<Record<string, { name: string; desc: string }>>({});

interface UaRule { pattern: string; note: string }

const sec = reactive({
  geo_allow: [] as string[],
  geo_deny: [] as string[],
  ip_allow: [] as string[],
  ip_deny: [] as string[],
  block_bots: false,
  waf: false,
  rate_limit: 0,
  rate_burst: 20,
  ua_categories: [] as string[],
  ua_rules: [] as UaRule[],
  block_empty_ua: false,
  ref_block: [] as string[],
  ref_allow: [] as string[],
  block_empty_ref: false,
});

/* ---------- флаг страны из ISO-кода (региональные индикаторы) ---------- */
function flagEmoji(code: string): string {
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((c) => 0x1F1E6 + c.charCodeAt(0) - 65));
}

/* ---------- инлайн-компонент: поиск страны с флагами ---------- */
const CountryPicker = defineComponent({
  name: 'CountryPicker',
  props: {
    codes: { type: Array as PropType<string[]>, required: true },
    names: { type: Object as PropType<Record<string, string>>, required: true },
    added: { type: Array as PropType<string[]>, required: true },
    placeholder: { type: String, default: 'найти страну: код или название…' },
  },
  emits: { pick: (code: string) => typeof code === 'string' },
  setup(props, { emit }) {
    const q = ref('');
    const open = ref(false);
    const act = ref(0);
    const root = ref<HTMLElement | null>(null);

    const filtered = computed<string[]>(() => {
      const s = q.value.trim().toLowerCase();
      if (!s) return props.codes;
      return props.codes.filter((c) =>
        c.toLowerCase().includes(s) ||
        (props.names[c] || '').toLowerCase().includes(s));
    });

    function pick(i: number): void {
      const c = filtered.value[i];
      if (!c || props.added.includes(c)) return; // не добавлять дважды
      emit('pick', c);
      q.value = '';
      open.value = false;
    }

    function onDoc(e: MouseEvent): void {
      if (open.value && root.value && !root.value.contains(e.target as Node))
        open.value = false;
    }
    onMounted(() => document.addEventListener('click', onDoc));
    onBeforeUnmount(() => document.removeEventListener('click', onDoc));

    return (): VNode => {
      const list = filtered.value;
      const items: VNode[] = list.map((c, i) =>
        h('div', {
          key: c,
          class: ['geopick-item', { act: i === act.value, added: props.added.includes(c) }],
          onClick: (): void => pick(i),
          onMouseenter: (): void => { act.value = i; },
        }, [
          h('span', { class: 'geopick-flag' }, flagEmoji(c)),
          h('span', { class: 'geopick-name' }, props.names[c] || c),
          h('span', { class: 'geopick-code mono' }, c),
        ]));
      const children: VNode[] = [
        h('input', {
          type: 'text',
          value: q.value,
          placeholder: props.placeholder,
          autocomplete: 'off',
          onInput: (e: Event): void => {
            q.value = (e.target as HTMLInputElement).value;
            open.value = true;
            act.value = 0;
          },
          onFocus: (): void => { open.value = true; },
          onKeydown: (e: KeyboardEvent): void => {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              if (!open.value) open.value = true;
              else act.value = Math.min(act.value + 1, list.length - 1);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              act.value = Math.max(act.value - 1, 0);
            } else if (e.key === 'Enter') {
              e.preventDefault();
              if (open.value) pick(act.value);
            } else if (e.key === 'Escape') {
              open.value = false;
            }
          },
        }),
      ];
      if (open.value) {
        children.push(h('div', { class: 'geopick-list' },
          items.length ? items :
            [h('div', { class: 'geopick-item faint' }, 'ничего не найдено')]));
      }
      return h('div', { ref: root, class: 'geopick' }, children);
    };
  },
});

/* ---------- загрузка ---------- */
const sortedCountries = computed(() =>
  Object.keys(countries.value).sort((a, b) =>
    (countries.value[a] || a).localeCompare(countries.value[b] || b, 'ru')));

/* Счётчики запросов: устаревший ответ не должен перетирать свежий. */
let loadGen = 0;

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const gen = ++loadGen;
  loading.value = true;
  err.value = '';
  try {
    const d = await api('/api/site/' + s.id + '/security');
    const sd = d.security || {};
    countries.value = d.countries || {};
    botCats.value = d.bot_categories || {};
    geoAvailable.value = !!d.geo_available;
    sec.geo_allow = [...(sd.geo_allow || [])];
    sec.geo_deny = [...(sd.geo_deny || [])];
    /* миграция старой схемы geo_mode/geo_countries */
    if (!sd.geo_allow && !sd.geo_deny &&
        Array.isArray(sd.geo_countries) && sd.geo_countries.length) {
      if (sd.geo_mode === 'deny') sec.geo_deny = [...sd.geo_countries];
      else if (sd.geo_mode === 'allow') sec.geo_allow = [...sd.geo_countries];
    }
    sec.ip_allow = [...(sd.ip_allow || [])];
    sec.ip_deny = [...(sd.ip_deny || [])];
    sec.block_bots = !!sd.block_bots;
    sec.waf = !!sd.waf;
    sec.rate_limit = sd.rate_limit || 0;
    sec.rate_burst = sd.rate_burst == null ? 20 : sd.rate_burst;
    sec.ua_categories = [...(sd.ua_categories || [])];
    sec.ua_rules = (sd.ua_rules || []).map((r: UaRule) =>
      ({ pattern: String(r.pattern || ''), note: String(r.note || '') }));
    sec.block_empty_ua = !!sd.block_empty_ua;
    sec.ref_block = [...(sd.ref_block || [])];
    sec.ref_allow = [...(sd.ref_allow || [])];
    sec.block_empty_ref = !!sd.block_empty_ref;
  } catch (e: any) {
    if (gen === loadGen) { err.value = e.message || String(e); loading.value = false; }
    return;
  }
  if (gen === loadGen) loading.value = false;
}

const geoActive = computed(() => !!(sec.geo_allow.length || sec.geo_deny.length));

/* ---------- страны: два независимых списка ---------- */
function secAddGeoAllow(c: string): void {
  if (c && !sec.geo_allow.includes(c)) sec.geo_allow.push(c);
}
function secAddGeoDeny(c: string): void {
  if (c && !sec.geo_deny.includes(c)) sec.geo_deny.push(c);
}
function secRemoveGeo(kind: 'allow' | 'deny', c: string): void {
  if (kind === 'allow') sec.geo_allow = sec.geo_allow.filter((x) => x !== c);
  else sec.geo_deny = sec.geo_deny.filter((x) => x !== c);
}

/* Установка GeoIP2 (модуль + база стран) прямо из вкладки */
async function secGeoInstall(): Promise<void> {
  try {
    const r = await api('/api/software/install', { method: 'POST', body: { name: 'geoip2' } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}

/* ---------- списки IP ---------- */
const newDeny = ref('');
const newAllow = ref('');

/** Проверка адреса: IPv4 — полностью, IPv6 — упрощённо (hex-группы через «:»). */
function isValidIp(ip: string): boolean {
  // IPv4: четыре числа 0–255
  const m4 = ip.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (m4) return m4.slice(1).every((x) => +x >= 0 && +x <= 255);
  // CIDR-префикс (например 10.0.0.0/8) — проверяем адресную часть
  const slash = ip.indexOf('/');
  if (slash > 0) {
    const pl = ip.slice(slash + 1);
    if (!/^\d{1,3}$/.test(pl) || +pl > 128) return false;
    return isValidIp(ip.slice(0, slash));
  }
  // IPv6 (упрощённо): 2–8 групп hex через «:», допустимо одно «::»
  if (ip.includes(':')) {
    if (/[^0-9a-fA-F:]/.test(ip)) return false;
    const dc = ip.split('::');
    if (dc.length > 2) return false;
    const groups = dc.flatMap((s) => (s === '' ? [] : s.split(':')));
    if (groups.some((g) => !/^[0-9a-fA-F]{1,4}$/.test(g))) return false;
    return groups.length >= 2 && groups.length <= 8;
  }
  return false;
}

function secAddIp(kind: 'deny' | 'allow'): void {
  const input = kind === 'deny' ? newDeny : newAllow;
  const ip = input.value.trim();
  if (!ip) return;
  if (!isValidIp(ip)) {
    toastErr(new Error('«' + ip + '» не похож на IP-адрес — проверьте ввод ' +
      '(например 45.155.205.11 или 2a01:4f8::1)'));
    return;
  }
  const list = kind === 'deny' ? sec.ip_deny : sec.ip_allow;
  if (!list.includes(ip)) list.push(ip);
  input.value = '';
}

function secRemoveIp(kind: 'deny' | 'allow', ip: string): void {
  if (kind === 'deny') sec.ip_deny = sec.ip_deny.filter((x) => x !== ip);
  else sec.ip_allow = sec.ip_allow.filter((x) => x !== ip);
}

/* ---------- боты: категории и свои UA-правила ---------- */
const catIcon: Record<string, string> = {
  scanners: 'wrench', abuse: 'down', ai: 'cpu', http_tools: 'term', headless: 'pause',
};
const catList = computed(() => Object.entries(botCats.value));

function toggleCat(id: string): void {
  const i = sec.ua_categories.indexOf(id);
  if (i >= 0) sec.ua_categories.splice(i, 1);
  else sec.ua_categories.push(id);
}

const newRulePat = ref('');
const newRuleNote = ref('');

function secAddRule(): void {
  const pat = newRulePat.value.trim();
  if (!pat) { toastErr('введите шаблон User-Agent'); return; }
  if (pat.length > 150 || /["\\{}]/.test(pat)) {
    toastErr('недопустимый шаблон User-Agent (кавычки, скобки, слэши)'); return;
  }
  try { new RegExp(pat); } catch { toastErr('некорректный regex в шаблоне User-Agent'); return; }
  if (!sec.ua_rules.some((r) => r.pattern === pat))
    sec.ua_rules.push({ pattern: pat, note: newRuleNote.value.trim() });
  newRulePat.value = '';
  newRuleNote.value = '';
}

function sanitizeUa(ua: string): string {
  return ua.replace(/["\\{}]/g, '').trim().slice(0, 150);
}
function uaInRules(ua: string): boolean {
  const pat = sanitizeUa(ua);
  return !!pat && sec.ua_rules.some((r) => r.pattern === pat);
}
function blockUa(ua: string): void {
  const pat = sanitizeUa(ua);
  if (!pat || sec.ua_rules.some((r) => r.pattern === pat)) return;
  sec.ua_rules.push({ pattern: pat, note: 'из логов' });
}

/* подсказка категории по характерным сигнатурам UA */
const CAT_HINTS: Array<[RegExp, string]> = [
  [/gptbot|claude|anthropic|cc-?crawler|bytespider|perplexity|google-?extended|facebookbot/i, 'ai'],
  [/sqlmap|nikto|nmap|masscan|dirbuster|acunetix|nessus|wpscan/i, 'scanners'],
  [/semrush|ahrefs|mj12|dotbot|petalbot|serpstat|megaindex|barkrowler/i, 'abuse'],
  [/curl|wget|python-requests|python-urllib|go-http-client|java\/|okhttp|libwww|scrapy/i, 'http_tools'],
  [/headlesschrome|phantomjs|puppeteer|playwright/i, 'headless'],
];
function uaHint(ua: string): string | null {
  for (const [rx, id] of CAT_HINTS)
    if (rx.test(ua) && botCats.value[id]) return id;
  return null;
}
function addCat(id: string): void {
  if (!sec.ua_categories.includes(id)) sec.ua_categories.push(id);
}

/* ---------- источники (Referer) ---------- */
const newRefBlock = ref('');
const newRefAllow = ref('');

function cleanDomain(v: string): string {
  return v.trim().toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/\/.*$/, '');
}
function secAddRef(kind: 'block' | 'allow'): void {
  const input = kind === 'block' ? newRefBlock : newRefAllow;
  const d = cleanDomain(input.value);
  if (!d) return;
  const list = kind === 'block' ? sec.ref_block : sec.ref_allow;
  if (!list.includes(d)) list.push(d);
  input.value = '';
}
function secRemoveRef(kind: 'block' | 'allow', d: string): void {
  if (kind === 'block') sec.ref_block = sec.ref_block.filter((x) => x !== d);
  else sec.ref_allow = sec.ref_allow.filter((x) => x !== d);
}
function blockRef(d: string): void {
  if (!sec.ref_block.includes(d)) sec.ref_block.push(d);
}
function refBlocked(d: string): boolean {
  return sec.ref_block.includes(d);
}

/* ---------- анализ из логов ---------- */
const logs = ref<any | null>(null);
const statsLoading = ref(false);
let statsGen = 0;
let statsLoaded = false; // ленивая загрузка — только при первом открытии под-таба

interface UaRow { ua: string; count: number; hint: string | null }
interface RefRow { ref: string; count: number }

const topUas = computed<UaRow[]>(() =>
  (logs.value?.top_uas || []).map(([ua, count]: [string, number]) =>
    ({ ua, count, hint: uaHint(ua) })));
const topRefs = computed<RefRow[]>(() =>
  (logs.value?.top_refs || []).map(([ref, count]: [string, number]) =>
    ({ ref, count })));

async function loadStats(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const gen = ++statsGen;
  statsLoading.value = true;
  try {
    const d = await api('/api/site/' + s.id + '/stats?days=30');
    if (gen !== statsGen) return; // устаревший ответ — был более свежий запрос
    logs.value = d.stats || null;
  } catch { if (gen === statsGen) logs.value = null; } /* анализ не должен ломать вкладку */
  if (gen === statsGen) statsLoading.value = false;
}

/** Под-таб «Из логов»: статистика грузится лениво, при первом открытии. */
function setSecTab(t: string): void {
  secTab.value = t;
  if (t === 'analysis' && !statsLoaded) {
    statsLoaded = true;
    void loadStats();
  }
}

function fmtCount(n: number): string {
  return Number(n).toLocaleString('ru-RU');
}

onMounted(() => { load(); });

/* ---------- сохранение (новая схема WAF 2.0) ---------- */
async function secSave(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const secBody = {
    geo_allow: [...sec.geo_allow],
    geo_deny: [...sec.geo_deny],
    ip_allow: [...sec.ip_allow],
    ip_deny: [...sec.ip_deny],
    block_bots: sec.block_bots,
    waf: sec.waf,
    rate_limit: Number(sec.rate_limit) || 0,
    rate_burst: Number(sec.rate_burst) || 20,
    ua_categories: [...sec.ua_categories],
    ua_rules: sec.ua_rules.map((r) => ({ pattern: r.pattern, note: r.note })),
    block_empty_ua: sec.block_empty_ua,
    ref_block: [...sec.ref_block],
    ref_allow: [...sec.ref_allow],
    block_empty_ref: sec.block_empty_ref,
  };
  try {
    const r = await api('/api/sites/security', { method: 'POST',
      body: { id: s.id, security: secBody } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}
</script>

<template>
  <div v-if="siteState.site">
    <div v-if="loading" class="empty">Загрузка…</div>
    <div v-else-if="err" class="empty">{{ err }}</div>
    <template v-else>
      <div class="notice info" style="margin-bottom:12px">
        Правила защиты работают на уровне nginx и применяются к этому сайту
        кнопкой «Применить правила» ниже. Кнопка «Сохранить» в шапке к ним
        не относится.
      </div>

      <!-- под-табы WAF -->
      <div class="tabs" style="margin-bottom:12px">
        <button class="tab" :class="{ active: secTab === 'geo' }"
                @click="setSecTab('geo')">Страны</button>
        <button class="tab" :class="{ active: secTab === 'ip' }"
                @click="setSecTab('ip')">IP-адреса</button>
        <button class="tab" :class="{ active: secTab === 'bots' }"
                @click="setSecTab('bots')">Боты и User-Agent</button>
        <button class="tab" :class="{ active: secTab === 'ref' }"
                @click="setSecTab('ref')">Рефереры</button>
        <button class="tab" :class="{ active: secTab === 'protect' }"
                @click="setSecTab('protect')">Защита и лимиты</button>
        <button class="tab" :class="{ active: secTab === 'analysis' }"
                @click="setSecTab('analysis')">Из логов</button>
      </div>
      <div v-show="secTab === 'geo'">      <!-- 1. Гео-доступ: два независимых списка стран -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Доступ по странам</span>
          <span class="pill" :class="geoActive ? 'ok' : 'gray'" style="margin-left:auto">
            {{ geoActive
              ? 'фильтр активен: ' + sec.geo_allow.length + ' разреш., ' +
                sec.geo_deny.length + ' запрета'
              : 'выключено' }}</span>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Два независимых списка, их можно комбинировать: «разрешённые» пускают
          только выбранные страны, «запрещённые» закрывают доступ из нежелательных.
          Например: RU в запретах + BY в разрешениях — белорусам вход, остальным
          кроме запрещённых — тоже. Если оба списка пусты — фильтр выключен.
        </div>
        <div class="split geo-cols">
          <div class="field" style="margin:0">
            <label>Разрешённые страны (только они получат доступ)</label>
            <CountryPicker :codes="sortedCountries" :names="countries"
                           :added="sec.geo_allow" @pick="secAddGeoAllow" />
            <div class="chips" style="margin-top:10px">
              <template v-if="sec.geo_allow.length">
                <span v-for="c in sec.geo_allow" :key="c" class="chip geo-ok">
                  {{ flagEmoji(c) }} {{ countries[c] || c }}
                  <button type="button" @click="secRemoveGeo('allow', c)">×</button>
                </span>
              </template>
              <span v-else class="faint" style="font-size:12.5px">пусто</span>
            </div>
          </div>
          <div class="field" style="margin:0">
            <label>Запрещённые страны (доступ закрыт)</label>
            <CountryPicker :codes="sortedCountries" :names="countries"
                           :added="sec.geo_deny" @pick="secAddGeoDeny" />
            <div class="chips" style="margin-top:10px">
              <template v-if="sec.geo_deny.length">
                <span v-for="c in sec.geo_deny" :key="c" class="chip geo-err">
                  {{ flagEmoji(c) }} {{ countries[c] || c }}
                  <button type="button" @click="secRemoveGeo('deny', c)">×</button>
                </span>
              </template>
              <span v-else class="faint" style="font-size:12.5px">пусто</span>
            </div>
          </div>
        </div>
        <div v-if="!geoActive" class="notice" style="margin-top:12px">
          Гео-фильтр выключен: списки стран пусты, сайт открыт для всего мира.
        </div>
        <div v-if="!geoAvailable" class="notice warn" style="margin-top:10px">
          Модуль nginx geoip2 или база стран GeoLite2 не установлены —
          без них фильтр по странам работать не будет. Установите в разделе
          «Установка ПО» (группа «SSL и безопасность») или прямо здесь:
          <button class="btn sm" style="margin:4px 0 0 8px" @click="secGeoInstall()">Установить GeoIP2</button>
        </div>
      </div>

    </div>
      <div v-show="secTab === 'ip'">      <!-- 2/3. Списки IP -->
      <div class="split" style="margin-bottom:12px">
        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Чёрный список IP</span>
            <span class="pill" :class="sec.ip_deny.length ? 'err' : 'gray'" style="margin-left:auto">
              {{ sec.ip_deny.length ? 'заблокировано: ' + sec.ip_deny.length : 'пусто' }}</span>
          </div>
          <div class="faint" style="font-size:12px;margin-bottom:10px">
            Эти адреса получат ошибку 403 при любом обращении. Вносите спамеров,
            ботов-парсеров и взломщиков, которых видно во вкладке «Статистика».
          </div>
          <div class="row">
            <input v-model="newDeny" type="text" placeholder="например, 45.155.205.11" style="flex:1"
                   @keyup.enter="secAddIp('deny')">
            <button class="btn sm" @click="secAddIp('deny')">Добавить</button>
          </div>
          <div class="chips" style="margin-top:10px">
            <template v-if="sec.ip_deny.length">
              <span v-for="ip in sec.ip_deny" :key="ip" class="chip mono">
                {{ ip }}
                <button type="button" @click="secRemoveIp('deny', ip)">×</button>
              </span>
            </template>
            <span v-else class="faint" style="font-size:12.5px">пусто</span>
          </div>
        </div>

        <div class="card" style="margin:0">
          <div class="card-h"><span class="card-t">Белый список IP</span>
            <span class="pill" :class="sec.ip_allow.length ? 'ok' : 'gray'" style="margin-left:auto">
              {{ sec.ip_allow.length ? 'только они: ' + sec.ip_allow.length : 'пусто' }}</span>
          </div>
          <div class="faint" style="font-size:12px;margin-bottom:10px">
            Если список непуст — доступ открыт ТОЛЬКО с этих адресов, всем
            остальным 403. Удобно, пока сайт в разработке, или чтобы закрыть
            админку от посторонних.
          </div>
          <div class="row">
            <input v-model="newAllow" type="text" placeholder="например, 10.0.0.5" style="flex:1"
                   @keyup.enter="secAddIp('allow')">
            <button class="btn sm" @click="secAddIp('allow')">Добавить</button>
          </div>
          <div class="chips" style="margin-top:10px">
            <template v-if="sec.ip_allow.length">
              <span v-for="ip in sec.ip_allow" :key="ip" class="chip mono">
                {{ ip }}
                <button type="button" @click="secRemoveIp('allow', ip)">×</button>
              </span>
            </template>
            <span v-else class="faint" style="font-size:12.5px">пусто</span>
          </div>
        </div>
      </div>

    </div>
      <div v-show="secTab === 'bots'">      <!-- 3. Боты и User-Agent -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Боты и User-Agent</span>
          <span class="pill" :class="sec.ua_categories.length || sec.ua_rules.length ? 'warn' : 'gray'"
                style="margin-left:auto">
            {{ (sec.ua_categories.length || sec.ua_rules.length)
              ? 'категорий: ' + sec.ua_categories.length + ', правил: ' + sec.ua_rules.length
              : 'выключено' }}</span>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Блокируйте ботов целыми категориями или точечными правилами по
          подстроке/regex их User-Agent. Поисковые роботы (Googlebot, YandexBot,
          Bingbot…) категориями не блокируются никогда — выдача поисковиков
          не пострадает.
        </div>

        <div class="cat-grid">
          <div v-for="[id, cat] in catList" :key="id" class="cat"
               :class="{ on: sec.ua_categories.includes(id) }">
            <UiCheckbox :model-value="sec.ua_categories.includes(id)"
                        @update:model-value="toggleCat(id)">
              <span style="margin-left:2px">
                <span class="cat-name">
                  <UiIcon :name="catIcon[id] || 'shield'" :size="15" />
                  <b>{{ cat.name }}</b></span>
                <span class="faint" style="display:block;font-size:11.5px;margin-top:2px">
                  {{ cat.desc }}</span>
              </span>
            </UiCheckbox>
          </div>
        </div>

        <label style="display:block;font-size:12.5px;font-weight:500;color:var(--muted);margin:12px 0 6px">
          Свои правила User-Agent (подстрока или regex)</label>
        <div v-if="sec.ua_rules.length">
          <div v-for="(r, i) in sec.ua_rules" :key="i" class="rule-row">
            <span class="mono trunc" :title="r.pattern">{{ r.pattern }}</span>
            <span v-if="r.note" class="faint mini trunc" :title="r.note">{{ r.note }}</span>
            <button type="button" class="rule-x" @click="sec.ua_rules.splice(i, 1)">×</button>
          </div>
        </div>
        <div v-else class="faint" style="font-size:12.5px;margin-bottom:6px">
          правил пока нет — добавьте ниже или из блока «Анализ из логов»
        </div>
        <div class="row" style="margin-top:8px;align-items:flex-end">
          <div class="field" style="flex:2;margin:0">
            <label>Шаблон</label>
            <input v-model="newRulePat" type="text" placeholder="например, semrush"
                   @keyup.enter="secAddRule">
          </div>
          <div class="field" style="flex:2;margin:0">
            <label>Заметка (необязательно)</label>
            <input v-model="newRuleNote" type="text" placeholder="например, SEO-парсер"
                   @keyup.enter="secAddRule">
          </div>
          <button class="btn sm" @click="secAddRule">Добавить</button>
        </div>

        <UiCheckbox v-model="sec.block_empty_ua" style="margin-top:12px">
          <span style="margin-left:2px"><b>Блокировать запросы без User-Agent</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              У обычных браузеров User-Agent есть всегда. Пустой — верный признак
              самописного скрипта: такие запросы получат 403.</span></span>
        </UiCheckbox>
      </div>

    </div>
      <div v-show="secTab === 'ref'">      <!-- 4. Источники (Referer) -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Источники (Referer)</span>
          <span class="pill"
                :class="sec.ref_block.length || sec.ref_allow.length ? 'warn' : 'gray'"
                style="margin-left:auto">
            {{ (sec.ref_block.length || sec.ref_allow.length)
              ? 'запрещено: ' + sec.ref_block.length + ', в белом: ' + sec.ref_allow.length
              : 'выключено' }}</span>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Фильтр по домену, с которого пришёл посетитель. Полезно против спама
          в статистике и «реферального» трафика с мусорных сайтов. Указывайте
          домен без протокола: spam-site.com.
        </div>
        <div class="split geo-cols">
          <div class="field" style="margin:0">
            <label>Запрещённые источники (403)</label>
            <div class="row">
              <input v-model="newRefBlock" type="text" placeholder="например, spam-site.com"
                     style="flex:1" @keyup.enter="secAddRef('block')">
              <button class="btn sm" @click="secAddRef('block')">Добавить</button>
            </div>
            <div class="chips" style="margin-top:10px">
              <template v-if="sec.ref_block.length">
                <span v-for="d in sec.ref_block" :key="d" class="chip geo-err mono">
                  {{ d }}
                  <button type="button" @click="secRemoveRef('block', d)">×</button>
                </span>
              </template>
              <span v-else class="faint" style="font-size:12.5px">пусто</span>
            </div>
          </div>
          <div class="field" style="margin:0">
            <label>Белый список источников (если непуст — только они)</label>
            <div class="row">
              <input v-model="newRefAllow" type="text" placeholder="например, news.example.com"
                     style="flex:1" @keyup.enter="secAddRef('allow')">
              <button class="btn sm" @click="secAddRef('allow')">Добавить</button>
            </div>
            <div class="chips" style="margin-top:10px">
              <template v-if="sec.ref_allow.length">
                <span v-for="d in sec.ref_allow" :key="d" class="chip geo-ok mono">
                  {{ d }}
                  <button type="button" @click="secRemoveRef('allow', d)">×</button>
                </span>
              </template>
              <span v-else class="faint" style="font-size:12.5px">пусто</span>
            </div>
          </div>
        </div>
        <UiCheckbox v-model="sec.block_empty_ref" style="margin-top:12px">
          <span style="margin-left:2px"><b>Блокировать запросы без Referer</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Осторожно: прямой переход по адресу или ссылке из мессенджера идёт
              без Referer — включайте только для защищаемых разделов.</span></span>
        </UiCheckbox>
      </div>

    </div>
      <div v-show="secTab === 'analysis'">      <!-- 5. Анализ из логов -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h">
          <span class="card-t">Анализ из логов</span>
          <span class="faint" style="font-size:12px">за 30 дней</span>
          <button class="btn sm" style="margin-left:auto" :disabled="statsLoading"
                  @click="loadStats()">
            <UiIcon name="refresh" :size="14" /> Обновить анализ</button>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Что реально ходит на сайт по данным журналов. Кнопка «Блок» добавляет
          правило в списки выше — не забудьте нажать «Применить правила» внизу.
        </div>

        <template v-if="statsLoading">
          <div class="faint" style="font-size:12.5px">Загрузка статистики…</div>
        </template>
        <template v-else-if="!topUas.length && !topRefs.length">
          <div class="faint" style="font-size:12.5px">
            Данных за 30 дней нет — сайт пуст или логи ещё не разобраны.</div>
        </template>
        <template v-else>
          <label style="display:block;font-size:12.5px;font-weight:500;color:var(--muted);margin-bottom:6px">
            Top User-Agent</label>
          <div v-for="(u, i) in topUas" :key="'ua' + i" class="rule-row">
            <span class="mono trunc" :title="u.ua">{{ u.ua || '(пустой User-Agent)' }}</span>
            <span class="pill gray">{{ fmtCount(u.count) }}</span>
            <button v-if="u.hint && !sec.ua_categories.includes(u.hint)"
                    type="button" class="btn sm" @click="addCat(u.hint)">
              + категория «{{ botCats[u.hint].name }}»</button>
            <button v-if="!uaInRules(u.ua)" type="button" class="btn sm"
                    @click="blockUa(u.ua)">Блок</button>
            <span v-else class="pill ok">в правилах</span>
          </div>

          <label style="display:block;font-size:12.5px;font-weight:500;color:var(--muted);margin:14px 0 6px">
            Top источники (Referer)</label>
          <div v-for="(r, i) in topRefs" :key="'ref' + i" class="rule-row">
            <span class="mono trunc" :title="r.ref">{{ r.ref || '(без источника)' }}</span>
            <span class="pill gray">{{ fmtCount(r.count) }}</span>
            <button v-if="!refBlocked(r.ref)" type="button" class="btn sm"
                    @click="blockRef(r.ref)">Блок</button>
            <span v-else class="pill err">заблокирован</span>
          </div>
        </template>
      </div>

    </div>
      <div v-show="secTab === 'protect'">      <!-- 6. Автоматическая защита -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Автоматическая защита</span></div>
        <UiCheckbox v-model="sec.block_bots" style="margin:8px 0">
          <span style="margin-left:2px"><b>Блокировать ботов и сканеров</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Известные боты, утилиты перебора паролей и сканеры уязвимостей
              получат 403 по их User-Agent. Обычные посетители не пострадают.</span></span>
        </UiCheckbox>
        <UiCheckbox v-model="sec.waf" style="margin:8px 0">
          <span style="margin-left:2px"><b>Включить WAF</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Блокирует типовые атаки: SQL-инъекции, XSS-скрипты в адресах,
              попытки скачать скрытые файлы (.env, .git и т.п.).</span></span>
        </UiCheckbox>
      </div>

      <!-- 7. Ограничение частоты -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Ограничение частоты запросов</span>
          <span class="pill" :class="sec.rate_limit ? 'warn' : 'gray'" style="margin-left:auto">
            {{ sec.rate_limit ? sec.rate_limit + ' зап./сек' : 'выключено' }}</span>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Защита от DDoS и брутфорса: если с одного адреса идёт больше запросов,
          чем разрешено, лишние получают ошибку 429. Обычному посетителю хватает
          5–20 запросов в секунду.
        </div>
        <div class="row">
          <div class="field" style="flex:1;margin:0">
            <label>Запросов в секунду (0 — выключено)</label>
            <input v-model.number="sec.rate_limit" type="number">
          </div>
          <div class="field" style="flex:1;margin:0">
            <label>Допуск всплесков (burst)</label>
            <input v-model.number="sec.rate_burst" type="number">
            <div class="faint" style="font-size:11.5px;margin-top:4px">
              На сколько запросов разрешено «превысить» лимит коротким всплеском
              (страница грузит 15 файлов разом — и это нормально). Обычно 20–50.
            </div>
          </div>
        </div>
      </div>

    </div>
      <!-- 8. Применить -->
      <div class="row" style="margin-top:4px;align-items:center">
        <button class="btn primary" @click="secSave()">
          <UiIcon name="check" :size="14" /> Применить правила</button>
        <span class="faint" style="font-size:12px">
          nginx перезагрузится автоматически; при ошибке конфиг откатится сам.</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* гео: две равные колонки (переопределяем .split 2fr/1fr) */
.geo-cols{grid-template-columns:1fr 1fr}
@media(max-width:1080px){.geo-cols{grid-template-columns:1fr}}

/* поиск страны (инлайн-компонент CountryPicker) */
.geopick{position:relative}
.geopick input{width:100%}
.geopick-list{position:absolute;top:calc(100% + 4px);left:0;right:0;z-index:40;
  background:var(--panel);border:1px solid var(--border);border-radius:var(--r-md);
  max-height:260px;overflow-y:auto;box-shadow:0 10px 28px rgba(0,0,0,.16)}
.geopick-item{display:flex;align-items:center;gap:8px;padding:6px 10px;
  font-size:13px;cursor:pointer;user-select:none}
.geopick-item.act{background:var(--sel)}
.geopick-item.added{opacity:.45;cursor:default}
.geopick-flag{flex-shrink:0}
.geopick-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.geopick-code{margin-left:auto;color:var(--faint);font-size:11.5px}

/* цветные чипы гео/рефереров */
.chip.geo-ok{background:var(--ok-s);color:var(--ok-d)}
.chip.geo-err{background:var(--err-s);color:var(--err)}

/* карточки категорий ботов */
.cat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:8px;margin-bottom:4px}
.cat{display:block;border:1px solid var(--border);border-radius:var(--r-md);
  padding:9px 12px;cursor:pointer;transition:border-color .15s}
.cat:hover{border-color:var(--muted)}
.cat.on{border-color:var(--primary)}
.cat-name{display:inline-flex;align-items:center;gap:6px}

/* строки правил и результатов анализа */
.rule-row{display:flex;align-items:center;gap:8px;padding:5px 10px;
  border:1px solid var(--border);border-radius:var(--r);font-size:12.5px;
  margin-bottom:6px}
.rule-x{background:none;border:0;color:var(--faint);cursor:pointer;
  font:inherit;padding:0 2px}
.rule-x:hover{color:var(--err)}
.trunc{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mini{font-size:11.5px;flex-shrink:1}
</style>
