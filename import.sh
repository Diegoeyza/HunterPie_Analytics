#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

HUNTS_DB="${HUNTS_DB:-backend/hunts.db}"
# Ingestion sources. Either may be absent (HunterPie fork and/or the
# REFramework mod). HunterPie is scanned first so its richer dump wins ties.
PIE_EXPORTS="/mnt/c/Program Files/HunterPie/HuntExports"
RF_EXPORTS="/mnt/c/Program Files (x86)/Steam/steamapps/common/MonsterHunterWilds/reframework/data/HuntExports"

abspath() {
  case "$1" in
    /*) printf '%s' "$1" ;;
    *) printf '%s/%s' "$(pwd)" "$1" ;;
  esac
}

if [ "${1:-}" = "--dir" ]; then
  SRC=(--dir "$(abspath "${2:-}")")
elif [ "${1:-}" = "--file" ]; then
  SRC=(--file "$(abspath "${2:?pass a .json path}")")
else
  SRC=()
  for d in "$PIE_EXPORTS" "$RF_EXPORTS"; do
    if [ -d "$d" ]; then SRC+=(--dir "$(abspath "$d")"); fi
  done
  if [ ${#SRC[@]} -eq 0 ]; then
    if [ -d seeds ] && ls seeds/*.json >/dev/null 2>&1; then
      echo "No export dirs found; importing seeds/ ..."
      SRC=(--dir "$(abspath seeds)")
    else
      echo "No HuntExports found at:"
      echo "  $PIE_EXPORTS"
      echo "  $RF_EXPORTS"
      echo ""
      echo "Pass --dir/--file, or place .json files in seeds/."
      exit 1
    fi
  fi
fi

# The app package lives in backend/, so run from there.
# Resolve all paths BEFORE cd'ing (HUNTS_DB is relative to the repo root).
DB_ABS="$(abspath "$HUNTS_DB")"
(cd backend && ../.venv/bin/python -m app.import_hunt --db "$DB_ABS" "${SRC[@]}")
