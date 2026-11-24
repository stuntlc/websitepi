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
MEDIA_DIR="${WEBSITEPI_MEDIA_DIR:-/home/q/websd/piscripts}"
MEDIA_URL="/piscripts"
if [ -n "${WEBSITEPI_MEDIA_DIR:-}" ]; then MEDIA_URL="/media"; fi
FILE="$TS-raw.jpg"
OUT="$MEDIA_DIR/$FILE"

if ! "${CAMERA_COMMAND[@]}" -o "$OUT"; then
	echo "Camera capture failed"
	exit 1
fi

# Save latest filename
if ! printf '%s\n' "$FILE" > "$MEDIA_DIR/latest.txt"; then
	echo "Could not save latest photo marker"
	exit 1
fi

echo "saved:$MEDIA_URL/$FILE"
