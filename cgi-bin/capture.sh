#!/bin/bash
echo "Content-Type: text/plain"
echo ""

TS=$(date +%Y%m%d-%H%M%S)
OUT="/home/q/websd/$TS.jpg"

rpicam-jpeg --rotation 180 -o "$OUT"

# Save latest filename
echo "$TS.jpg" > /home/q/websd/latest.txt

echo "saved:$TS.jpg"
