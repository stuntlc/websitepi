#!/bin/bash

while true; do
    ACC=$(adb shell dumpsys sensorservice | grep -i "accelerometer" -A 5 | grep "value" | head -n 1)
    GYRO=$(adb shell dumpsys sensorservice | grep -i "gyroscope" -A 5 | grep "value" | head -n 1)
    LIGHT=$(adb shell dumpsys sensorservice | grep -i "light" -A 5 | grep "value" | head -n 1)
    PROX=$(adb shell dumpsys sensorservice | grep -i "proximity" -A 5 | grep "value" | head -n 1)
    ORIENT=$(adb shell dumpsys sensorservice | grep -i "orientation" -A 5 | grep "value" | head -n 1)

    BAT=$(adb shell dumpsys battery | grep -i level | awk '{print $2}')
    TEMP=$(adb shell cat /sys/class/thermal/thermal_zone0/temp)
    WIFI=$(adb shell dumpsys wifi | grep "RSSI" | head -n 1 | awk '{print $2}')
    BT=$(adb shell dumpsys bluetooth_manager | grep "enabled" | awk '{print $2}')

    echo "{
        \"timestamp\": \"$(date +%s)\",
        \"accelerometer\": \"$ACC\",
        \"gyroscope\": \"$GYRO\",
        \"light\": \"$LIGHT\",
        \"proximity\": \"$PROX\",
        \"orientation\": \"$ORIENT\",
        \"battery\": \"$BAT\",
        \"thermal\": \"$TEMP\",
        \"wifi_rssi\": \"$WIFI\",
        \"bluetooth_enabled\": \"$BT\"
    }"

    sleep 1
done
