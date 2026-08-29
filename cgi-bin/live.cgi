#!/bin/bash
echo "Content-type: text/plain"
echo ""

# Stop any existing MJPEG server
pkill -f mjpeg.py
sleep 0.5

# Start new MJPEG server
nohup python3 /home/q/mjpeg.py > /dev/null 2>&1 &

echo "Live stream started on port 8000"
