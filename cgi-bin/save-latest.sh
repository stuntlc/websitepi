#!/bin/bash
echo "Content-Type: text/plain"
echo ""

FILE=$(echo "$QUERY_STRING" | sed 's/file=//')
if ! echo "$FILE" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*\.(jpg|jpeg)$'; then
    echo "Invalid photo filename"
    exit 1
fi
if ! printf '%s\n' "$FILE" > "${WEBSITEPI_MEDIA_DIR:-/home/q/websd/piscripts}/latest.txt"; then
    echo "Could not save latest photo marker"
    exit 1
fi
echo "ok"
