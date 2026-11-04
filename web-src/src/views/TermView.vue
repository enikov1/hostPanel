<script setup lang="ts">
/* Веб-терминал: выполнение команд на сервере (замена SSH-клиенту). */
import { ref, nextTick, onMounted } from 'vue';
import { api } from '../api/client';

const cwd = ref('/root');
const cmd = ref('');
const out = ref('root@server — команды выполняются на сервере (замена SSH)\n');
const outEl = ref<HTMLElement | null>(null);
const cmdEl = ref<HTMLInputElement | null>(null);

let hist: string[] = [];
let histIdx = -1;

function scrollDown(): void {
  nextTick(() => {
    const el = outEl.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

async function run(): Promise<void> {
  const c = cmd.value.trim();
  if (!c) return;
  const w = cwd.value.trim() || '/root';
  out.value += 'root:~$ ' + c + '\n';
  hist.push(c);
  if (hist.length > 100) hist.shift();
  histIdx = -1;
  cmd.value = '';
  scrollDown();
  try {
    const r = await api('/api/exec', { method: 'POST', body: { cmd: c, cwd: w } });
    out.value += (r.output && r.output.trim()) ? r.output : '(нет вывода)';
    if (r.code !== 0) out.value += '\n[код завершения ' + r.code + ']';
    out.value += '\n';
  } catch (e: any) {
    out.value += 'ОШИБКА: ' + (e.message || String(e)) + '\n';
  }
  scrollDown();
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Enter') {
    run();
  } else if (e.key === 'ArrowUp') {
    if (histIdx < hist.length - 1) {
      histIdx++;
      cmd.value = hist[hist.length - 1 - histIdx];
    }
    e.preventDefault();
  } else if (e.key === 'ArrowDown') {
    if (histIdx > 0) {
      histIdx--;
      cmd.value = hist[hist.length - 1 - histIdx];
    } else {
      histIdx = -1;
      cmd.value = '';
    }
    e.preventDefault();
  }
}

function clear(): void { out.value = ''; }

onMounted(() => { cmdEl.value?.focus(); });
</script>

<template>
  <div class="card" style="padding:10px">
    <div class="row">
      <div class="field" style="flex:1">
        <label>Рабочая папка</label>
        <input v-model="cwd" type="text" class="mono">
      </div>
    </div>
    <div ref="outEl" class="logbox"
         style="height:440px;overflow:auto;white-space:pre-wrap;background:var(--hover)">{{ out }}</div>
    <div class="row" style="margin-top:10px">
      <input ref="cmdEl" v-model="cmd" type="text" class="mono" autocomplete="off"
             placeholder="команда, например: df -h" style="flex:1" @keydown="onKey">
      <button class="btn primary" @click="run()">Выполнить</button>
      <button class="btn" @click="clear()">Очистить</button>
    </div>
    <div class="faint" style="font-size:11.5px;margin-top:6px">
      ↑/↓ — история · Enter — выполнить · cd меняет рабочую папку · интерактивные программы (top, vim) не поддерживаются
    </div>
  </div>
</template>
