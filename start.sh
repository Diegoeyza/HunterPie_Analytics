#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HUNTS_DB="${HUNTS_DB:-backend/hunts.db}"

# Start API
echo "Starting API on :$PORT ..."
cd backend
../.venv/bin/python -m app.api &
API_PID=$!
cd ..

# Wait for API
for i in $(seq 1 15); do
  curl -s -o /dev/null "http://localhost:$PORT/api/health" 2>/dev/null && break
  sleep 1
done

# Start dashboard
echo "Starting dashboard on :3000 ..."
cd dashboard
npx next dev -p 3000 &
DASH_PID=$!
cd ..

echo ""
echo "  API:      http://localhost:$PORT"
echo "  Dashboard: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $API_PID $DASH_PID 2>/dev/null" EXIT
wait
