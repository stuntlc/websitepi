#!/usr/bin/env python3
"""Detect, install, launch, and start/stop the UdpMic Android app over adb (USB or already-connected)."""
import cgi
import ipaddress
import json
import os
import subprocess

APP_PACKAGE = "com.skunkworks.udpmic"
APP_COMPONENT = APP_PACKAGE + "/.StreamService"
APP_ACTIVITY = APP_PACKAGE + "/.MainActivity"
APK_PATH = os.environ.get("UDPMIC_APK_PATH", "/home/q/websd/android/UdpMic.apk")


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print()
    print(json.dumps(payload))


def run_adb(args, timeout=15):
    return subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout)


form = cgi.FieldStorage()
action = form.getfirst("action", "")
host = form.getfirst("host", "")
port = form.getfirst("port", "9100")

if action not in {"start", "stop", "status", "install", "launch"}:
    respond({"ok": False, "error": "Unknown action."}, "400 Bad Request")
    raise SystemExit

if action == "status":
    try:
        result = run_adb(["shell", "pm", "list", "packages", APP_PACKAGE])
    except (OSError, subprocess.TimeoutExpired) as error:
        respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
        raise SystemExit
    installed = APP_PACKAGE in result.stdout
    respond({"ok": True, "installed": installed})
    raise SystemExit

if action == "install":
    if not os.path.isfile(APK_PATH):
        respond({"ok": False, "error": "APK not found on Pi: " + APK_PATH}, "404 Not Found")
        raise SystemExit
    try:
        result = run_adb(["install", "-r", APK_PATH], timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        respond({"ok": False, "error": "adb install failed: " + str(error)}, "502 Bad Gateway")
        raise SystemExit
    if result.returncode != 0 or "Success" not in result.stdout:
        message = (result.stderr or result.stdout).strip() or "adb install failed."
        respond({"ok": False, "error": message}, "502 Bad Gateway")
        raise SystemExit
    respond({"ok": True, "message": "App installed."})
    raise SystemExit

if action == "launch":
    try:
        result = run_adb(["shell", "am", "start", "-n", APP_ACTIVITY])
    except (OSError, subprocess.TimeoutExpired) as error:
        respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
        raise SystemExit
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "adb launch failed."
        respond({"ok": False, "error": message}, "502 Bad Gateway")
        raise SystemExit
    respond({"ok": True, "message": "App launched. Allow the requested permissions on the phone."})
    raise SystemExit

if action == "start":
    try:
        ipaddress.ip_address(host)
    except ValueError:
        respond({"ok": False, "error": "Invalid host."}, "400 Bad Request")
        raise SystemExit
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        respond({"ok": False, "error": "Invalid port."}, "400 Bad Request")
        raise SystemExit
    command = [
        "shell", "am", "start-foreground-service",
        "-n", APP_COMPONENT,
        "-a", "com.skunkworks.udpmic.START",
        "--es", "host", host,
        "--ei", "port", port,
    ]
else:
    command = [
        "shell", "am", "startservice",
        "-n", APP_COMPONENT,
        "-a", "com.skunkworks.udpmic.STOP",
    ]

try:
    result = run_adb(command)
except (OSError, subprocess.TimeoutExpired) as error:
    respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

if result.returncode != 0:
    message = (result.stderr or result.stdout).strip() or "adb command failed."
    respond({"ok": False, "error": message}, "502 Bad Gateway")
    raise SystemExit

respond({"ok": True, "message": "App " + action + " command sent via adb."})
