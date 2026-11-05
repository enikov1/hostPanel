<script setup lang="ts">
/* ============ Страница «SSL-сертификаты»: сертификаты всех сайтов ============ */
import { computed, onMounted, ref } from 'vue';
import { api } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import UiIcon from '../components/UiIcon.vue';
import { sslActive, sslDays, type Site } from './site/siteShared';

const loading = ref(true);
const sites = ref<Site[]>([]);
const busy = ref<number | null>(null);

async function load(): Promise<void> {
  try {
    const d = await api('/api/sites');
    sites.value = d.sites || [];
  } catch (e) {
    sites.value = [];
    toastErr(e);
  }
  loading.value = false;
}

onMounted(() => { void load(); });

/* ---------- сводка ---------- */
const withSsl = computed<Site[]>(() => sites.value.filter((s) => sslActive(s)));
const expiring30 = computed(() => withSsl.value.filter((s) => {
  const d = sslDays(s);
  return d !== null && d < 30;
}).length);

/* ---------- сортировка: сначала истекающие ---------- */
const sorted = computed<Site[]>(() => {
  return [...sites.value].sort((a, b) => {
    const da = sslDays(a), db = sslDays(b);
    if (da === null && db === null) return a.domain.localeCompare(b.domain);
    if (da === null) return 1;   /* без SSL — в конец */
    if (db === null) return -1;
    return da - db;              /* меньше дней — выше */
  });
});

/* ---------- ячейки ---------- */
function kindText(s: Site): string {
  return s.ssl.kind === 'letsencrypt' ? "Let's Encrypt" : 'Самоподписанный';
}

function pillCls(s: Site): string {
  const d = sslDays(s);
  if (d === null) return 'pill err';
  if (d < 14) return 'pill err';
  if (d < 30) return 'pill warn';
  return 'pill ok';
}

function pillText(s: Site): string {
  const d = sslDays(s);
  if (d === null) return 'истекает';
  return d + ' дн.';
}

/* ---------- действия ---------- */
async function issueGo(s: Site): Promise<void> {
  busy.value = s.id;
  const email = window.prompt('E-mail для уведомлений Let\'s Encrypt (можно пропустить):') || '';
  try {
    const r = await api('/api/sites/ssl', { method: 'POST', body: { id: s.id, kind: 'letsencrypt', email } });
    toast(r.message);
    await load();
  } catch (e) { toastErr(e); }
  busy.value = null;
}

function reissue(s: Site): void {
  void issueGo(s);
}

function issueEmpty(s: Site): void {
  void issueGo(s);
}

function delCert(s: Site): void {
  confirmDlg('Удалить сертификат', 'Сертификат сайта ' + s.domain + ' будет удалён.',
    async () => {
      busy.value = s.id;
      try {
        const r = await api('/api/sites/ssl_delete', { method: 'POST', body: { id: s.id } });
        toast(r.message);
        await load();
      } catch (e) { toastErr(e); }
      busy.value = null;
    });
}
</script>

<template>
  <div v-table>
    <div v-if="loading" class="empty">Загрузка…</div>

    <template v-else>
      <div class="toolbar">
        <span class="muted" style="font-size:13px">
          всего сертификатов: <b>{{ withSsl.length }}</b>
          <span class="faint">·</span>
          истекают в 30 дней: <b>{{ expiring30 }}</b></span>
      </div>

      <div class="card" style="padding:6px 10px">
        <div class="twrap">
          <table>
            <thead><tr>
              <th>Домен</th><th>Тип</th><th>Домены серта</th><th>Действует до</th><th></th>
            </tr></thead>
            <tbody>
              <tr v-for="s in sorted" :key="s.id">
                <td class="mono">{{ s.domain }}</td>
                <td>
                  <template v-if="s.ssl && s.ssl.kind !== 'none'">{{ kindText(s) }}</template>
                  <span v-else class="pill err">нет</span>
                </td>
                <td class="mono" style="word-break:break-all">
                  {{ (s.ssl && s.ssl.domains && s.ssl.domains.length) ? s.ssl.domains.join(', ') : '—' }}</td>
                <td>
                  <template v-if="s.ssl && s.ssl.kind !== 'none' && s.ssl.expires">
                    {{ s.ssl.expires }}
                    <span :class="pillCls(s)">{{ pillText(s) }}</span>
                  </template>
                  <span v-else class="pill err">нет</span>
                </td>
                <td>
                  <div class="actions-cell">
                    <template v-if="s.ssl && s.ssl.kind !== 'none'">
                      <button class="btn sm" :disabled="busy === s.id" @click="reissue(s)">
                        <UiIcon name="refresh" :size="13" /> Перевыпустить</button>
                      <button class="btn sm icon danger" title="Удалить сертификат"
                              :disabled="busy === s.id" @click="delCert(s)">
                        <UiIcon name="trash" :size="13" /></button>
                    </template>
                    <button v-else class="btn sm primary" :disabled="busy === s.id" @click="issueEmpty(s)">
                      <UiIcon name="plus" :size="13" /> Выпустить</button>
                    <router-link class="btn sm" :to="'/sites/' + s.id + '?tab=ssl'">
                      <UiIcon name="gear" :size="13" /> Настроить</router-link>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!sites.length" class="empty">
            Сайтов пока нет — SSL-сертификаты выпускаются в карточке сайта.</div>
        </div>
      </div>
    </template>
  </div>
</template>
