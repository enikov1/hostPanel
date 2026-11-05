/* ============ Общие данные приложений (phpMyAdmin) ============
   Заполняются на странице «Установка ПО»; используются страницей
   «Сайты» (кнопка phpMyAdmin в карточке сайта). */
import { ref, computed } from 'vue';

export const pmaApps = ref<any[]>([]);

const byDomain = computed<Record<string, any>>(() => {
  const m: Record<string, any> = {};
  pmaApps.value.forEach((a: any) => { m[a.domain] = a; });
  return m;
});

export function getPmaByDomain(): Record<string, any> { return byDomain.value; }
export function getPmaApps(): any[] { return pmaApps.value; }
