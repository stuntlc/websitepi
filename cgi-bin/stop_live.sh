#!/bin/bash
echo "Content-Type: text/plain"
echo ""
pkill -f mjpeg.py 2>/dev/null || true
echo "Live camera stopped"
