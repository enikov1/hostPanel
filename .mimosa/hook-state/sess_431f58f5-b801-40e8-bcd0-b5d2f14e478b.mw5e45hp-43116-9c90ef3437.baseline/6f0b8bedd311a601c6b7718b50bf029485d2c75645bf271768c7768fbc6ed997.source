/* ============ Брендовые логотипы служб ============
   id службы/модуля -> имя файла в /logos/ (simple-icons, брендовый цвет).
   Если логотипа нет — рисуем feather-иконку (fallback в BrandLogo). */

export const BRANDS: Record<string, string> = {
  nginx: 'nginx',
  apache: 'apache',
  apache2: 'apache',
  mariadb: 'mariadb',
  mysql: 'mysql',
  postgresql: 'postgresql',
  redis: 'redis',
  php: 'php',
  node: 'nodedotjs',
  nodejs: 'nodedotjs',
  cloudflare: 'cloudflare',
  git: 'git',
  letsencrypt: 'letsencrypt',
  certbot: 'letsencrypt',
  docker: 'docker',
  pma: 'php',
  joomla: 'joomla',
  drupal: 'drupal',
  dle: 'archive',
  omro: 'php',
  phpmyadmin: 'php',
  ioncube: 'php',
  geoip2: 'cloudflare',
};

/** Логотип по имени службы/пакета (nginx, apache2, php8.2-fpm, mariadb…). */
export function brandFor(name: string): string | null {
  const n = (name || '').toLowerCase();
  if (n.startsWith('php') || n.includes('php-fpm')) return 'php';
  if (n.startsWith('apache')) return 'apache';
  if (n.startsWith('nginx')) return 'nginx';
  if (n.startsWith('mariadb')) return 'mariadb';
  if (n.startsWith('mysql')) return 'mysql';
  if (n.startsWith('postgres')) return 'postgresql';
  if (n.startsWith('redis')) return 'redis';
  if (n.startsWith('memcached')) return null; // логотипа нет
  if (n.startsWith('fail2ban')) return null;
  if (n.startsWith('postfix')) return null;
  if (n.startsWith('dovecot')) return null;
  if (n.startsWith('node')) return 'nodedotjs';
  if (n === 'dle') return 'archive';
  if (n === 'omro') return 'php';
  if (n.startsWith('certbot')) return 'letsencrypt';
  if (n.startsWith('letsencrypt')) return 'letsencrypt';
  if (n.startsWith('git')) return 'git';
  return BRANDS[n] || null;
}
