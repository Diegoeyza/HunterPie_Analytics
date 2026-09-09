#!/usr/bin/env bash
set -euo pipefail

# Kill any stale processes
for pid in $(pgrep -f "app.api" 2>/dev/null || true); do kill -9 "$pid" 2>/dev/null || true; done
for pid in $(pgrep -f "next dev" 2>/dev/null || true); do kill -9 "$pid" 2>/dev/null || true; done
sleep 1

cd /workspace/HunterPie_Analytics

# Start API
cd backend
.venv/bin/python -m app.api &
API_PID=$!
cd ..

# Start dashboard
cd dashboard
npx next dev -p 3000 &
DASH_PID=$!
cd ..

# Wait for both
echo "Waiting for servers..."
for i in $(seq 1 40); do
  if curl -s -o /dev/null http://localhost:8000/api/health 2>/dev/null && \
     curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
    echo "Servers ready!"
    break
  fi
  sleep 1
done

echo "API health: $(curl -s http://localhost:8000/api/health)"
echo "Dashboard: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000)"

# Take screenshots
cd /workspace/HunterPie_Analytics/dashboard
node take-screenshots.mjs

# Cleanup
kill $API_PID $DASH_PID 2>/dev/null || true
echo "All done."
