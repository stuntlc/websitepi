#!/bin/bash
echo "Content-type: text/plain"
echo ""

ACTION=$(echo "$QUERY_STRING" | sed -n 's/^.*action=\([^&]*\).*$/\1/p')

LOG=/home/q/websd/logs/udpmic.log
LOCK=/tmp/udpmic.lock
PATTERN="udpmic\.py"

# /proc-based port check: works even without ss/netstat/fuser installed.
port_busy() {
  local port="$1"
  local hexport
  hexport=$(printf '%04X' "$port")
  grep -qE "^[[:space:]]*[0-9]+:[[:space:]]*[0-9A-Fa-f]+:${hexport}[[:space:]]" \
    /proc/net/tcp /proc/net/tcp6 /proc/net/udp /proc/net/udp6 2>/dev/null
}

# /proc-based pid lookup for a port, used when fuser isn't available.
pids_on_port() {
  local port="$1"
  local hexport inode fd pid
  hexport=$(printf '%04X' "$port")
  for inode in $(awk -v p=":${hexport}" '$2 ~ p {print $10}' /proc/net/tcp /proc/net/tcp6 /proc/net/udp /proc/net/udp6 2>/dev/null | sort -u); do
    [ -z "$inode" ] && continue
    for fd in /proc/[0-9]*/fd/*; do
      [ -e "$fd" ] || continue
      case "$(readlink "$fd" 2>/dev/null)" in
        "socket:[$inode]")
          pid=$(echo "$fd" | sed -E 's#/proc/([0-9]+)/fd/.*#\1#')
          echo "$pid"
          ;;
      esac
    done
  done | sort -u
}

kill_port() {
  local port="$1"
  local pid
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/udp" "${port}/tcp" 2>/dev/null
  fi
  for pid in $(pids_on_port "$port"); do
    kill -9 "$pid" 2>/dev/null
  done
}

# Find and kill whatever still has the lock file open, in case a wedged process
# is holding it (this is what makes "busy" persist until reboot otherwise).
kill_lock_holders() {
  local fd pid
  for fd in /proc/[0-9]*/fd/*; do
    [ -e "$fd" ] || continue
    if [ "$(readlink -f "$fd" 2>/dev/null)" = "$LOCK" ]; then
      pid=$(echo "$fd" | sed -E 's#/proc/([0-9]+)/fd/.*#\1#')
      kill -9 "$pid" 2>/dev/null
    fi
  done
}

debug_snapshot() {
  echo "--- pgrep -af $PATTERN ---"
  pgrep -af "$PATTERN" 2>/dev/null
  echo "--- pids on 9100/9101 ---"
  echo "9100: $(pids_on_port 9100 | tr '\n' ' ')"
  echo "9101: $(pids_on_port 9101 | tr '\n' ' ')"
  echo "--- port_busy checks ---"
  port_busy 9100 && echo "9100: busy" || echo "9100: free"
  port_busy 9101 && echo "9101: busy" || echo "9101: free"
  echo "--- last 20 lines of $LOG ---"
  tail -n 20 "$LOG" 2>/dev/null
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
      kill_port "$port"
      sleep 0.2
    done
  done
}

# True when a single udpmic.py already owns both ports, so start can skip the teardown/rebuild.
receiver_healthy() {
  local pids
  pids=$(pgrep -f "$PATTERN")
  [ -n "$pids" ] || return 1
  [ "$(echo "$pids" | wc -l)" = "1" ] || return 1
  port_busy 9100 || return 1
  port_busy 9101 || return 1
  [ "$(pids_on_port 9100)" = "$pids" ] || return 1
  [ "$(pids_on_port 9101)" = "$pids" ] || return 1
  return 0
}

if [ "$ACTION" = "debug" ]; then
  debug_snapshot
  exit 0
fi

if [ "$ACTION" = "force" ]; then
  # Bypass the lock wait entirely: best-effort, used to recover a wedged receiver.
  kill_lock_holders
  rm -f "$LOCK"
  pkill -9 -f "$PATTERN" 2>/dev/null
  kill_port 9100
  kill_port 9101
  echo "Force cleanup done."
  debug_snapshot
  exit 0
fi

# Serialize start/stop requests so double-clicks can't race each other into a bad state.
exec 200>"$LOCK"
if ! flock -w 20 200; then
  echo "ERROR: receiver busy, try again (or use action=force to unstick)"
  debug_snapshot
  exit 1
fi

if [ "$ACTION" != "stop" ] && receiver_healthy; then
  echo "UDP mic already listening on 9100/udp, stream on 9101/tcp"
  exit 0
fi

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

echo "ERROR: UDP mic receiver failed to start"
debug_snapshot
exit 1
