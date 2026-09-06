#!/bin/bash
echo "Content-Type: text/plain"
echo ""

# Stop live stream first
pkill -f mjpeg.py

TS=$(date +%Y%m%d-%H%M%S)
OUT="/home/q/websd/piscripts/$TS.jpg"

# Capture rotated image
rpicam-jpeg --rotation 180 -o "$OUT"

# Save latest filename
echo "$TS.jpg" > /home/q/websd/piscripts/latest.txt

echo "saved:/piscripts/$TS.jpg"
