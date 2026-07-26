#!/bin/bash
echo "Content-Type: text/plain"
echo ""

# Kill MJPEG server before capturing
pkill -f /home/q/mjpeg.py
pkill -f rpicam-vid

TS=$(date +%Y%m%d-%H%M%S)
OUT="/home/q/websd/$TS.jpg"

# Capture rotated image
rpicam-jpeg --rotation 180 -o "$OUT"

# Save latest filename
echo "$TS.jpg" > /home/q/websd/latest.txt

echo "saved:$TS.jpg"
