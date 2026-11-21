#!/bin/bash
if [ -n "${REQUEST_METHOD:-}" ]; then
    python3 "$(dirname "$0")/security_gate.py" text || exit 0
fi
echo "Content-Type: text/plain"
echo ""

ACTION="$QUERY_STRING"

case "$ACTION" in
    led_on)
        /home/q/websd/piscripts/relayon
        echo "LED ON"
        ;;
    led_off)
        /home/q/websd/piscripts/relayoff
        echo "LED OFF"
        ;;
    reboot)
        if ! systemctl reboot; then
            echo "ERROR: Pi reboot is not available to the website account."
            exit 1
        fi
        ;;
    check_sms)
        python3 "$(dirname "$0")/sms_monitor.py"
        ;;
    *)
        echo "Unknown action: $ACTION"
        ;;
esac
