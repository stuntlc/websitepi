#!/bin/bash
echo "Content-type: text/plain"
echo ""

ACTION=$(echo "$QUERY_STRING" | sed -n 's/^.*action=\([^&]*\).*$/\1/p')

pkill -f "piscripts/udpmic.py" 2>/dev/null
sleep 0.3

if [ "$ACTION" = "stop" ]; then
  echo "UDP mic stream stopped"
  exit 0
fi

nohup python3 /home/q/websd/piscripts/udpmic.py > /home/q/websd/logs/udpmic.log 2>&1 &

echo "UDP mic listening on 9100/udp, stream on 9101/tcp"
