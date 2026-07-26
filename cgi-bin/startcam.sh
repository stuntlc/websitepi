#!/bin/sh
echo "Content-type: text/plain"
echo ""

# Kill any previous instance
pkill -f /home/q/mjpeg.py

# Start the MJPEG server in background
nohup python3 /home/q/mjpeg.py > /dev/null 2>&1 &

echo "Camera started"
