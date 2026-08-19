#!/bin/bash
# Process each new incoming SMS exactly once.
PHONE="SOEUDQIBF6ZLXK75"
STATE_FILE="/var/tmp/websitepi-last-sms-id"
LOCK_FILE="/var/tmp/websitepi-sms-monitor.lock"
RECEIVER="/home/q/websd/sms/smsreceive"

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

last_id=""
initialized=0
if [ -f "$STATE_FILE" ]; then
    read -r last_id < "$STATE_FILE"
    initialized=1
fi

while true; do
    LAST=$(adb -s "$PHONE" shell content query \
        --uri content://sms/inbox \
        --projection _id:body \
        --sort "date DESC" \
        --limit 1 2>/dev/null)
    ID=$(printf '%s\n' "$LAST" | sed -n 's/.*_id=\([^, ]*\).*/\1/p' | tr -d '\r')
    BODY=$(printf '%s\n' "$LAST" | sed -n 's/.*body=//p' | tr -d '\r')

    if [ -n "$ID" ] && [ "$initialized" -eq 0 ]; then
        printf '%s\n' "$ID" > "${STATE_FILE}.tmp"
        mv -f "${STATE_FILE}.tmp" "$STATE_FILE"
        last_id="$ID"
        initialized=1
    elif [ -n "$ID" ] && [ "$ID" != "$last_id" ]; then
        printf '%s\n' "$ID" > "${STATE_FILE}.tmp"
        mv -f "${STATE_FILE}.tmp" "$STATE_FILE"
        last_id="$ID"
        echo "Received SMS: $BODY"
        "$RECEIVER" "$BODY"
    fi

    sleep 3
done
