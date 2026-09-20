#!/bin/bash
echo "Content-type: text/plain"
echo ""

ACTION=$(echo "$QUERY_STRING" | sed -n 's/^.*action=\([^&]*\).*$/\1/p')

LOG=/home/q/websd/logs/udpmic.log
LOCK=/tmp/udpmic.lock
PATTERN="piscripts/udpmic.py"

# Serialize start/stop requests so double-clicks can't race each other into a bad state.
exec 200>"$LOCK"
flock -w 10 200 || { echo "ERROR: receiver busy, try again"; exit 1; }

port_busy() {
  # Best-effort occupancy check; falls back to "unknown" (treated as free) if no tool is available.
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -lntu 2>/dev/null | awk '{print $5}' | grep -qE ":${port}\$"
  elif command -v netstat >/dev/null 2>&1; then
    netstat -lntu 2>/dev/null | awk '{print $4}' | grep -qE ":${port}\$"
  else
    return 1
  fi
}

kill_receiver() {
  local pids
  pids=$(pgrep -f "$PATTERN")
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null
    for _ in $(seq 1 15); do
      pgrep -f "$PATTERN" >/dev/null || break
      sleep 0.2
    done
    pkill -9 -f "$PATTERN" 2>/dev/null
    sleep 0.2
  fi

  # Old process may be gone but the kernel can still hold the port briefly (TIME_WAIT/lingering fds).
  for port in 9100 9101; do
    for _ in $(seq 1 15); do
      port_busy "$port" || break
      if command -v fuser >/dev/null 2>&1; then
        fuser -k "${port}/udp" "${port}/tcp" 2>/dev/null
      fi
      sleep 0.2
    done
  done
}

kill_receiver

if [ "$ACTION" = "stop" ]; then
  echo "UDP mic stream stopped"
  exit 0
fi

start_once() {
  : > "$LOG"
  nohup python3 /home/q/websd/piscripts/udpmic.py >> "$LOG" 2>&1 &
  local pid=$!
  for _ in $(seq 1 15); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi
    if port_busy 9100 && port_busy 9101; then
      return 0
    fi
    sleep 0.2
  done
  kill -0 "$pid" 2>/dev/null
}

if start_once; then
  echo "UDP mic listening on 9100/udp, stream on 9101/tcp"
  exit 0
fi

# One retry after a harder cleanup, in case the ports were still settling.
kill_receiver
if start_once; then
  echo "UDP mic listening on 9100/udp, stream on 9101/tcp"
  exit 0
fi

echo "ERROR: UDP mic receiver failed to start (see udpmic.log)"
exit 1
