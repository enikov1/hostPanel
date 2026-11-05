/* ============ Общее состояние карточки сайта (в оригинале — window._*) ============
   Вкладки карточки редактируют reactive-поля, «Сохранить» собирает их все
   сразу (как прежний siteSave, читавший поля из всех вкладок модалки). */
import { reactive } from 'vue';

export interface SiteSsl {
  kind: string;
  expires?: string;
  domains?: string[];
  [k: string]: any;
}

export interface Site {
  id: number;
  domain: string;
  parent?: number | null;
  webserver: string;
  php?: string;
  php_modules?: string[];
  node?: { enabled: boolean; version: string; port: number; script: string } | null;
  ssl: SiteSsl;
  enabled: boolean;
  maintenance: boolean;
  security_status?: string;
  disk?: number;
  disk_hist?: { t: string; mb: number }[];
  docroot?: string;
  fpm?: { pm: string; max_children: number; start_servers: number; min_spare?: number; max_spare?: number };
  perf?: { gzip?: boolean; static_cache?: boolean; hsts?: boolean; http2?: boolean };
  snippets?: { www_redirect?: boolean; admin_path?: string; admin_ip?: string; upload_size?: string };
  [k: string]: any;
}

export const WEBSERVERS: [string, string][] = [
  ['nginx', 'nginx + PHP-FPM (рекомендуется)'],
  ['nginx+apache', 'nginx + Apache (mod_php-совместимость)'],
  ['apache', 'Apache (напрямую)'],
  ['nginx+node', 'nginx + Node.js (прокси)'],
  ['static', 'Статика без PHP'],
];

export function wsLabel(ws: string): string {
  return (WEBSERVERS.find((w) => w[0] === ws) || [, '?'])[1];
}

export const siteState = reactive({
  /** текущий сайт, как его отдал сервер (обновляется после reload) */
  site: null as Site | null,
  /** версии PHP (ключи /api/php → versions), отсортированы по убыванию */
  phpVersions: [] as string[],
  moduleNames: {} as Record<string, string>,
  /** модули, доступные для выбранной версии PHP */
  modAvail: [] as string[],

  /* веб-сервер при загрузке — видимость perf-полей как в прежнем DOM */
  origWs: '',
  origHasSsl: false,

  /* редактируемые поля для siteSave */
  f_webserver: '',
  f_enabled: true,
  f_www: false,
  f_php: '',
  f_php_modules: [] as string[],
  f_fpm: { pm: 'dynamic', max_children: 10, start_servers: 3 },
  f_node: null as { enabled: boolean; version: string; port: number; script: string } | null,
  f_perf: { gzip: false, static_cache: false, hsts: false, http2: false },
  f_snippets: { www_redirect: false, admin_path: 'admin', admin_ip: '', upload_size: '' },
  fpmReco: '',
});

/** Заполнить состояние данными сайта (сбрасывает несохранённые правки —
 *  как полная перерисовка модалки в оригинале). */
export function fillSiteState(s: Site, phpData: { versions: Record<string, string[]>; module_names?: Record<string, string> }): void {
  siteState.site = s;
  const versions = Object.keys(phpData.versions || {}).sort().reverse();
  siteState.phpVersions = versions;
  siteState.moduleNames = phpData.module_names || {};
  siteState.modAvail = s.php ? (phpData.versions || {})[s.php] || [] : [];
  siteState.origWs = s.webserver;
  siteState.origHasSsl = !!(s.ssl && s.ssl.kind !== 'none');
  siteState.f_webserver = s.webserver;
  siteState.f_enabled = !!s.enabled;
  siteState.f_www = !!s.www;
  siteState.f_php = s.php || '';
  siteState.f_php_modules = [...(s.php_modules || [])];
  siteState.f_fpm = {
    pm: s.fpm ? s.fpm.pm : 'dynamic',
    max_children: s.fpm ? s.fpm.max_children : 10,
    start_servers: s.fpm ? s.fpm.start_servers : 3,
  };
  siteState.f_node = s.node
    ? { enabled: !!s.node.enabled, version: s.node.version || '20',
        port: s.node.port || 3000, script: s.node.script || 'app.js' }
    : null;
  const perf = s.perf || {};
  siteState.f_perf = {
    gzip: !!perf.gzip, static_cache: !!perf.static_cache,
    hsts: !!perf.hsts, http2: !!perf.http2,
  };
  const snip = s.snippets || {};
  siteState.f_snippets = {
    www_redirect: !!snip.www_redirect,
    admin_path: snip.admin_path || 'admin',
    admin_ip: snip.admin_ip || '',
    upload_size: snip.upload_size || '',
  };
  siteState.fpmReco = '';
}

/** Тело для POST /api/sites/update — тот же набор полей, что у siteSave. */
export function buildSaveBody(): Record<string, unknown> {
  const s = siteState.site as Site;
  const isNode = s.webserver === 'nginx+node';
  const hasSsl = !!(s.ssl && s.ssl.kind !== 'none');
  return {
    id: s.id,
    www: siteState.f_www,
    webserver: siteState.f_webserver,
    enabled: siteState.f_enabled,
    php: siteState.f_php,
    php_modules: [...siteState.f_php_modules],
    fpm: {
      pm: siteState.f_fpm.pm,
      max_children: Number(siteState.f_fpm.max_children),
      start_servers: Number(siteState.f_fpm.start_servers),
      min_spare: s.fpm ? (s.fpm.min_spare ?? 2) : 2,
      max_spare: s.fpm ? (s.fpm.max_spare ?? 5) : 5,
    },
    node: s.node ? {
      enabled: siteState.f_node ? siteState.f_node.enabled : false,
      version: siteState.f_node ? siteState.f_node.version : '20',
      port: siteState.f_node ? Number(siteState.f_node.port) : 3000,
      script: siteState.f_node ? siteState.f_node.script : 'app.js',
    } : undefined,
    perf: {
      gzip: siteState.f_perf.gzip,
      static_cache: isNode ? undefined : siteState.f_perf.static_cache,
      hsts: hasSsl ? siteState.f_perf.hsts : undefined,
      http2: hasSsl ? siteState.f_perf.http2 : undefined,
    },
    snippets: {
      www_redirect: siteState.f_snippets.www_redirect,
      admin_path: siteState.f_snippets.admin_path,
      admin_ip: siteState.f_snippets.admin_ip,
      upload_size: siteState.f_snippets.upload_size,
    },
  };
}

/** Дней до конца сертификата SSL (null — дату разобрать не удалось). */
export function sslDays(s: Site): number | null {
  if (!s.ssl || s.ssl.kind === 'none' || !s.ssl.expires) return null;
  const days = Math.round((new Date(s.ssl.expires).getTime() - Date.now()) / 86400000);
  return isNaN(days) ? null : days;
}

export function sslActive(s: Site): boolean {
  return !!(s.ssl && s.ssl.kind !== 'none');
}

export function openSiteUrl(domain: string): void {
  if (domain) window.open('http://' + domain, '_blank');
}
