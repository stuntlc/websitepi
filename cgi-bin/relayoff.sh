#!/bin/bash
if [ -n "${REQUEST_METHOD:-}" ]; then
  python3 "$(dirname "$0")/security_gate.py" text || exit 0
fi
if output=$(/home/q/websd/piscripts/relayoff 2>&1); then
  printf 'Content-Type: text/plain\n\nRelay turned OFF\n'
else
  printf 'Status: 500 Internal Server Error\nContent-Type: text/plain\n\nERROR: Relay could not turn off: %s\n' "$output"
  exit 1
fi
