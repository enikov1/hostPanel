/* ============ Клиентский расчёт следующего запуска cron-выражения ============ */

/**
 * Разбор одного поля cron в множество допустимых значений.
 * Поддержка: звёздочка, шаг «звёздочка/N», число, списки «1,15»,
 * диапазоны «1-5», диапазоны и числа с шагом «1-5/2», «5/10».
 * Возвращает null при неверном поле.
 */
function parseField(field: string, min: number, max: number): Set<number> | null {
  const out = new Set<number>();
  for (const part of (field || '').split(',')) {
    let body = part;
    let step = 1;
    const sm = part.match(/^(.*)\/(\d+)$/);
    if (sm) { body = sm[1]; step = Math.max(1, +sm[2]); }
    let lo: number, hi: number;
    if (body === '*') { lo = min; hi = max; }
    else {
      const rm = body.match(/^(\d+)-(\d+)$/);
      if (rm) { lo = +rm[1]; hi = +rm[2]; }
      else if (/^\d+$/.test(body)) { lo = hi = +body; }
      else return null;
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
    if (lo < min || hi > max || lo > hi) return null;
    for (let v = lo; v <= hi; v += step) out.add(v);
  }
  return out.size ? out : null;
}

/**
 * Следующий запуск для стандартного 5-полей cron-выражения
 * (минуты часы день-месяца месяц день-недели).
 * День недели: 0–7, где 0 и 7 — воскресенье.
 * Умный расчёт по полям: перебор дней (горизонт 4 года — високосный 29 февраля)
 * с быстрым отсевом по месяцам/дням, внутри дня — ближайшие часы/минуты.
 * Возвращает Date или null (неверное выражение / запусков нет в горизонте).
 */
export function nextRunCron(expr: string, from: Date = new Date()): Date | null {
  const parts = (expr || '').trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const mins = parseField(parts[0], 0, 59);
  const hours = parseField(parts[1], 0, 23);
  const doms = parseField(parts[2], 1, 31);
  const mons = parseField(parts[3], 1, 12);
  const dowsRaw = parseField(parts[4], 0, 7);
  if (!mins || !hours || !doms || !mons || !dowsRaw) return null;
  const dows = new Set<number>();
  for (const v of dowsRaw) dows.add(v % 7); // 7 → 0 (воскресенье)

  const domAny = parts[2] === '*';
  const dowAny = parts[4] === '*';

  const start = new Date(from.getTime());
  start.setSeconds(0, 0);

  const hoursAsc = [...hours].sort((a, b) => a - b);
  const minsAsc = [...mins].sort((a, b) => a - b);

  for (let dOff = 0; dOff < 1461; dOff++) {
    const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + dOff);
    if (!mons.has(day.getMonth() + 1)) continue;
    // 29 февраля и другие несуществующие даты отсекаются самим Date:
    // getDate() вернёт реальный день месяца (1–28/29/30/31)
    const domOk = doms.has(day.getDate());
    const dowOk = dows.has(day.getDay());
    // стандартный cron: если ограничены оба поля (день месяца и день недели) —
    // достаточно совпадения любого из них
    const dayOk = (!domAny && !dowAny) ? (domOk || dowOk)
      : domAny ? dowOk
      : dowAny ? domOk
      : (domOk && dowOk);
    if (!dayOk) continue;

    const sameDay = dOff === 0;
    for (const h of hoursAsc) {
      if (sameDay && h < start.getHours()) continue;
      for (const m of minsAsc) {
        if (sameDay && h === start.getHours() && m < start.getMinutes()) continue;
        return new Date(day.getFullYear(), day.getMonth(), day.getDate(), h, m, 0);
      }
    }
  }
  return null;
}
