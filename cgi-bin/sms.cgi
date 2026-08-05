#!/bin/bash
echo "Content-Type: text/plain"
echo ""

ACTION="$QUERY_STRING"

case "$ACTION" in
    led_on)
        /usr/bin/python3 /home/q/websitepi/actions/led_on.py
        echo "LED ON"
        ;;
    led_off)
        /usr/bin/python3 /home/q/websitepi/actions/led_off.py
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
