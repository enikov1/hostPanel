<script setup lang="ts">
/* ============ Вкладка «Фильтры» (безопасность) карточки сайта ============
   Каждая группа — отдельная карточка с человеческим описанием:
   гео-страны, чёрный/белый список IP, автоблокировка ботов/WAF,
   ограничение частоты запросов. */
import { onMounted, reactive, ref } from 'vue';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import { siteState } from './siteShared';

const loading = ref(true);
const err = ref('');
const geoAvailable = ref(true);
const countries = ref<Record<string, string>>({});

const sec = reactive({
  geo_mode: 'off',
  geo_countries: [] as string[],
  ip_allow: [] as string[],
  ip_deny: [] as string[],
  block_bots: false,
  waf: false,
  rate_limit: 0,
  rate_burst: 20,
});

/* значения инпутов добавления */
const newDeny = ref('');
const newAllow = ref('');

const countryOptions = ref<string[]>([]);

async function load(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  loading.value = true;
  err.value = '';
  try {
    const d = await api('/api/site/' + s.id + '/security');
    const sd = d.security || {};
    countries.value = d.countries || {};
    countryOptions.value = Object.keys(countries.value);
    geoAvailable.value = !!d.geo_available;
    sec.geo_mode = sd.geo_mode || 'off';
    sec.geo_countries = [...(sd.geo_countries || [])];
    sec.ip_allow = [...(sd.ip_allow || [])];
    sec.ip_deny = [...(sd.ip_deny || [])];
    sec.block_bots = !!sd.block_bots;
    sec.waf = !!sd.waf;
    sec.rate_limit = sd.rate_limit || 0;
    sec.rate_burst = sd.rate_burst == null ? 20 : sd.rate_burst;
  } catch (e: any) {
    err.value = e.message || String(e);
  }
  loading.value = false;
}

onMounted(load);

function secAddCountry(ev: Event): void {
  const v = (ev.target as HTMLSelectElement).value;
  if (!v) return;
  if (!sec.geo_countries.includes(v)) sec.geo_countries.push(v);
  (ev.target as HTMLSelectElement).value = '';
}

function secRemoveCountry(c: string): void {
  sec.geo_countries = sec.geo_countries.filter((x) => x !== c);
}

function secAddIp(kind: 'deny' | 'allow'): void {
  const input = kind === 'deny' ? newDeny : newAllow;
  const ip = input.value.trim();
  if (!ip) return;
  const list = kind === 'deny' ? sec.ip_deny : sec.ip_allow;
  if (!list.includes(ip)) list.push(ip);
  input.value = '';
}

function secRemoveIp(kind: 'deny' | 'allow', ip: string): void {
  if (kind === 'deny') sec.ip_deny = sec.ip_deny.filter((x) => x !== ip);
  else sec.ip_allow = sec.ip_allow.filter((x) => x !== ip);
}

/* Установка GeoIP2 (модуль + база стран) прямо из вкладки */
async function secGeoInstall(): Promise<void> {
  try {
    const r = await api('/api/software/install', { method: 'POST', body: { name: 'geoip2' } });
    toast(r.message);
  } catch (e) { toastErr(e); }
}

async function secSave(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  const secBody = {
    geo_mode: sec.geo_mode,
    geo_countries: sec.geo_countries,
    ip_allow: sec.ip_allow,
    ip_deny: sec.ip_deny,
    block_bots: sec.block_bots,
    waf: sec.waf,
    rate_limit: Number(sec.rate_limit) || 0,
    rate_burst: Number(sec.rate_burst) || 0,
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

      <!-- 1. Гео-доступ -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Доступ по странам</span>
          <span class="pill gray" style="margin-left:auto">
            {{ sec.geo_mode === 'off' ? 'выключено' :
               sec.geo_mode === 'allow' ? 'только выбранные' : 'кроме выбранных' }}</span>
        </div>
        <div class="faint" style="font-size:12px;margin-bottom:10px">
          Можно пустить на сайт посетителей только из выбранных стран — или,
          наоборот, закрыть доступ из нежелательных. Например: сайт только для
          России — режим «разрешить только выбранные» + RU.
        </div>
        <div class="row">
          <div class="field" style="flex:1;margin:0">
            <label>Режим</label>
            <select v-model="sec.geo_mode">
              <option value="off">— все страны —</option>
              <option value="allow">разрешить только выбранные</option>
              <option value="deny">запретить выбранные</option>
            </select>
          </div>
          <div class="field" style="flex:1;margin:0">
            <label>Добавить страну</label>
            <select :disabled="sec.geo_mode === 'off'" @change="secAddCountry">
              <option value="">{{ sec.geo_mode === 'off' ? 'сначала выберите режим' : '+ выбрать страну…' }}</option>
              <option v-for="c in countryOptions" :key="c" :value="c">{{ c }} — {{ countries[c] }}</option>
            </select>
          </div>
        </div>
        <div class="chips" style="margin-top:10px">
          <template v-if="sec.geo_countries.length">
            <span v-for="c in sec.geo_countries" :key="c" class="chip">
              {{ c }} · {{ countries[c] || '' }}
              <button type="button" @click="secRemoveCountry(c)">×</button>
            </span>
          </template>
          <span v-else class="faint" style="font-size:12.5px">страны не выбраны</span>
        </div>
        <div v-if="!geoAvailable" class="notice warn" style="margin-top:10px">
          Модуль nginx geoip2 или база стран GeoLite2 не установлены —
          без них фильтр по странам работать не будет. Установите в разделе
          «Установка ПО» (группа «SSL и безопасность») или прямо здесь:
          <button class="btn sm" style="margin:4px 0 0 8px" @click="secGeoInstall()">Установить GeoIP2</button>
        </div>
      </div>

      <!-- 2/3. Списки IP -->
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

      <!-- 4. Автоматическая защита -->
      <div class="card" style="margin:0 0 12px">
        <div class="card-h"><span class="card-t">Автоматическая защита</span></div>
        <label class="check" style="display:flex;margin:8px 0">
          <input v-model="sec.block_bots" type="checkbox">
          <span style="margin-left:2px"><b>Блокировать ботов и сканеров</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Известные боты, утилиты перебора паролей и сканеры уязвимостей
              получат 403 по их User-Agent. Обычные посетители не пострадают.</span></span>
        </label>
        <label class="check" style="display:flex;margin:8px 0">
          <input v-model="sec.waf" type="checkbox">
          <span style="margin-left:2px"><b>Включить WAF</b>
            <span class="faint" style="display:block;font-size:12px;margin-top:2px">
              Блокирует типовые атаки: SQL-инъекции, XSS-скрипты в адресах,
              попытки скачать скрытые файлы (.env, .git и т.п.).</span></span>
        </label>
      </div>

      <!-- 5. Ограничение частоты -->
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

      <div class="row" style="margin-top:4px;align-items:center">
        <button class="btn primary" @click="secSave()">
          <UiIcon name="check" :size="14" /> Применить правила</button>
        <span class="faint" style="font-size:12px">
          nginx перезагрузится автоматически; при ошибке конфиг откатится сам.</span>
      </div>
    </template>
  </div>
</template>
