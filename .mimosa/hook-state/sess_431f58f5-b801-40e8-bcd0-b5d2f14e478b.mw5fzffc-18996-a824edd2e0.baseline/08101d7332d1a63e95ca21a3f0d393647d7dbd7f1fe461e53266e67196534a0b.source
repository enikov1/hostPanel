/* ============ Тема оформления (light/dark) ============ */

export function applyTheme(t: string): void {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('hp_theme', t); } catch (e) { /* noop */ }
}

export function currentTheme(): string {
  return document.documentElement.getAttribute('data-theme') ||
    ((): string => {
      try { return localStorage.getItem('hp_theme') || 'light'; } catch (e) { return 'light'; }
    })();
}

export function toggleTheme(): string {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  return next;
}
