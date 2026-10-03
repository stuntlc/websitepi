#!/bin/bash
# Runs the OUI scan periodically so new devices trigger alerts even when the page is closed.
cd /home/q/websd || exit 1
while true; do
    SCRIPT_FILENAME=/home/q/websd/cgi-bin/oui.cgi /home/q/websd/cgi-bin/oui.cgi >/dev/null 2>&1
    sleep 60
done
