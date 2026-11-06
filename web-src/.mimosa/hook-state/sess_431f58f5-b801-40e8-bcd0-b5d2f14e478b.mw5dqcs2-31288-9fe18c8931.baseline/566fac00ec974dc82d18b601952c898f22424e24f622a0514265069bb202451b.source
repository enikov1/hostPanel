/* ============ Пароли: генерация и оценка силы (UI — в PwField.vue) ============ */

export function genPassword(len = 16): string {
  const a = 'abcdefghjkmnpqrstuvwxyz', A = 'ABCDEFGHJKMNPQRSTUVWXYZ',
        d = '23456789', s = '!@#$%&*_-+=';
  const all = a + A + d + s;
  const pick = (set: string) => set[Math.floor(Math.random() * set.length)];
  let p = pick(a) + pick(A) + pick(d) + pick(s);
  for (let i = p.length; i < len; i++) p += pick(all);
  return p.split('').sort(() => Math.random() - 0.5).join('');
}

export function pwStrength(pw: string): number {
  if (!pw) return 0;
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  return Math.min(3, Math.floor(score / 2) + (score >= 4 ? 1 : 0));
}
