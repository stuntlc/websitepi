#!/bin/bash
if [ -n "${REQUEST_METHOD:-}" ]; then
  python3 "$(dirname "$0")/security_gate.py" text || exit 0
fi
echo "Content-type: text/plain"
echo ""

# Stop any existing MJPEG server
pkill -f mjpeg.py
sleep 0.5

nohup python3 /home/q/websd/piscripts/mjpeg.py > "${WEBSITEPI_LOG_DIR:-/home/q/websd/logs}/live.log" 2>&1 &
pid=$!
for _ in $(seq 1 30); do
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "ERROR: Live camera server failed to start; see logs/live.log"
    exit 1
  fi
  if (echo >/dev/tcp/127.0.0.1/8000) 2>/dev/null; then
    echo "Live camera server started"
    exit 0
  fi
  sleep 0.1
done
kill "$pid" 2>/dev/null || true
echo "ERROR: Live camera server did not become ready; see logs/live.log"
exit 1
