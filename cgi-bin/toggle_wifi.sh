#!/bin/bash
# toggle_wifi.sh
STATE=$1  # "on" or "off"
if [ "$STATE" == "on" ]; then
    adb shell svc wifi enable
else
    adb shell svc wifi disable
fi
