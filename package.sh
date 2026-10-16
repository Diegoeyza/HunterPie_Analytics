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
cat > "$DIST/hunt-dumper/INSTALL.txt" <<'TXT'
HuntDumper — REFramework mod for Monster Hunter Wilds
=====================================================

Install
-------
1. Install REFramework for MH Wilds (dinput8.dll in the game folder).
2. Copy hunt_dumper.lua to:
     <game>\reframework\autorun\hunt_dumper.lua
   Steam path:
     ...\steamapps\common\MonsterHunterWilds\reframework\autorun\
3. Open the in-game REFramework menu -> HuntDumper to confirm it is enabled.
4. Dumps are written at quest end to:
     <game>\reframework\data\HuntExports\*.json

Notes
-----
- Load the script before a quest starts (a mid-hunt script reload resets its
  state and skips that hunt).
- Captures: quest metadata, monster id + HP curve, per-player damage totals,
  the 30 quest awards (hunter highlights), CPU-supporter flags, and the local
  player's weapon name.
- Per-player weapon classes and DPS curves come from HunterPie, not this mod.

For the full dashboard, see the project README / docs/SHARING.md.
TXT
( cd "$DIST/hunt-dumper" \
    && zip -q "../hunt-dumper-${MOD_VERSION}.zip" hunt_dumper.lua INSTALL.txt )
rm -rf "$DIST/hunt-dumper"

# 2) Full app source: exactly what git tracks (no venv/node_modules/DB).
git archive --format=zip \
  -o "$DIST/HunterPie-Analytics-src-${GIT_SHORT}.zip" HEAD

echo "Built into $DIST/:"
ls -1 "$DIST"
