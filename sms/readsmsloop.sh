#!/bin/bash
# Continuous SMS monitor using ADB (stable version)
STATE_FILE="/tmp/websitepi-last-sms-id"

while true; do
    MSG=$(adb shell content query --uri content://sms --projection _id:address:body --sort "_id" | tail -n 1)
    ID=$(echo "$MSG" | sed -n 's/.*_id=\([^, ]*\).*/\1/p' | tr -d '\r')
    BODY=$(echo "$MSG" | sed 's/.*body=//')

    if [ -n "$ID" ] && [ ! -f "$STATE_FILE" ]; then
        printf '%s' "$ID" > "$STATE_FILE"
    elif [ -n "$ID" ] && [ "$ID" != "$(cat "$STATE_FILE" 2>/dev/null)" ]; then
        printf '%s' "$ID" > "$STATE_FILE"
        echo "Received SMS: $BODY"
        /home/q/websd/sms/smsreceive "$BODY"
    fi

    sleep 3
done
