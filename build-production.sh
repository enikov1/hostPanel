#!/bin/bash
# ============================================================
# Сборка папки production — готового дистрибутива HostPanel.
#
# Что делает:
#   1. Собирает фронтенд (Vue) из vue-src -> dist
#   2. Собирает production/:
#        install.sh, uninstall.sh, hcp, VERSION, README.md
#        panel/    — код панели Python + web/ (собранный фронтенд)
#        hostpanel-<версия>.tar.gz — всё одним архивом для закидывания на сервер
#   3. Всё, что в production/ — можно сразу закидывать на сервер:
#        scp production/hostpanel-*.tar.gz root@СЕРВЕР:/root/
#        ssh root@СЕРВЕР 'cd /root && tar xzf hostpanel-*.tar.gz && cd hostpanel-* && sudo bash install.sh'
#
# Запуск:  bash build-production.sh          (с пересборкой фронтенда)
#          SKIP_BUILD=1 bash build-production.sh   (взять готовый dist)
# ============================================================
set -e
cd "$(dirname "$0")"

ROOT="$(pwd)"
VUE="$ROOT/vue-src"
SRC_PANEL="$ROOT/server-pull/panel"
PROD="$ROOT/production"

# ---------- версия ----------
VER="$(cat "$ROOT/VERSION" | tr -d '[:space:]')"
echo "==> HostPanel v$VER — сборка production"

# ---------- 1. фронтенд ----------
if [ "${SKIP_BUILD:-0}" != "1" ]; then
    echo "==> Сборка фронтенда (vue-src: npm run build)"
    (cd "$VUE" && npm run build)
else
    echo "==> SKIP_BUILD=1 — использую готовый vue-src/dist"
fi
if [ ! -f "$VUE/dist/index.html" ]; then
    echo "ОШИБКА: нет vue-src/dist/index.html — сначала соберите фронтенд" >&2
    exit 1
fi

# ---------- 2. очистка и сборка production ----------
echo "==> Сборка $PROD"
# каталог не удаляем целиком (может быть занят открытым проводником/шеллом),
# чистим только содержимое
mkdir -p "$PROD"
find "$PROD" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$PROD/panel"

# установщики и CLI
for f in install.sh uninstall.sh hcp README.md VERSION; do
    [ -f "$ROOT/$f" ] && cp "$ROOT/$f" "$PROD/"
done

# код панели (Python) без мусора — содержимое src/panel -> production/panel
cp -r "$SRC_PANEL/." "$PROD/panel/"
cd "$PROD/panel"
rm -rf __pycache__ web-src web-old web-backup-old
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true
find . -name '*.bak*' -delete 2>/dev/null || true

# собранный фронтенд: заменяем web/ целиком свежей сборкой
rm -rf "$PROD/panel/web"
cp -r "$VUE/dist" "$PROD/panel/web"
cd "$ROOT"

# ---------- 3. архив одним файлом ----------
TARBALL="$PROD/hostpanel-$VER.tar.gz"
echo "==> Архив $TARBALL"
STAGE="$ROOT/.prod-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/hostpanel-$VER"
cp -r "$PROD/." "$STAGE/hostpanel-$VER/"
rm -f "$PROD"/hostpanel-*.tar.gz
tar czf "$TARBALL" -C "$STAGE" "hostpanel-$VER"
rm -rf "$STAGE"

# ---------- итог ----------
echo
echo "============================================================"
echo "Готово: $PROD"
echo
ls -la "$PROD"
echo
echo "Установка на чистый сервер (Ubuntu/Debian):"
echo "  scp $PROD/hostpanel-$VER.tar.gz root@IP:/root/"
echo "  ssh root@IP 'apt -y install curl && cd /root && \\"
echo "       tar xzf hostpanel-$VER.tar.gz && cd hostpanel-$VER && bash install.sh'"
echo
echo "Пароль админа после установки: cat /opt/hostpanel/admin.txt"
echo "============================================================"
