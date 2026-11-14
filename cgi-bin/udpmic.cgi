#!/bin/bash
echo "Content-type: text/plain"
echo ""

ACTION=$(echo "$QUERY_STRING" | sed -n 's/^.*action=\([^&]*\).*$/\1/p')
LOG=/home/q/websd/logs/udpmic.log
LOCK=/tmp/udpmic.lock
PATTERN='[p]ython3? /home/q/websd/piscripts/udpmic[.]py([[:space:]]|$)'

port_busy() {
  local hexport
  hexport=$(printf '%04X' "$2")
  if [ "$1" = "tcp" ]; then
    awk -v p=":${hexport}" '$2 ~ p "$" && $4 == "0A" {found=1} END {exit !found}' /proc/net/tcp /proc/net/tcp6
  else
    awk -v p=":${hexport}" '$2 ~ p "$" {found=1} END {exit !found}' /proc/net/udp /proc/net/udp6
  fi
}

pid_owns_port() {
  local pid="$1" protocol="$2" hexport inode fd
  hexport=$(printf '%04X' "$3")
  for inode in $(awk -v p=":${hexport}" '$2 ~ p "$" {print $10}' "/proc/net/$protocol" "/proc/net/${protocol}6"); do
    for fd in /proc/"$pid"/fd/*; do
      [ "$(readlink "$fd" 2>/dev/null)" = "socket:[$inode]" ] && return 0
    done
  done
  return 1
}

debug_snapshot() {
  echo "--- receiver processes ---"
  pgrep -af "$PATTERN" || true
  port_busy udp 9100 && echo "9100/udp: busy" || echo "9100/udp: free"
  port_busy tcp 9101 && echo "9101/tcp: busy" || echo "9101/tcp: free"
  echo "--- last 20 lines of $LOG ---"
  tail -n 20 "$LOG" 2>/dev/null || true
}

kill_receiver() {
  local pids
  pids=$(pgrep -f "$PATTERN")
  [ -n "$pids" ] || return 0
  kill $pids 2>/dev/null || true
  for _ in $(seq 1 15); do
    pgrep -f "$PATTERN" >/dev/null || return 0
    sleep 0.2
  done
  pkill -9 -f "$PATTERN" 2>/dev/null || true
  for _ in $(seq 1 15); do
    pgrep -f "$PATTERN" >/dev/null || return 0
    sleep 0.2
  done
  echo "ERROR: could not stop the old UDP mic receiver"
  return 1
}

# Older receivers inherited fd 200 and can hold the lock indefinitely.
release_legacy_lock() {
  local pid fd
  for pid in $(pgrep -f "$PATTERN"); do
    for fd in /proc/"$pid"/fd/*; do
      if [ "$fd" -ef "$LOCK" ]; then
        kill "$pid" 2>/dev/null || true
        break
      fi
    done
  done
}

if [ "$ACTION" = "debug" ]; then
  debug_snapshot
  exit 0
fi

if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ] && [ "$ACTION" != "force" ] && [ -n "$ACTION" ]; then
  echo "ERROR: unknown action"
  exit 1
fi

# Never unlink the lock: concurrent requests must all lock the same inode.
exec 200>"$LOCK"
if ! flock -w 3 200; then
  release_legacy_lock
  if ! flock -w 20 200; then
    echo "ERROR: receiver busy; could not acquire the startup lock"
    debug_snapshot
    exit 1
  fi
fi

kill_receiver || exit 1

if [ "$ACTION" = "stop" ] || [ "$ACTION" = "force" ]; then
  echo "UDP mic stream stopped"
  exit 0
fi

if port_busy udp 9100 || port_busy tcp 9101; then
  echo "ERROR: UDP port 9100 or TCP port 9101 is already in use by another process"
  debug_snapshot
  exit 1
fi

: > "$LOG"
# The receiver must not inherit the CGI lock.
nohup python3 /home/q/websd/piscripts/udpmic.py 200>&- >> "$LOG" 2>&1 &
pid=$!
for _ in $(seq 1 25); do
  if ! kill -0 "$pid" 2>/dev/null; then
    break
  fi
  if pid_owns_port "$pid" udp 9100 && pid_owns_port "$pid" tcp 9101; then
    echo "UDP mic listening on 9100/udp, stream on 9101/tcp"
    exit 0
  fi
  sleep 0.2
done

kill "$pid" 2>/dev/null || true
echo "ERROR: UDP mic receiver failed to start"
debug_snapshot
exit 1
