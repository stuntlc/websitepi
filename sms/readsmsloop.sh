#!/bin/bash
# Continuous SMS monitor using ADB (stable version)
while true; do
    MSG=$(adb shell content query --uri content://sms --projection _id:address:body --sort "_id" | tail -n 1)
    BODY=$(echo "$MSG" | sed 's/.*body=//')
    echo "Received SMS: $BODY"
    /home/q/websd/sms/smsreceive "$BODY"
    sleep 3
done
