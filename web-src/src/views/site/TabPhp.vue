<script setup lang="ts">
/* ============ Вкладка «PHP и FPM» карточки сайта ============
   Модули: включённые в PHP (из php -m, с пилюлей) + доступные в apt.
   Кнопка установки появляется только при выборе новых модулей.
   Пул FPM: человеческие подписи и пояснения к каждому параметру. */
import { computed, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import { siteState } from './siteShared';

const router = useRouter();

const installedSet = ref<Set<string>>(new Set());
const aptAvailable = ref<string[]>([]);
const selectedNew = ref<string[]>([]);
const installing = ref(false);
const installLog = ref<string[]>([]);

const PM_MODES: Record<string, string> = {
  dynamic: 'Процессы создаются и убираются под нагрузкой — подходит большинству сайтов (рекомендуется).',
  static: 'Постоянно держать заданное число процессов. Стабильная скорость на мощных серверах с ровным трафиком.',
  ondemand: 'Процесс запускается только при обращении. Экономно для редко посещаемых сайтов.',
};

async function loadModules(version: string): Promise<void> {
  if (!version) return;
  try {
    const p = await api('/api/php');
    const list = ((p.versions || {})[version] || []) as string[];
    siteState.modAvail = list;
  } catch (e) { /* тихо */ }
  try {
    const m = await api('/api/php/modules?version=' + encodeURIComponent(version));
    installedSet.value = new Set<string>(m.installed || []);
    aptAvailable.value = (m.available || []) as string[];
  } catch (e) { /* тихо */ }
}

/* смена версии PHP — список модулей обновляется, галочки сбрасываются
   (как stPhpChanged в оригинале) */
watch(() => siteState.f_php, async (v) => {
  selectedNew.value = [];
  installLog.value = [];
  await loadModules(v);
  siteState.f_php_modules = [];
}, { immediate: true });

/** Доступные в apt пакеты, ещё не установленные (без префикса phpX.Y-). */
const newModules = computed(() => {
  const prefix = 'php' + siteState.f_php + '-';
  return aptAvailable.value
    .filter((p: string) => !installedSet.value.has(p))
    .map((p: string) => p.startsWith(prefix) ? p.slice(prefix.length) : p)
    .filter((m) => m && !siteState.modAvail.includes(m));
});

const newSelectedCount = computed(() =>
  selectedNew.value.length);

function toggleNew(m: string, checked: boolean): void {
  const i = selectedNew.value.indexOf(m);
  if (checked && i < 0) selectedNew.value.push(m);
  if (!checked && i >= 0) selectedNew.value.splice(i, 1);
}

async function pollTask(): Promise<void> {
  for (let i = 0; i < 150; i++) {
    try {
      const t = await api('/api/packages/task');
      if (!t.running) return;
    } catch (e) { return; }
    await new Promise((r) => setTimeout(r, 2000));
  }
}

async function installSelected(): Promise<void> {
  const version = siteState.f_php;
  if (!version || !selectedNew.value.length || installing.value) return;
  installing.value = true;
  installLog.value = [];
  const mods = [...selectedNew.value];
  for (const m of mods) {
    installLog.value.push('php' + version + '-' + m + ' — запускаю установку…');
    try {
      await api('/api/php/install_module', {
        method: 'POST', body: { version, module: m },
      });
      await pollTask();
      installLog.value.push('php' + version + '-' + m + ' — установлен');
      toast('Модуль php' + version + '-' + m + ' установлен');
    } catch (e: any) {
      installLog.value.push('php' + version + '-' + m + ' — ОШИБКА: ' +
        (e.message || String(e)).slice(0, 120));
      toastErr(e);
    }
  }
  selectedNew.value = [];
  await loadModules(version);
  installing.value = false;
  toast('Готово. Отметьте модули для сайта и нажмите «Сохранить»');
}

/* подбор лимитов FPM под сервер */
async function stFpmReco(): Promise<void> {
  const s = siteState.site;
  if (!s) return;
  try {
    const r = await api('/api/site/' + s.id + '/fpm_reco');
    siteState.f_fpm.max_children = r.max_children;
    siteState.f_fpm.start_servers = r.start_servers;
    siteState.fpmReco = 'Рекомендация: max_children ' + r.max_children;
    toast('Рекомендация: max_children = ' + r.max_children + ' (' + r.note + ')');
  } catch (e) { toastErr(e); }
}
</script>

<template>
  <div v-if="siteState.site">
    <div class="field">
      <label>Версия PHP</label>
      <select v-model="siteState.f_php">
        <option v-for="v in siteState.phpVersions" :key="v" :value="v">PHP {{ v }}</option>
      </select>
    </div>

    <div class="g-title">Модули PHP (для версии {{ siteState.f_php || '—' }})</div>
    <div class="faint" style="font-size:12px;margin:0 0 8px">
      Галочки отмечают, какие модули доступны сайту. Модули, уже включённые
      в PHP, помечены зелёным — их отключать здесь не нужно.
    </div>
    <div style="max-height:220px;overflow:auto;border:1px solid var(--border);border-radius:10px;padding:10px">
      <label v-for="m in siteState.modAvail" :key="'en-' + m" class="check" style="margin:4px 0">
        <input type="checkbox" checked disabled> {{ m }}
        <span class="pill ok" style="margin-left:6px">включён</span>
        <span v-if="siteState.moduleNames[m]" class="faint">— {{ siteState.moduleNames[m] }}</span>
      </label>
      <label v-for="m in newModules" :key="'new-' + m" class="check" style="margin:4px 0">
        <input type="checkbox" :checked="selectedNew.includes(m)"
               :disabled="installing"
               @change="toggleNew(m, ($event.target as HTMLInputElement).checked)">
        {{ m }}
        <span class="pill gray" style="margin-left:6px">не установлен</span>
        <span v-if="siteState.moduleNames[m]" class="faint">— {{ siteState.moduleNames[m] }}</span>
      </label>
      <div v-if="!siteState.modAvail.length && !newModules.length" class="empty">
        Список модулей недоступен
      </div>
    </div>

    <!-- установка появляется только при выборе новых модулей -->
    <div v-if="newSelectedCount > 0 || installing || installLog.length"
         class="card" style="margin:10px 0 0;padding:10px 14px">
      <div v-if="installing" class="notice info" style="margin:0 0 8px">
        Устанавливаю модули — не закрывайте страницу. Обычно 1–2 модуля занимают около минуты.
      </div>
      <div v-if="installLog.length" class="logbox" style="max-height:140px">{{ installLog.join('\n') }}</div>
      <div v-if="newSelectedCount > 0 && !installing" class="row"
           style="margin:8px 0 0;align-items:center;gap:10px">
        <span>Выбрано новых модулей: <b>{{ newSelectedCount }}</b></span>
        <button class="btn primary sm" @click="installSelected()">
          <UiIcon name="down" :size="14" /> Установить через apt</button>
        <button class="btn sm" @click="selectedNew = []">Отменить выбор</button>
      </div>
    </div>
    <div v-else class="faint" style="font-size:11.5px;margin-top:8px">
      Нужен модуль, которого нет в списке? Отметьте его ниже списка «не установлен» — и появится кнопка установки.
    </div>

    <div class="g-title">Настройки пула PHP-FPM</div>
    <div class="faint" style="font-size:12px;margin:0 0 8px">
      Пул — это «рабочие» процессы PHP, которые обрабатывают запросы к сайту.
    </div>
    <div class="row">
      <div class="field" style="flex:1">
        <label>Режим работы</label>
        <select v-model="siteState.f_fpm.pm">
          <option v-for="m in ['dynamic', 'static', 'ondemand']" :key="m" :value="m">{{ m }}</option>
        </select>
        <div class="faint" style="font-size:11.5px;margin-top:4px">
          {{ PM_MODES[siteState.f_fpm.pm] || '' }}
        </div>
      </div>
      <div class="field" style="flex:1">
        <label>Максимум процессов (max_children)</label>
        <input v-model.number="siteState.f_fpm.max_children" type="number">
        <div class="faint" style="font-size:11.5px;margin-top:4px">
          Сколько запросов к PHP сайт обрабатывает одновременно. Больше — быстрее
          под нагрузкой, но выше расход памяти.
        </div>
      </div>
      <div class="field" style="flex:1">
        <label>Стартовых процессов (start_servers)</label>
        <input v-model.number="siteState.f_fpm.start_servers" type="number">
        <div class="faint" style="font-size:11.5px;margin-top:4px">
          Сколько процессов держать готовыми сразу (используется в режиме dynamic).
        </div>
      </div>
    </div>
    <div class="row" style="margin-top:8px;align-items:center">
      <button class="btn sm" @click="stFpmReco()">
        <UiIcon name="zap" :size="14" /> Подобрать под сервер</button>
      <span class="faint" style="font-size:11.5px">{{ siteState.fpmReco }}</span>
    </div>
  </div>
</template>
