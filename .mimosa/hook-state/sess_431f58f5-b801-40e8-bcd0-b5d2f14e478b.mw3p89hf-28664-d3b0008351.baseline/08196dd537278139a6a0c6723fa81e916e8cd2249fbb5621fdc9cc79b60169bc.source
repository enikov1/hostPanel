/* ============ Подтверждения: глобальный reactive-сторе + ConfirmHost ============ */
import { reactive } from 'vue';

interface ConfirmState {
  open: boolean;
  title: string;
  text: string;
  danger: boolean;
  onOk: (() => void) | null;
}

export const confirmState = reactive<ConfirmState>({
  open: false, title: '', text: '', danger: true, onOk: null,
});

export function confirmDlg(title: string, text: string,
                           onOk: () => void, danger = true): void {
  confirmState.title = title;
  confirmState.text = text;
  confirmState.danger = danger;
  confirmState.onOk = onOk;
  confirmState.open = true;
}

export function confirmAccept(): void {
  const fn = confirmState.onOk;
  confirmState.open = false;
  confirmState.onOk = null;
  if (fn) fn();
}

export function confirmCancel(): void {
  confirmState.open = false;
  confirmState.onOk = null;
}
