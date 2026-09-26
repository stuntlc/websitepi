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


NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
VECTOR_PATTERNS = [
    re.compile(r"\[\s*(" + NUM + r")\s*,\s*(" + NUM + r")\s*,\s*(" + NUM + r")\s*\]"),
    re.compile(r"<\s*(" + NUM + r")\s*,\s*(" + NUM + r")\s*,\s*(" + NUM + r")\s*>"),
    re.compile(r"x\s*[:=]\s*(" + NUM + r")[^0-9\-]+y\s*[:=]\s*(" + NUM + r")[^0-9\-]+z\s*[:=]\s*(" + NUM + r")", re.IGNORECASE),
]
SCALAR_PATTERNS = [
    re.compile(r"\[\s*(" + NUM + r")\s*\]"),
    re.compile(r"value[s]?\s*[:=]\s*(" + NUM + r")", re.IGNORECASE),
]


def extract_reading(text, label, vector=True, lookahead=8):
    """Scan for the sensor's name and pull the freshest numeric reading near it.

    Different Android/vendor builds format "dumpsys sensorservice" differently
    (bracketed vectors, angle-bracket vectors, or x=/y=/z= tuples), so try each
    shape and keep the last (most recent) match found in the whole dump.
    """
    lines = text.splitlines()
    lower_label = label.lower()
    patterns = VECTOR_PATTERNS if vector else SCALAR_PATTERNS
    best = ""
    for index, line in enumerate(lines):
        if lower_label not in line.lower():
            continue
        window = "\n".join(lines[index:index + lookahead])
        for pattern in patterns:
            match = pattern.search(window)
            if match:
                best = ", ".join(match.groups())
                break
    return best


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
# Real Wi-Fi RSSI is always negative dBm; requiring the sign avoids matching
# unrelated positive counters (e.g. "Num RSSI polls") earlier in the dump.
wifi_match = re.search(r"RSSI:?\s*(-\d+)", wifi_dump, re.IGNORECASE)
bt_match = re.search(r"enabled:?\s*(true|false)", bt_dump, re.IGNORECASE)

try:
    with open(os.path.join(os.path.dirname(__file__), "..", "logs", "sensors-debug.log"), "w", encoding="utf-8") as debug_file:
        debug_file.write(sensors)
except OSError:
    pass

respond({
    "ok": True,
    "timestamp": int(time.time()),
    "accelerometer": extract_reading(sensors, "accelerometer", vector=True),
    "gyroscope": extract_reading(sensors, "gyroscope", vector=True),
    "light": extract_reading(sensors, "light", vector=False),
    "proximity": extract_reading(sensors, "proximity", vector=False),
    "orientation": extract_reading(sensors, "orientation", vector=True),
    "battery": battery_match.group(1) if battery_match else "",
    "thermal": first_number(thermal),
    "wifi_rssi": wifi_match.group(1) if wifi_match else "",
    "bluetooth_enabled": bt_match.group(1).lower() if bt_match else "",
})
