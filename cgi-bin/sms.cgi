#!/bin/bash
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
        sudo reboot
        ;;
    check_sms)
        /bin/bash /home/q/websd/piscripts/readsms.sh &
        echo "Started SMS monitor"
        ;;
    *)
        echo "Unknown action: $ACTION"
        ;;
esac
