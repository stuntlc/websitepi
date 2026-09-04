#!/bin/bash
printf 'Content-Type: text/plain\r\n\r\n'

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
/bin/bash "$SCRIPT_DIR/sms/readsms" 2>&1