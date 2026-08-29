#!/bin/sh
echo "Content-type: text/plain"
echo ""

# Kill any leftover camera processes
pkill -f rpicam-vid
sleep 0.5

# Start MJPEG stream on port 8000
nohup rpicam-vid -t 0 --codec mjpeg --width 640 --height 480 --framerate 15 -o tcp://0.0.0.0:8000 > /dev/null 2>&1 &

echo "Camera started"
