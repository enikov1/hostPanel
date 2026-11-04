/* ============ Графики на canvas: линия и доступность ============ */

export function cssVar(n: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(n).trim();
}

export interface Series {
  data: number[];
  color: string;
  fill?: boolean;
}

export interface LineOptions {
  max?: number;
  labels?: string[];
}

export function drawLine(cv: HTMLCanvasElement | null, series: Series[], opts: LineOptions = {}): void {
  if (!cv) return;
  const alive = (series || []).filter((s) => s && Array.isArray(s.data) && s.data.length);
  if (!alive.length) return; // пустые series/data — рисовать нечего
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 300, h = cv.clientHeight || 200;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext('2d')!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const padL = 38, padR = 8, padT = 8, padB = 20;
  const allVals = alive.reduce<number[]>((a, s) => a.concat(s.data), []);
  const max = opts.max || Math.max(...allVals, 1) * 1.15;
  const n = alive[0].data.length;
  const X = (i: number) => padL + (w - padL - padR) * (n < 2 ? 0 : i / (n - 1));
  const Y = (v: number) => padT + (h - padT - padB) * (1 - Math.min(v / max, 1));
  ctx.strokeStyle = cssVar('--border'); ctx.fillStyle = cssVar('--muted');
  ctx.font = '10.5px sans-serif'; ctx.lineWidth = 1;
  for (let g = 0; g <= 4; g++) {
    const y = padT + (h - padT - padB) * g / 4;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
    ctx.textAlign = 'right'; ctx.fillText(String(Math.round(max * (1 - g / 4))), padL - 5, y + 3);
  }
  alive.forEach((s) => {
    // невалидный цвет (например пустой cssVar) не должен ронять отрисовку
    let color = s.color || '#888';
    try { ctx.fillStyle = color; } catch { color = '#888'; }
    if (s.fill) {
      try {
        const grad = ctx.createLinearGradient(0, padT, 0, h - padB)!;
        grad.addColorStop(0, color + '44'); grad.addColorStop(1, color + '00');
        ctx.beginPath(); ctx.moveTo(X(0), Y(s.data[0]));
        for (let i = 1; i < n; i++) ctx.lineTo(X(i), Y(s.data[i]));
        ctx.lineTo(X(n - 1), h - padB); ctx.lineTo(X(0), h - padB); ctx.closePath();
        ctx.fillStyle = grad; ctx.fill();
      } catch { /* невалидный цвет — заливку пропускаем */ }
    }
    ctx.beginPath(); ctx.moveTo(X(0), Y(s.data[0]));
    for (let i = 1; i < n; i++) ctx.lineTo(X(i), Y(s.data[i]));
    ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.stroke();
  });
  if (opts.labels && opts.labels.length) {
    ctx.textAlign = 'left'; ctx.fillStyle = cssVar('--faint');
    ctx.fillText(opts.labels[0], padL, h - 6);
    ctx.textAlign = 'right'; ctx.fillText(opts.labels[opts.labels.length - 1], w - padR, h - 6);
  }
}

export interface UptimePoint { ok: boolean; ms: number }

/** Столбчатый график доступности (живучесть): ok=зелёный, fail=красный. */
export function drawUptime(cv: HTMLCanvasElement | null, series: UptimePoint[]): void {
  if (!cv) return;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 300, h = cv.clientHeight || 60;
  cv.width = w * dpr; cv.height = h * dpr;
  const ctx = cv.getContext('2d')!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const n = series.length;
  if (!n) return;
  const bw = Math.max(2, Math.min(10, (w - 4) / n - 2));
  series.forEach((v, i) => {
    ctx.fillStyle = v.ok ? cssVar('--ok') : cssVar('--err');
    const bh = v.ok ? Math.max(4, (h - 6) * Math.min(1, v.ms / 300)) : (h - 6);
    ctx.fillRect(2 + i * ((w - 4) / n), h - 3 - bh, bw, bh);
  });
}
