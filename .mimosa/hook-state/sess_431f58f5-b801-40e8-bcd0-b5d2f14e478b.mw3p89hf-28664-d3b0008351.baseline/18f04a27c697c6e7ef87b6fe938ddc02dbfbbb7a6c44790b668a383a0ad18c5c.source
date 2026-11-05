/* ============ Копирование в буфер ============ */

export function copyText(text: string, btn?: HTMLElement): void {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      btn.classList.add('copied');
      setTimeout(() => btn.classList.remove('copied'), 900);
    }
  }).catch(() => {
    // fallback для HTTP-контекста (панель без TLS)
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* noop */ }
    ta.remove();
    if (btn) {
      btn.classList.add('copied');
      setTimeout(() => btn.classList.remove('copied'), 900);
    }
  });
}
