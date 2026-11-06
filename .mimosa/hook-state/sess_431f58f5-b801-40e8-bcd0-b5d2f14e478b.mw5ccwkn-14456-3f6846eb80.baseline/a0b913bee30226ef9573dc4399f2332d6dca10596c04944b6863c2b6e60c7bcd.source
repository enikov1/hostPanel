import { createApp, type Directive } from 'vue';
import App from './App.vue';
import { router } from './router';
import './app.css';
import { applyTheme } from './lib/theme';

/* Мобильная адаптация таблиц: заголовки thead -> data-l у ячеек
   (использовать как v-table на корне с таблицами после рендера). */
const table: Directive<HTMLElement> = {
  updated(el: HTMLElement) {
    queueMicrotask(() => {
      el.querySelectorAll('table').forEach((t) => {
        const heads = Array.from(t.querySelectorAll('thead th'))
          .map((th) => (th.textContent || '').trim());
        if (!heads.length) return;
        t.querySelectorAll('tbody tr').forEach((tr) => {
          Array.from(tr.children).forEach((td, i) => {
            td.setAttribute('data-l', heads[i] || '');
          });
        });
      });
    });
  },
};

applyTheme(((): string => {
  try { return localStorage.getItem('hp_theme') || 'light'; } catch (e) { return 'light'; }
})());

createApp(App)
  .use(router)
  .directive('table', table)
  .mount('#ui');
