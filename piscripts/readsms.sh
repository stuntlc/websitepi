#!/bin/bash
# Continuous SMS monitor using ADB
PHONE="SOEUDQIBF6ZLXK75"
STATE_FILE="/tmp/websitepi-last-sms-id"

while true; do
    LAST=$(adb -s "$PHONE" shell content query --uri content://sms/inbox --projection _id:body --sort "date DESC" --limit 1)
    ID=$(echo "$LAST" | sed -n 's/.*_id=\([^, ]*\).*/\1/p' | tr -d '\r')
    BODY=$(echo "$LAST" | sed 's/.*body=//')

    if [ -n "$ID" ] && [ ! -f "$STATE_FILE" ]; then
        printf '%s' "$ID" > "$STATE_FILE"
    elif [ -n "$ID" ] && [ "$ID" != "$(cat "$STATE_FILE" 2>/dev/null)" ]; then
        printf '%s' "$ID" > "$STATE_FILE"
        echo "Received SMS: $BODY"
        /home/q/websd/sms/smsreceive "$BODY"
    fi

    sleep 3
done
