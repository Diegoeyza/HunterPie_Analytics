#!/usr/bin/env bash
# HunterPie Analytics — per-user Linux install (no root, no Python needed).
#
#   ./install.sh              install for the current user
#   ./install.sh --uninstall  remove the app (hunt data is kept)
#
# Installs into ${XDG_DATA_HOME:-~/.local/share}/hunterpie-analytics, links
# `hunterpie-analytics` into ~/.local/bin, and adds a desktop entry + icon.
set -euo pipefail

APP="HunterPieAnalytics"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA_HOME/hunterpie-analytics"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
DESKTOP_FILE="$APP_DIR/hunterpie-analytics.desktop"
ICON_FILE="$ICON_DIR/hunterpie-analytics.svg"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-install}" = "--uninstall" ]; then
  rm -rf "$PREFIX"
  rm -f "$BIN_DIR/hunterpie-analytics" "$DESKTOP_FILE" "$ICON_FILE"
  command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
  echo "Removed HunterPie Analytics. Hunt history is kept in $DATA_HOME/$APP."
  exit 0
fi

if [ ! -x "$HERE/$APP" ]; then
  echo "error: $HERE/$APP is missing — run this from the extracted folder." >&2
  exit 1
fi

mkdir -p "$PREFIX" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"
rm -rf "${PREFIX:?}"/*
cp -a "$HERE"/. "$PREFIX"/
chmod +x "$PREFIX/$APP" "$PREFIX/install.sh" 2>/dev/null || true
ln -sf "$PREFIX/$APP" "$BIN_DIR/hunterpie-analytics"
cp "$HERE/icon.svg" "$ICON_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HunterPie Analytics
Comment=Monster Hunter Wilds hunt analytics
Exec="$PREFIX/$APP"
Icon=$ICON_FILE
Terminal=false
Categories=Game;Utility;
StartupWMClass=HunterPieAnalytics
EOF

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

case ":$PATH:" in
  *":$BIN_DIR:"*) run_hint="hunterpie-analytics" ;;
  *) run_hint="$BIN_DIR/hunterpie-analytics" ;;
esac

echo "Installed to $PREFIX"
echo "Run: $run_hint    (or open HunterPie Analytics from your app menu)"
echo
echo "Your hunt data lives in $DATA_HOME/$APP and survives updates/uninstalls."
