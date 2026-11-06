/* ============ Типы данных API для страниц Обзор / Живучесть / Службы ============ */

export interface SvcInfo {
  name: string;
  state: string;
  exists: boolean;
  uptime_sec?: number;
  uptime_h?: string;
  since?: string;
}

export interface Metrics {
  cpu: number;
  cores: number;
  hist: number[];
  ram: { used: number; total: number; percent: number };
  disk: { used: number; total: number; percent: number };
  net: { in_mbit: number; out_mbit: number };
  uptime_sec: number;
  load: number[];
}

export interface NotificationItem {
  ts: string;
  text: string;
  level?: string;
}

export interface OverviewData {
  metrics: Metrics;
  services: SvcInfo[];
  sites_count: number;
  sites_enabled: number;
  sites_maintenance: number;
  dbs_count: number;
  backups_count: number;
  sites_load?: { cpu: number; mem_mb: number; php_workers: number };
  notifications?: NotificationItem[];
}

export interface SiteRow {
  id: number;
  domain: string;
  enabled: boolean;
  maintenance: boolean;
  [k: string]: any;
}

export interface HealthLast {
  ok: boolean;
  ms: number;
  code?: number;
  ext?: { ok: boolean };
}

export interface HealthReport {
  uptime_24h?: number | null;
  uptime_7d?: number | null;
  last?: HealthLast;
  incidents?: { start: string }[];
  series?: { ok: boolean; ms: number }[];
}
