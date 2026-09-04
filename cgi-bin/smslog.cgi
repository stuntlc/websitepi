#!/bin/bash
echo "Content-Type: text/plain"
echo ""
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tail -n 20 "$SCRIPT_DIR/logs/sms.log"
