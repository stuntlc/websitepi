#!/bin/bash

phone_portrait_begin() {
    local auto rotation
    exec 9>/run/websitepi/phone-ui.lock || return 1
    if ! flock -w 30 9; then
        echo "Phone controls are busy. Try again."
        return 1
    fi
    auto=$("$ADB" shell settings get system accelerometer_rotation 9>&-) || return 1
    rotation=$("$ADB" shell settings get system user_rotation 9>&-) || return 1
    PHONE_OLD_AUTO=$(printf '%s' "$auto" | tr -d '\r')
    PHONE_OLD_ROTATION=$(printf '%s' "$rotation" | tr -d '\r')
    if [[ ! "$PHONE_OLD_AUTO" =~ ^[01]$ || ! "$PHONE_OLD_ROTATION" =~ ^[0123]$ ]]; then
        echo "Could not read the phone's rotation settings."
        return 1
    fi
    PHONE_ROTATION_ACTIVE=1
    if ! "$ADB" shell settings put system accelerometer_rotation 0 9>&- ||
       ! "$ADB" shell settings put system user_rotation 0 9>&-; then
        echo "Could not switch the phone to portrait."
        return 1
    fi
}

phone_portrait_restore() {
    local failed=0
    [ "${PHONE_ROTATION_ACTIVE:-0}" = "1" ] || return 0
    "$ADB" shell settings put system user_rotation "$PHONE_OLD_ROTATION" 9>&- || failed=1
    "$ADB" shell settings put system accelerometer_rotation "$PHONE_OLD_AUTO" 9>&- || failed=1
    if [ "$failed" -ne 0 ]; then
        echo "Could not restore the phone's rotation settings."
        return 1
    fi
    PHONE_ROTATION_ACTIVE=0
}
