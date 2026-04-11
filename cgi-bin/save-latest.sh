#!/bin/bash
echo "Content-Type: text/plain"
echo ""

FILE=$(echo "$QUERY_STRING" | sed 's/file=//')
echo "$FILE" > /home/q/websd/latest.txt
echo "ok"
