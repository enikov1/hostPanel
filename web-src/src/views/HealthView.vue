<script setup lang="ts">
/* ============ Страница «Живучесть» (старый id 'health') ============ */
import { ref, onMounted, nextTick } from 'vue';
import { api } from '../api/client';
import { toastErr } from '../lib/toast';
import { fmtDate } from '../lib/format';
import { drawUptime } from '../lib/charts';
import type { SiteRow, HealthReport } from './monitoring/types';

interface HealthRow { s: SiteRow; h: HealthReport | null }

const rows = ref<HealthRow[]>([]);
const sparks = new Map<number, HTMLCanvasElement>();

function setSpark(id: number, el: unknown): void {
  if (el instanceof HTMLCanvasElement) sparks.set(id, el);
  else sparks.delete(id);
}

function upPillCls(u: number | null | undefined): string {
  if (u == null) return 'gray';
  return u >= 99.5 ? 'ok' : u >= 97 ? 'warn' : 'err';
}
function upPillTxt(u: number | null | undefined): string {
  return u == null ? 'нет данных' : u + '%';
}
function respTxt(r: HealthRow): string {
  const last = r.h?.last;
  if (!last) return '—';
  return last.ok ? last.ms + ' мс' : 'HTTP ' + (last.code || '—');
}
function respCls(r: HealthRow): string {
  const last = r.h?.last;
  if (!last) return '';
  return last.ok ? 'ok' : 'err';
}
function extTxt(r: HealthRow): string {
  const ext = r.h?.last?.ext;
  if (!ext) return '';
  return ext.ok ? 'внешн. ок' : 'внешн. fail';
}
function extCls(r: HealthRow): string {
  const ext = r.h?.last?.ext;
  if (!ext) return '';
  return ext.ok ? 'ok' : 'err';
}
function incCount(r: HealthRow): number {
  return (r.h?.incidents || []).length;
}

async function load(): Promise<void> {
  let sites: SiteRow[];
  try {
    sites = (await api('/api/sites')).sites;
  } catch (e) {
    rows.value = [];
    toastErr(e);
    return;
  }
  const rs: HealthRow[] = await Promise.all(sites.map(async (s) => {
    let h: HealthReport | null = null;
    try { h = (await api('/api/site/' + s.id + '/health')).report; } catch (e) { /* сайт без отчёта */ }
    return { s, h };
  }));
  rows.value = rs;
  await nextTick();
  rs.forEach((r) => {
    if (r.h && r.h.series) {
      drawUptime(sparks.get(r.s.id) || null, r.h.series.slice(-140));
    }
  });
}

onMounted(() => { void load(); });
</script>

<template>
  <div v-table>
    <div class="card" style="padding:6px 10px">
      <div class="twrap"><table>
        <thead><tr>
          <th>Сайт</th><th>Доступность 24 ч</th><th>7 дней</th><th>Ответ</th>
          <th>Инциденты</th><th>Проверки (12 ч)</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.s.id">
            <td><b>{{ r.s.domain }}</b>
              <span v-if="!r.s.enabled" class="pill warn">отключён</span>
              <span v-if="r.s.maintenance" class="pill warn">обслуживание</span></td>
            <td><span class="pill" :class="upPillCls(r.h?.uptime_24h)">{{ upPillTxt(r.h?.uptime_24h) }}</span></td>
            <td>{{ r.h?.uptime_7d != null ? r.h.uptime_7d + '%' : '—' }}</td>
            <td>
              <span v-if="r.h?.last" class="pill" :class="respCls(r)">{{ respTxt(r) }}</span>
              <template v-else>—</template>
              <span v-if="extTxt(r)" class="pill" :class="extCls(r)"
                    :title="extCls(r) === 'ok'
                      ? 'Проверка через публичный IP сервера'
                      : 'Через публичный IP сайт недоступен: проверьте файрвол/порты'">
                {{ extTxt(r) }}</span>
            </td>
            <td>
              <template v-if="incCount(r)">
                <span class="pill err">{{ incCount(r) }}</span>
                <div class="faint" style="font-size:11.5px">
                  последний: {{ fmtDate((r.h?.incidents || [])[0]?.start) }}</div>
              </template>
              <span v-else class="pill ok">0</span>
            </td>
            <td style="min-width:200px">
              <canvas class="spark" :ref="(el) => setSpark(r.s.id, el)"></canvas>
            </td>
          </tr>
        </tbody>
      </table></div>
    </div>
    <div class="notice info">
      Панель сама проверяет каждый включённый сайт раз в минуту (интервал меняется в настройках).
      Инциденты и уведомления о недоступности появляются автоматически.
    </div>
  </div>
</template>
