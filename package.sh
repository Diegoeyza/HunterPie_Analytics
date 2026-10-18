#!/usr/bin/env bash
# Build shareable bundles into dist/:
#   hunt-dumper-<version>.zip          REFramework mod (drop-in) + install notes
#   HunterPie-Analytics-src-<sha>.zip  full app source (git-tracked files only)
set -euo pipefail
cd "$(dirname "$0")"

command -v zip >/dev/null || { echo "error: 'zip' is required" >&2; exit 1; }

MOD_VERSION="$(sed -n 's/^local VERSION = "\([^"]*\)".*/\1/p' \
  reframework/hunt_dumper.lua | head -1)"
GIT_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
DIST="dist"

rm -rf "$DIST"
mkdir -p "$DIST/hunt-dumper"

# 1) REFramework mod bundle: the single Lua file + install notes.
cp reframework/hunt_dumper.lua "$DIST/hunt-dumper/hunt_dumper.lua"
cp reframework/INSTALL.txt "$DIST/hunt-dumper/INSTALL.txt"
( cd "$DIST/hunt-dumper" \
    && zip -q "../hunt-dumper-${MOD_VERSION}.zip" hunt_dumper.lua INSTALL.txt )
rm -rf "$DIST/hunt-dumper"

# 2) Full app source: exactly what git tracks (no venv/node_modules/DB).
git archive --format=zip \
  -o "$DIST/HunterPie-Analytics-src-${GIT_SHORT}.zip" HEAD

echo "Built into $DIST/:"
ls -1 "$DIST"
