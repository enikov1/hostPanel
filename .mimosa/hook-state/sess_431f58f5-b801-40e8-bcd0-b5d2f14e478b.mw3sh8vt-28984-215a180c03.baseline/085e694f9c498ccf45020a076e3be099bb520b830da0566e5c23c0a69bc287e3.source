/* ============ Роутер: реальные URL вместо #решётки ============ */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { me } from './stores';

export interface NavItem {
  path: string;
  t: string;
  ic: string;
  g: string;
  d: string;
  expert?: boolean;
}

/** Порядок и группы совпадают с прежним меню панели. */
export const NAV: NavItem[] = [
  { path: '/', t: 'Обзор', ic: 'activity', g: 'Главное',
    d: 'Состояние сервера и первые шаги' },
  { path: '/health', t: 'Живучесть', ic: 'shield', g: 'Главное',
    d: 'Работают ли ваши сайты прямо сейчас' },
  { path: '/services', t: 'Службы', ic: 'server', g: 'Главное',
    d: 'Что запущено на сервере' },
  { path: '/sites', t: 'Сайты', ic: 'globe', g: 'Ваш проект',
    d: 'Создание и настройка сайтов' },
  { path: '/databases', t: 'Базы данных', ic: 'db', g: 'Ваш проект',
    d: 'MariaDB и PostgreSQL: создание, пароли, импорт/экспорт' },
  { path: '/mail', t: 'Почта', ic: 'ext', g: 'Ваш проект',
    d: 'Почтовые ящики на вашем домене' },
  { path: '/files', t: 'Файловый менеджер', ic: 'folder', g: 'Ваш проект',
    d: 'Файлы сайтов: загрузка и правка' },
  { path: '/backups', t: 'Резервные копии', ic: 'archive', g: 'Ваш проект',
    d: 'Копии сайтов и баз — восстановление в один клик' },
  { path: '/certificates', t: 'SSL-сертификаты', ic: 'lock', g: 'Ваш проект',
    d: 'Управление сертификатами всех сайтов' },
  { path: '/cron', t: 'Планировщик', ic: 'clock', g: 'Ваш проект',
    d: 'Задания по расписанию' },
  { path: '/software', t: 'Установка ПО', ic: 'pkg', g: 'Система',
    d: 'PHP, базы данных и другие программы' },
  { path: '/software/settings', t: 'Настройки ПО', ic: 'gear', g: 'Система',
    d: 'Пароли, параметры и конфиги установленных служб' },
  { path: '/packages', t: 'Пакеты и обновления', ic: 'pkg', g: 'Система',
    d: 'Обновления сервера и PHP-модули' },
  { path: '/firewall', t: 'Брандмауэр', ic: 'shield', g: 'Система',
    d: 'Какие порты открыты наружу' },
  { path: '/terminal', t: 'Командная строка', ic: 'term', g: 'Система',
    d: 'Для опытных: команды прямо на сервере', expert: true },
  { path: '/settings', t: 'Настройки', ic: 'gear', g: 'Система',
    d: 'Пароль, тема и параметры панели' },
];

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'overview',
    component: () => import('./views/OverviewView.vue'),
    meta: { t: 'Обзор', d: 'Состояние сервера и первые шаги' } },
  { path: '/health', name: 'health',
    component: () => import('./views/HealthView.vue'),
    meta: { t: 'Живучесть', d: 'Работают ли ваши сайты прямо сейчас' } },
  { path: '/services', name: 'services',
    component: () => import('./views/ServicesView.vue'),
    meta: { t: 'Службы', d: 'Что запущено на сервере' } },
  { path: '/sites', name: 'sites',
    component: () => import('./views/SitesView.vue'),
    meta: { t: 'Сайты', d: 'Создание и настройка сайтов' } },
  { path: '/sites/:id', name: 'site',
    component: () => import('./views/SiteDetailView.vue'),
    meta: { t: 'Сайт', d: 'Карточка сайта' } },
  { path: '/databases', name: 'dbs',
    component: () => import('./views/DbsView.vue'),
    meta: { t: 'Базы данных', d: 'MariaDB и PostgreSQL: создание, пароли, импорт/экспорт' } },
  { path: '/mail', name: 'mail',
    component: () => import('./views/MailView.vue'),
    meta: { t: 'Почта', d: 'Почтовые ящики на вашем домене' } },
  { path: '/files', name: 'files',
    component: () => import('./views/FilesView.vue'),
    meta: { t: 'Файловый менеджер', d: 'Файлы сайтов: загрузка и правка' } },
  { path: '/backups', name: 'backups',
    component: () => import('./views/BackupsView.vue'),
    meta: { t: 'Резервные копии', d: 'Копии сайтов и баз — восстановление в один клик' } },
  { path: '/certificates', name: 'certs',
    component: () => import('./views/CertsView.vue'),
    meta: { t: 'SSL-сертификаты', d: 'Управление сертификатами всех сайтов' } },
  { path: '/cron', name: 'cron',
    component: () => import('./views/CronView.vue'),
    meta: { t: 'Планировщик', d: 'Задания по расписанию' } },
  { path: '/software', name: 'software',
    component: () => import('./views/SoftwareView.vue'),
    meta: { t: 'Установка ПО', d: 'PHP, базы данных и другие программы' } },
  { path: '/software/settings', name: 'swset',
    component: () => import('./views/SwSetView.vue'),
    meta: { t: 'Настройки ПО', d: 'Пароли, параметры и конфиги установленных служб' } },
  { path: '/packages', name: 'packages',
    component: () => import('./views/PackagesView.vue'),
    meta: { t: 'Пакеты и обновления', d: 'Обновления сервера и PHP-модули' } },
  { path: '/firewall', name: 'firewall',
    component: () => import('./views/FirewallView.vue'),
    meta: { t: 'Брандмауэр', d: 'Какие порты открыты наружу' } },
  { path: '/terminal', name: 'term',
    component: () => import('./views/TermView.vue'),
    meta: { t: 'Командная строка', d: 'Для опытных: команды прямо на сервере' } },
  { path: '/settings', name: 'settings',
    component: () => import('./views/SettingsView.vue'),
    meta: { t: 'Настройки', d: 'Пароль, тема и параметры панели' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 }; },
});

/** Простой режим скрывает экспертные разделы. */
export function navVisible(): NavItem[] {
  return NAV.filter((n) => !n.expert || me.expert);
}

/** Для поиска/редиректов: путь раздела по его прежнему id. */
export function navPath(id: string): string {
  return (NAV.find((n) => n.path === '/' + id) || NAV[0]).path;
}
