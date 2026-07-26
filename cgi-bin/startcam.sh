#!/bin/sh
echo "Content-type: text/plain"
echo ""

# Kill Python MJPEG server
pkill -f /home/q/mjpeg.py

# Kill rpicam-vid if still running
pkill -f rpicam-vid

# Start fresh instance
nohup python3 /home/q/mjpeg.py > /dev/null 2>&1 &

echo "Camera restarted"
