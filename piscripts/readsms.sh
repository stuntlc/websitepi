#!/bin/bash
# Continuous SMS monitor using ADB
PHONE="SOEUDQIBF6ZLXK75"

while true; do
    LAST=$(adb -s "$PHONE" shell content query --uri content://sms/inbox --projection body --sort "date DESC" --limit 1)
    BODY=$(echo "$LAST" | grep "body=" | sed 's/.*body=//')

    if [ -n "$BODY" ]; then
        echo "Received SMS: $BODY"
        /home/q/websd/sms/smsreceive "$BODY"
    fi

    sleep 3
done
