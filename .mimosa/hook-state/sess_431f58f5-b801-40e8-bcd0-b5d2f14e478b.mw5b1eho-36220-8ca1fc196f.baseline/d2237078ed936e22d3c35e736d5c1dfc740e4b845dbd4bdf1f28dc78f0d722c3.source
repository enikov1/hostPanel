/* ============ Глобальное состояние приложения (Vue reactive) ============ */
import { reactive } from 'vue';

/** Данные /api/me (заполняются в App.vue после подтверждения сессии). */
export const me = reactive({
  ok: false, demo: false, version: '', www_root: '', home: '',
  expert: false, login: '', must_change_password: false,
});

/** Признак «пароль ещё стандартный» (подсказка на экране входа). */
export const session = reactive({
  defaultPw: false,
  version: '',
  /** подготовленный шаг 2FA welcome-мастера */
  wizard2fa: null as any,
});
