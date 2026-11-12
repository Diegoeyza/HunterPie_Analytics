#!/usr/bin/env bash
# Copy the bundled HuntDumper mod into every Steam copy of MH Wilds found.
#
#   ./install-mod.sh          install/update the mod next to REFramework
#
# Wilds runs through Proton, but its game folder is a normal Linux directory,
# so this works without Wine. REFramework itself must already be installed
# (dinput8.dll in the game folder).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LUA="$HERE/hunt_dumper.lua"
[ -f "$LUA" ] || { echo "error: hunt_dumper.lua is missing from the bundle." >&2; exit 1; }

roots=()
for r in "$HOME/.steam/steam" "$HOME/.local/share/Steam" \
         "$HOME/.var/app/com.valvesoftware.Steam/data/Steam" \
         "$HOME/snap/steam/common/.local/share/Steam"; do
  [ -d "$r" ] && roots+=("$r")
done
# Libraries listed in libraryfolders.vdf (extra drives, SD card, etc.).
for r in "${roots[@]}"; do
  vdf="$r/steamapps/libraryfolders.vdf"
  [ -f "$vdf" ] || continue
  while IFS= read -r lib; do
    [ -d "$lib" ] && roots+=("$lib")
  done < <(sed -n 's/.*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$vdf")
done

installed=0
for r in "${roots[@]}"; do
  game="$r/steamapps/common/MonsterHunterWilds"
  [ -d "$game" ] || continue
  if [ ! -d "$game/reframework" ]; then
    echo "Found $game but REFramework is not installed there — skipping."
    echo "Install REFramework for Wilds first, then re-run this script."
    continue
  fi
  mkdir -p "$game/reframework/autorun"
  cp "$LUA" "$game/reframework/autorun/hunt_dumper.lua"
  echo "Installed mod into $game/reframework/autorun/hunt_dumper.lua"
  installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
  echo "No Monster Hunter Wilds install was found under the Steam libraries."
  echo "Extract HuntDumper-*.zip into your game folder manually instead:"
  echo "  <game>/reframework/autorun/hunt_dumper.lua"
  exit 1
fi

echo
echo "Start a quest with the mod loaded; dumps land in"
echo "  <game>/reframework/data/HuntExports/"
echo "HunterPie Analytics picks that folder up automatically."
