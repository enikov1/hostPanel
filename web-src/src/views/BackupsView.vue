<script setup lang="ts">
/* ============ Страница «Резервные копии» (старый id 'backups') ============ */
import { ref, onMounted } from 'vue';
import { api, downloadFile } from '../api/client';
import { toast, toastErr } from '../lib/toast';
import { confirmDlg } from '../lib/confirm';
import { fmtSize, fmtDate } from '../lib/format';
import UiIcon from '../components/UiIcon.vue';
import AppModal from '../components/AppModal.vue';

interface Backup { id: string; created: string; size: number; sites?: string[]; with_db?: boolean }

const loading = ref(true);
const backups = ref<Backup[]>([]);

async function load(): Promise<void> {
  try {
    const d = await api('/api/backups');
    backups.value = d.backups || [];
  } catch (e) {
    backups.value = [];
    toastErr(e);
  }
  loading.value = false;
}

onMounted(() => { void load(); });

/* ---------- создание копии ---------- */
const crtDlg = ref(false);
const crtWithDb = ref(true);

function createBackupDlg(): void {
  crtWithDb.value = true;
  crtDlg.value = true;
}

const creating = ref(false);

async function createBackup(): Promise<void> {
  creating.value = true;
  try {
    toast('Создаётся резервная копия…');
    const r = await api('/api/backups/create', { method: 'POST', body: { with_db: crtWithDb.value } });
    crtDlg.value = false;
    toast((r.message || 'готово') + ' (' + fmtSize(r.backup && r.backup.size) + ')');
    void load();
  } catch (e) { toastErr(e); }
  creating.value = false;
}

/* ---------- восстановление ---------- */
function restoreBackup(b: Backup): void {
  confirmDlg('Восстановление',
    'Файлы сайтов будут заменены содержимым копии от ' + fmtDate(b.created) + '. Продолжить?',
    async () => {
      try {
        const r = await api('/api/backups/restore', { method: 'POST', body: { id: b.id } });
        toast(r.message || 'готово');
      } catch (e) { toastErr(e); }
    });
}

/* ---------- удаление ---------- */
function delBackup(b: Backup): void {
  confirmDlg('Удалить копию', 'Резервная копия будет удалена навсегда.',
    async () => {
      try {
        const r = await api('/api/backups/delete', { method: 'POST', body: { id: b.id } });
        toast(r.message || 'готово');
        void load();
      } catch (e) { toastErr(e); }
    });
}

/* ---------- скачивание ---------- */
function dlBackup(b: Backup): void {
  void downloadFile('/api/backup/download?id=' + encodeURIComponent(b.id),
    'backup_' + b.id + '.tar.gz');
}
</script>

<template>
  <div v-table>
    <div v-if="loading" class="empty">Загрузка…</div>

    <template v-else>
      <div class="toolbar">
        <button class="btn primary" @click="createBackupDlg()">
          <UiIcon name="plus" :size="15" />Создать резервную копию</button>
        <span class="tb-spacer"></span>
        <span class="muted" style="font-size:13px">Копий: {{ backups.length }}</span>
      </div>

      <div class="card" style="padding:6px 10px">
        <div class="twrap">
          <table>
            <thead><tr>
              <th>Дата</th><th>Состав</th><th>Размер</th><th></th>
            </tr></thead>
            <tbody>
              <tr v-for="b in backups" :key="b.id">
                <td class="mono">{{ fmtDate(b.created) }}</td>
                <td>{{ (b.sites || []).join(', ') || '—' }}<template v-if="b.with_db"> + БД</template></td>
                <td>{{ fmtSize(b.size) }}</td>
                <td>
                  <div class="actions-cell">
                    <button class="btn sm" title="Скачать копию" @click="dlBackup(b)">
                      <UiIcon name="down" :size="13" /></button>
                    <button class="btn sm" @click="restoreBackup(b)">
                      <UiIcon name="refresh" :size="13" /> Восстановить</button>
                    <button class="btn sm icon danger" title="Удалить копию" @click="delBackup(b)">
                      <UiIcon name="trash" :size="13" /></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!backups.length" class="empty">
            Резервных копий пока нет — создайте первую.</div>
        </div>
      </div>
    </template>

    <!-- ======== создание копии ======== -->
    <AppModal :open="crtDlg" title="Резервное копирование" @close="crtDlg = false">
      <label class="check">
        <input v-model="crtWithDb" type="checkbox"> Включить дампы баз данных</label>
      <div class="notice info">В архив войдут файлы всех сайтов, дампы MySQL и настройки
        панели. Хранятся последние копии (см. Настройки).</div>
      <template #footer>
        <button class="btn primary" :disabled="creating" @click="createBackup()">
          <UiIcon name="archive" :size="15" /> Создать</button>
        <button class="btn" @click="crtDlg = false">Отмена</button>
      </template>
    </AppModal>
  </div>
</template>
