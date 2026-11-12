#!/usr/bin/env bash
# Build the Linux bundle: PyInstaller onedir app + static dashboard + mod.
#
#   .venv must have backend/requirements.txt + packaging/requirements-pack.txt
#   (pywebview + pyinstaller). Run from anywhere; output goes to
#   dist/linux/HunterPieAnalytics-linux-<version>.tar.gz
#
# Build on the OLDEST glibc you want to support: the frozen interpreter
# requires >= the build machine's glibc. CI uses ubuntu-22.04 (glibc 2.35).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(sed -n 's/^APP_VERSION = "\([^"]*\)".*/\1/p' backend/app/version.py)"
MOD_VERSION="$(sed -n 's/^local VERSION = "\([^"]*\)".*/\1/p' \
  reframework/hunt_dumper.lua | head -1)"
PY="${PYTHON:-.venv/bin/python}"
ROOT="$PWD"
BUILD="build/linux"
OUT="dist/linux"
APP="HunterPieAnalytics"
PKG="$ROOT/$BUILD/$APP"
PYDIST="$BUILD/pyinstaller-dist"

command -v npm >/dev/null || { echo "error: npm is required" >&2; exit 1; }
command -v zip >/dev/null || { echo "error: 'zip' is required" >&2; exit 1; }
"$PY" -c "import PyInstaller" 2>/dev/null \
  || { echo "error: install packaging/requirements-pack.txt into the venv" >&2; exit 1; }

echo "==> dashboard static export"
NEXT_OUTPUT=export npm run build --prefix dashboard

echo "==> PyInstaller onedir"
"$PY" -m PyInstaller --noconfirm --clean \
  --distpath "$PYDIST" --workpath "$BUILD/pyinstaller-work" \
  packaging/HunterPieAnalytics.spec

echo "==> assembling bundle"
rm -rf "$PKG" "$OUT" "$BUILD/nexus"
mkdir -p "$PKG" "$OUT"
cp -a "$PYDIST/$APP/." "$PKG/"
cp packaging/linux/install.sh packaging/linux/install-mod.sh \
   packaging/linux/README.txt "$PKG/"
cp dashboard/app/icon.svg "$PKG/icon.svg"
chmod +x "$PKG/install.sh" "$PKG/install-mod.sh" "$PKG/$APP"

# Capture mod: game-folder zip (Nexus/Vortex) + bare Lua for install-mod.sh.
cp reframework/hunt_dumper.lua "$PKG/hunt_dumper.lua"
mkdir -p "$BUILD/nexus/reframework/autorun"
cp reframework/hunt_dumper.lua "$BUILD/nexus/reframework/autorun/hunt_dumper.lua"
cp packaging/nexus/README.txt "$BUILD/nexus/README.txt"
( cd "$BUILD/nexus" \
    && zip -q -r "$PKG/HuntDumper-$MOD_VERSION.zip" . )

TARBALL="$OUT/HunterPieAnalytics-linux-$VERSION.tar.gz"
tar -C "$BUILD" -czf "$TARBALL" "$APP"

echo
echo "Built $TARBALL"
echo "  app:     $(du -h "$PKG/$APP" | cut -f1)"
echo "  bundle:  $(du -sh "$PKG" | cut -f1)"
echo "  sha256:  $(sha256sum "$TARBALL" | cut -d' ' -f1)"
