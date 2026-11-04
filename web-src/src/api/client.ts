/* ============ API-клиент: fetch + JSON + обработка ошибок ============ */

/** Хук «сессия истекла» — регистрируется в App.vue (переход на экран входа). */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHook(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(message: string) { super(message); }
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
}

/** Аутентификация — HttpOnly-cookie (SameSite=Strict); CSRF на сервере
 *  проверяется по Origin, токен в localStorage не хранится. */
export async function api(path: string, opts: ApiOptions = {}): Promise<any> {
  const init: RequestInit = {
    method: opts.method || 'GET',
    headers: {} as Record<string, string>,
  };
  if (opts.body !== undefined) {
    init.method = opts.method || 'POST';
    (init.headers as Record<string, string>)['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  const r = await fetch(path, init);
  if (r.status === 401) {
    if (onUnauthorized) onUnauthorized();
    throw new ApiError('требуется вход');
  }
  const j = await r.json();
  if (j && j.ok === false) throw new ApiError(j.error || 'ошибка запроса');
  return j;
}

/** POST multipart/form-data (загрузка файлов, импорт). */
export async function apiForm(path: string, fd: FormData): Promise<any> {
  const r = await fetch(path, { method: 'POST', body: fd });
  const j = await r.json();
  if (!j.ok) throw new ApiError(j.error || 'ошибка запроса');
  return j;
}

/** Скачивание файла через API с проверкой ошибок. */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const r = await fetch(url);
  const ct = r.headers.get('Content-Type') || '';
  if (ct.includes('application/json')) {
    const j = await r.json();
    throw new ApiError(j.error || 'ошибка скачивания');
  }
  const blob = await r.blob();
  const cd = r.headers.get('Content-Disposition') || '';
  const m = cd.match(/filename="([^"]+)"/);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : fallbackName;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}
