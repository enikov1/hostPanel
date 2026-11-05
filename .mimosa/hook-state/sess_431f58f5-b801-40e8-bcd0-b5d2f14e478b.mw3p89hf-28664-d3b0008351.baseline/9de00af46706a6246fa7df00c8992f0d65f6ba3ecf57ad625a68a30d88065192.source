/* ============ Тосты: глобальные функции + хост-компонент ============ */

const ERROR_HINTS: [RegExp, string][] = [
  [/(?:dns problem|failed authorization|dns_ok|не указывает на сервер)/i,
   'Домен пока не указывает на этот сервер. Добавьте у регистратора A-запись: имя домена → IP сервера (показан на странице «Обзор»). Изменения DNS применяются до нескольких часов.'],
  [/certbot|сертификат/i,
   'Для Let\'s Encrypt нужны: домен, указывающий на сервер, и открытый порт 80. Самоподписанный сертификат можно выпустить без домена — браузер лишь покажет предупреждение.'],
  [/(?:nginx -t|ошибка синтаксиса|configtest)/i,
   'Панель уже откатила изменения — конфиг остался рабочим. Проверьте последние правки в редакторе конфига сайта или службы.'],
  [/(?:не установлена|не установлен|not installed)/i,
   'Установите недостающее в разделе «Система → Установка ПО» — там всё ставится в один клик.'],
  [/(?:mysqldump|pg_dump|дамп)/i,
   'Проверьте, что СУБД запущена (раздел «Службы»), и попробуйте ещё раз.'],
  [/(?:no space left|место на диске|переполнен)/i,
   'Диск заполнен. Освободите место: старые резервные копии, журналы, ненужные файлы сайтов.'],
  [/слишком много попыток/i,
   'Это защита от подбора пароля — подождите 5 минут и попробуйте снова.'],
  [/(?:connection refused|connection reset|недоступен|timed out|время ожидания)/i,
   'Похоже, служба не отвечает. Проверьте состояние служб в разделе «Службы» и их журналы.'],
  [/(?:пароль короче|пароль слишком короткий)/i,
   'Минимум 8 символов. Нажмите «сгенерировать» рядом с полем — панель создаст надёжный пароль за вас.'],
];

export function explainError(m: unknown): string {
  let msg = String(m == null ? '' : m);
  for (const [rx, hint] of ERROR_HINTS)
    if (rx.test(msg)) return msg + ' — ' + hint;
  return msg;
}

export interface ToastItem { id: number; text: string; kind: string }

import { reactive } from 'vue';

export const toasts = reactive<ToastItem[]>([]);
let seq = 0;

export function toast(msg: string, kind = 'ok'): void {
  const id = ++seq;
  toasts.push({ id, text: msg, kind });
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id);
    if (i >= 0) toasts.splice(i, 1);
  }, 5000);
}

export function toastErr(e: unknown): void {
  const err = e as { message?: string };
  toast(explainError(err.message || String(e)), 'err');
}
