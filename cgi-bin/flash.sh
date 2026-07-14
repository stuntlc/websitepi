#!/bin/bash

TORCH="/sys/class/leds/flashlight/brightness"   # <-- change to your actual path

case "$1" in
    on)
        sudo adb shell "echo 1 > $TORCH"
        ;;
    off)
        sudo adb shell "echo 0 > $TORCH"
        ;;
    *)
        echo "Usage: $0 {on|off}"
        ;;
esac

