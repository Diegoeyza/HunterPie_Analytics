#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

HUNTS_DB="${HUNTS_DB:-backend/hunts.db}"
HUNT_EXPORTS="/mnt/c/Program Files/HunterPie/HuntExports"

if [ "${1:-}" = "--dir" ]; then
  HUNT_EXPORTS="${2:-$HUNT_EXPORTS}"
elif [ "${1:-}" = "--file" ]; then
  .venv/bin/python -m app.import_hunt --db "$HUNTS_DB" --file "$2"
  exit 0
elif [ -d "$HUNT_EXPORTS" ]; then
  echo "Importing from $HUNT_EXPORTS ..."
else
  echo "Usage: ./import.sh [--file path.json | [--dir /path/to/HuntExports]]"
  echo ""
  echo "No HuntExports folder found at:"
  echo "  $HUNT_EXPORTS"
  echo ""
  echo "Pass --dir to specify the correct path."
  exit 1
fi

.venv/bin/python -m app.import_hunt --db "$HUNTS_DB" --dir "$HUNT_EXPORTS"
