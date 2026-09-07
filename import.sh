#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

HUNTS_DB="${HUNTS_DB:-backend/hunts.db}"
HUNT_EXPORTS="/mnt/c/Program Files/HunterPie/HuntExports"

abspath() {
  case "$1" in
    /*) printf '%s' "$1" ;;
    *) printf '%s/%s' "$(pwd)" "$1" ;;
  esac
}

if [ "${1:-}" = "--dir" ]; then
  SRC=(--dir "$(abspath "${2:-$HUNT_EXPORTS}")")
elif [ "${1:-}" = "--file" ]; then
  SRC=(--file "$(abspath "${2:?pass a .json path}")")
elif [ -d "$HUNT_EXPORTS" ]; then
  echo "Importing from $HUNT_EXPORTS ..."
  SRC=(--dir "$(abspath "$HUNT_EXPORTS")")
elif [ -d "seeds" ] && ls seeds/*.json >/dev/null 2>&1; then
  echo "Importing from seeds/ ..."
  SRC=(--dir "$(abspath seeds)")
else
  echo "Usage: ./import.sh [--file path.json | [--dir /path/to/HuntExports]]"
  echo ""
  echo "No HuntExports folder found at:"
  echo "  $HUNT_EXPORTS"
  echo ""
  echo "Pass --dir to specify the correct path, or place .json files in seeds/."
  exit 1
fi

# The app package lives in backend/, so run from there.
# Resolve all paths BEFORE cd'ing (HUNTS_DB is relative to the repo root).
DB_ABS="$(abspath "$HUNTS_DB")"
(cd backend && ../.venv/bin/python -m app.import_hunt --db "$DB_ABS" "${SRC[@]}")
