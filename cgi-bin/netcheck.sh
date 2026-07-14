#!/bin/bash
echo "Content-type: text/html"
echo ""

# HTML wrapper
cat <<EOF
<html>
<body style="background:black;color:#00ff00;font-family:monospace;">
<pre style="font-size:16px; padding:20px; border:2px solid #00ff00; border-radius:10px; box-shadow:0 0 20px #00ff00;">
EOF

echo "=== NETWORK STATUS CHECK ==="
echo ""

# --- Ping tests ---
PING_IP=$(ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && echo OK || echo FAIL)
PING_DNS=$(ping -c1 -W1 google.com >/dev/null 2>&1 && echo OK || echo FAIL)

# --- ASCII banners ---
if [ "$PING_IP" = "OK" ] && [ "$PING_DNS" = "OK" ]; then
cat <<'EOF'
      ____   _      _ _        
     / __ \ | |    (_) |       
    | |  | || |     _| |_ ___  
    | |  | || |    | | __/ _ \ 
    | |__| || |____| | || (_) |
     \____/ |______|_|\__\___/ 

            STATUS: ONLINE
EOF
else
cat <<'EOF'
      ____   _   _   _      _ _  __ _ 
     / __ \ | | | | | |    | | |/ _` |
    | |  | || |_| | | |    | | | (_| |
    | |  | | \__, | | |    | | |\__,_|
    | |__| |   / /  | |____| | |      
     \____/   /_/   |______|_|_|      

            STATUS: OFFLINE
EOF
fi

echo ""
echo "Ping Google IP (8.8.8.8): $PING_IP"
echo "Ping google.com (DNS):    $PING_DNS"
echo ""

echo "=== ARP TABLE (Clients on LAN) ==="
arp -n 2>/dev/null
echo ""

echo "=== ROUTING TABLE ==="
ip route
echo ""

echo "=== TRACEROUTE TO GOOGLE.COM ==="
traceroute -w1 -q1 google.com 2>/dev/null
echo ""

echo "++BAT dump++"
sudo adb shell dumpsys battery 2>/dev/null
echo ""
# Close HTML
cat <<EOF
</pre>
</body>
</html>
EOF
