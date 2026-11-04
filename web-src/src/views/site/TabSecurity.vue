<script setup lang="ts">
/* ============ Вкладка «Фильтры» (безопасность) карточки сайта ============ */
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
      <div class="notice info">Правила применяются к сайту на уровне nginx: гео-страны (GeoIP2), списки IP, блокировка ботов и сканеров, базовый WAF (SQLi/XSS/скрытые файлы), ограничение частоты запросов.</div>

      <div class="g-title no-line">Доступ по странам</div>
      <div class="row">
        <select v-model="sec.geo_mode">
          <option value="off">— все страны —</option>
          <option value="allow">разрешить только выбранные</option>
          <option value="deny">запретить выбранные</option>
        </select>
        <div style="flex:1;min-width:200px">
          <select @change="secAddCountry">
            <option value="">+ добавить страну…</option>
            <option v-for="c in countryOptions" :key="c" :value="c">{{ c }} — {{ countries[c] }}</option>
          </select>
        </div>
      </div>
      <div class="chips" style="margin-top:8px">
        <template v-if="sec.geo_countries.length">
          <span v-for="c in sec.geo_countries" :key="c" class="chip">
            {{ c }} · {{ countries[c] || '' }}
            <button type="button" @click="secRemoveCountry(c)">×</button>
          </span>
        </template>
        <span v-else class="faint" style="font-size:12.5px">страны не выбраны</span>
      </div>
      <div v-if="!geoAvailable" class="notice warn" style="margin-top:10px">
        Модуль nginx geoip2 или база стран GeoLite2 не установлены. Установите в разделе «Установка ПО»
        (группа «SSL и безопасность») или прямо здесь:
        <button class="btn sm" style="margin:4px 0 0 8px" @click="secGeoInstall()">Установить GeoIP2</button>
      </div>

      <div class="g-title">Запрещённые IP (чёрный список)</div>
      <div class="row">
        <input v-model="newDeny" type="text" placeholder="например, 45.155.205.11" style="flex:1"
               @keyup.enter="secAddIp('deny')">
        <button class="btn sm" @click="secAddIp('deny')">Добавить</button>
      </div>
      <div class="chips" style="margin-top:8px">
        <template v-if="sec.ip_deny.length">
          <span v-for="ip in sec.ip_deny" :key="ip" class="chip mono">
            {{ ip }}
            <button type="button" @click="secRemoveIp('deny', ip)">×</button>
          </span>
        </template>
        <span v-else class="faint" style="font-size:12.5px">пусто</span>
      </div>

      <div class="g-title">Разрешённые IP (белый список; при непустом — только они)</div>
      <div class="row">
        <input v-model="newAllow" type="text" placeholder="например, 10.0.0.5" style="flex:1"
               @keyup.enter="secAddIp('allow')">
        <button class="btn sm" @click="secAddIp('allow')">Добавить</button>
      </div>
      <div class="chips" style="margin-top:8px">
        <template v-if="sec.ip_allow.length">
          <span v-for="ip in sec.ip_allow" :key="ip" class="chip mono">
            {{ ip }}
            <button type="button" @click="secRemoveIp('allow', ip)">×</button>
          </span>
        </template>
        <span v-else class="faint" style="font-size:12.5px">пусто</span>
      </div>

      <div class="row" style="margin-top:14px">
        <label class="check" style="margin:0">
          <input v-model="sec.block_bots" type="checkbox"> Блокировать ботов и сканеры</label>
        <label class="check" style="margin:0">
          <input v-model="sec.waf" type="checkbox"> Включить WAF (SQLi / XSS / скрытые файлы)</label>
      </div>

      <div class="g-title">Ограничение частоты запросов (защита от DDoS)</div>
      <div class="row">
        <div class="field" style="flex:1">
          <label style="margin-top:0">Запросов/сек (0 = выкл.)</label>
          <input v-model.number="sec.rate_limit" type="number">
        </div>
        <div class="field" style="flex:1">
          <label style="margin-top:0">Всплеск (burst)</label>
          <input v-model.number="sec.rate_burst" type="number">
        </div>
      </div>

      <div class="row" style="margin-top:14px">
        <button class="btn primary" @click="secSave()">
          <UiIcon name="check" :size="14" /> Применить фильтры</button>
      </div>
    </template>
  </div>
</template>
