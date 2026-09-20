#!/usr/bin/env python3
"""Live phone sensor/system snapshot over adb, returned as JSON for the sensors dashboard."""
import json
import os
import re
import subprocess
import time

ADB = os.environ.get("ADB", "adb")
PHONE_ADB_SERIAL = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print()
    print(json.dumps(payload))


def run_adb(args, timeout=10):
    return subprocess.run(
        [ADB, "-s", PHONE_ADB_SERIAL, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def value_after(text, label, lookahead=5):
    lines = text.splitlines()
    # "Recent Sensor events" lines carry both the label and the value on one line;
    # the last such line is the freshest reading, so prefer that over the sensor list header.
    combined = [line.strip() for line in lines if label in line.lower() and "value" in line.lower()]
    if combined:
        return combined[-1]
    for index, line in enumerate(lines):
        if label in line.lower():
            for candidate in lines[index:index + lookahead]:
                if "value" in candidate.lower():
                    return candidate.strip()
    return ""


def first_number(text):
    match = re.search(r"-?\d+(\.\d+)?", text or "")
    return match.group(0) if match else ""


try:
    sensors = run_adb(["shell", "dumpsys", "sensorservice"]).stdout
except (OSError, subprocess.TimeoutExpired) as error:
    respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

try:
    battery_dump = run_adb(["shell", "dumpsys", "battery"]).stdout
    thermal = run_adb(["shell", "cat", "/sys/class/thermal/thermal_zone0/temp"]).stdout.strip()
    wifi_dump = run_adb(["shell", "dumpsys", "wifi"]).stdout
    bt_dump = run_adb(["shell", "dumpsys", "bluetooth_manager"]).stdout
except (OSError, subprocess.TimeoutExpired) as error:
    respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

battery_match = re.search(r"level:\s*(-?\d+)", battery_dump, re.IGNORECASE)
wifi_match = re.search(r"RSSI:?\s*(-?\d+)", wifi_dump, re.IGNORECASE)
bt_match = re.search(r"enabled:?\s*(true|false)", bt_dump, re.IGNORECASE)

respond({
    "ok": True,
    "timestamp": int(time.time()),
    "accelerometer": value_after(sensors, "accelerometer"),
    "gyroscope": value_after(sensors, "gyroscope"),
    "light": value_after(sensors, "light"),
    "proximity": value_after(sensors, "proximity"),
    "orientation": value_after(sensors, "orientation"),
    "battery": battery_match.group(1) if battery_match else "",
    "thermal": first_number(thermal),
    "wifi_rssi": wifi_match.group(1) if wifi_match else "",
    "bluetooth_enabled": bt_match.group(1).lower() if bt_match else "",
})
