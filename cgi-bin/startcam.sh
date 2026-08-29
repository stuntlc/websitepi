#!/bin/sh
echo "Content-type: text/plain"
echo ""

# Kill any leftover processes
pkill -f mjpeg.py
pkill -f rpicam-vid
sleep 0.5

# Double-check no orphaned rpicam-vid remains
while pgrep -f rpicam-vid >/dev/null; do
    pkill -f rpicam-vid
    sleep 0.2
done

# Start fresh instance
nohup python3 /home/q/mjpeg.py > /dev/null 2>&1 &

echo "Camera restarted"
