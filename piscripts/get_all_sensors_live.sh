#!/bin/bash

LOGDIR="sensor_logs_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"

echo "Live sensor logging started. Saving to $LOGDIR"
echo "Press CTRL+C to stop."

while true; do
    TS=$(date +%Y-%m-%d_%H:%M:%S)

    echo "=== $TS ===" >> "$LOGDIR/sensors.txt"
    adb shell dumpsys sensorservice >> "$LOGDIR/sensors.txt"

    echo "=== $TS ===" >> "$LOGDIR/events.txt"
    timeout 1 adb shell getevent >> "$LOGDIR/events.txt"

    echo "=== $TS ===" >> "$LOGDIR/thermal.txt"
    adb shell cat /sys/class/thermal/thermal_zone*/temp >> "$LOGDIR/thermal.txt"

    echo "=== $TS ===" >> "$LOGDIR/battery.txt"
    adb shell dumpsys battery >> "$LOGDIR/battery.txt"

    echo "=== $TS ===" >> "$LOGDIR/wifi.txt"
    adb shell dumpsys wifi >> "$LOGDIR/wifi.txt"

    echo "=== $TS ===" >> "$LOGDIR/bluetooth.txt"
    adb shell dumpsys bluetooth_manager >> "$LOGDIR/bluetooth.txt"

    sleep 1
done
