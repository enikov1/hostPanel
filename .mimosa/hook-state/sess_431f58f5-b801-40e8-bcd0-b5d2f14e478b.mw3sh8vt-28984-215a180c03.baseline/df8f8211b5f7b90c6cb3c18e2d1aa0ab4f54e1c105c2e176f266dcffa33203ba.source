#!/usr/bin/env bash
# HostPanel — полное удаление панели с сервера.
# Файлы сайтов (/var/www) и бэкапы НЕ трогаются — удаляются только служба
# и сама панель. Для удаления данных используйте: rm -rf /opt/hostpanel
set -euo pipefail
PANEL_HOME="${PANEL_HOME:-/opt/hostpanel}"

echo "==> Остановка службы"
systemctl stop hostpanel 2>/dev/null || true
systemctl disable hostpanel 2>/dev/null || true
rm -f /etc/systemd/system/hostpanel.service
systemctl daemon-reload

echo "==> Удаление панели ($PANEL_HOME/panel)"
rm -rf "$PANEL_HOME/panel" "$PANEL_HOME/admin.txt" "$PANEL_HOME/admin.json"

echo "==> Удаление консольного клиента hcp"
rm -f /usr/local/bin/hcp /usr/local/bin/hcp-*

echo "Готово. Данные (state.json, бэкапы, сертификаты) остались в $PANEL_HOME —"
echo "удалите их вручную, если они больше не нужны: rm -rf $PANEL_HOME"
