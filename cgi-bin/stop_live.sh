#!/bin/bash
if [ -n "${REQUEST_METHOD:-}" ]; then
  python3 "$(dirname "$0")/security_gate.py" text || exit 0
fi
echo "Content-Type: text/plain"
echo ""
pkill -f mjpeg.py 2>/dev/null || true
echo "Live camera stopped"
