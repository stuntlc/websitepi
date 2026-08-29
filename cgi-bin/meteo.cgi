#!/bin/sh
echo "Content-type: text/html"
echo ""

echo "<div style='margin:25px auto; width:92%; max-width:1100px; padding:10px 0; background:rgba(0,0,0,0.55); color:#0f0; font-family:Courier New, monospace; text-align:center; box-shadow:0 0 20px rgba(0,0,0,0.8); border-radius:10px;'>"

if ping -c1 8.8.8.8 >/dev/null 2>&1; then

    echo "<div style='display:inline-block; text-align:left; white-space:pre; font-size:15px; line-height:1.1; margin:auto; padding:0; background:none;'>"

    /home/q/websd/piscripts/meteo | python3 -m ansi2html | \
        sed -e 's/<!DOCTYPE[^>]*>//g' \
            -e 's/<head>.*<\/head>//g' \
            -e 's/<\/\?html>//g' \
            -e 's/<\/\?body>//g'

    echo "</div>"

else
    echo "<b>Offline</b>"
fi

echo "</div>"
