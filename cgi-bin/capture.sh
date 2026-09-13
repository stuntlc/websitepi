#!/bin/bash
echo "Content-Type: text/plain"
echo ""

if command -v rpicam-jpeg >/dev/null 2>&1; then
	CAMERA_COMMAND=(rpicam-jpeg)
elif command -v libcamera-jpeg >/dev/null 2>&1; then
	CAMERA_COMMAND=(libcamera-jpeg)
else
	echo "Camera command unavailable: install rpicam-apps or libcamera-apps"
	exit 1
fi

# Stop live stream first
pkill -f mjpeg.py

TS=$(date +%Y%m%d-%H%M%S)
OUT="/home/q/websd/piscripts/$TS.jpg"

# Capture rotated image
"${CAMERA_COMMAND[@]}" --rotation 180 -o "$OUT"

# Save latest filename
echo "$TS.jpg" > /home/q/websd/piscripts/latest.txt

echo "saved:/piscripts/$TS.jpg"
