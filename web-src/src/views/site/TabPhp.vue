<script setup lang="ts">
/* ============ Вкладка «PHP и FPM» карточки сайта (stPhp) ============ */
import { watch } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '../../api/client';
import { toast, toastErr } from '../../lib/toast';
import UiIcon from '../../components/UiIcon.vue';
import { siteState } from './siteShared';

const router = useRouter();

/* смена версии PHP — список модулей обновляется, галочки сбрасываются
   (как stPhpChanged в оригинале) */
watch(() => siteState.f_php, async (v) => {
  try {
    const p = await api('/api/php');
    siteState.modAvail = (p.versions || {})[v] || [];
  } catch (e) { /* тихо */ }
  siteState.f_php_modules = [];
});

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
    <label>Модули PHP (для версии {{ siteState.f_php || '—' }})</label>
    <div style="max-height:180px;overflow:auto;border:1px solid var(--border);border-radius:10px;padding:10px">
      <label v-for="m in siteState.modAvail" :key="m" class="check" style="margin:4px 0">
        <input v-model="siteState.f_php_modules" type="checkbox" :value="m"> {{ m }}
        <span v-if="siteState.moduleNames[m]" class="faint">— {{ siteState.moduleNames[m] }}</span>
      </label>
    </div>
    <div class="row" style="margin-top:8px">
      <button class="btn sm" @click="router.push('/packages')">
        <UiIcon name="pkg" :size="14" /> Установить модули (apt)</button>
    </div>

    <label style="margin-top:12px">Настройки пула PHP-FPM</label>
    <div class="row">
      <div class="field" style="flex:1">
        <label>Режим</label>
        <select v-model="siteState.f_fpm.pm">
          <option v-for="m in ['dynamic', 'static', 'ondemand']" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <div class="field" style="flex:1">
        <label>max_children</label>
        <input v-model.number="siteState.f_fpm.max_children" type="number">
      </div>
      <div class="field" style="flex:1">
        <label>start_servers</label>
        <input v-model.number="siteState.f_fpm.start_servers" type="number">
      </div>
    </div>
    <div class="row" style="margin-top:8px;align-items:center">
      <button class="btn sm" @click="stFpmReco()">
        <UiIcon name="zap" :size="14" /> Подобрать под сервер</button>
      <span class="faint" style="font-size:11.5px">{{ siteState.fpmReco }}</span>
    </div>
  </div>
</template>
