#!/usr/bin/env python3
"""Detect, install, launch, and start/stop the UdpMic Android app over adb (USB or already-connected)."""
import cgi
import ipaddress
import json
import os
import re
import subprocess

if os.environ.get("REQUEST_METHOD"):
    from security_gate import require_access
    if not require_access("json"):
        raise SystemExit

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

if action not in {"start", "stop", "status", "install", "launch", "link"}:
    respond({"ok": False, "error": "Unknown action."}, "400 Bad Request")
    raise SystemExit

if action == "link":
    try:
        pi = subprocess.run(
            ["ip", "-o", "-4", "addr", "show", "dev", "usb0"],
            capture_output=True, text=True, timeout=8,
        )
        phone = run_adb(["shell", "ip", "-o", "-4", "addr", "show", "dev", "rndis0"], timeout=8)
        if pi.returncode != 0 or phone.returncode != 0:
            raise RuntimeError((pi.stderr or phone.stderr or phone.stdout).strip() or "USB interface unavailable.")
        pi_addresses = [ipaddress.ip_interface(value) for value in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", pi.stdout)]
        phone_addresses = [ipaddress.ip_interface(value) for value in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", phone.stdout)]
        for pi_address in pi_addresses:
            for phone_address in phone_addresses:
                if phone_address.ip in pi_address.network and pi_address.ip in phone_address.network:
                    respond({"ok": True, "host": str(pi_address.ip), "phone": str(phone_address.ip)})
                    raise SystemExit
        raise RuntimeError("No matching IPv4 addresses on usb0 and phone rndis0.")
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
        respond({"ok": False, "error": "USB link check failed: " + str(error)}, "502 Bad Gateway")
        raise SystemExit

if action == "status":
    try:
        result = run_adb(["shell", "pm", "list", "packages", APP_PACKAGE])
    except (OSError, subprocess.TimeoutExpired) as error:
        respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
        raise SystemExit
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "adb status check failed."
        respond({"ok": False, "error": message}, "502 Bad Gateway")
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
    if result.returncode != 0 or "Error:" in result.stdout:
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
        "shell", "am", "stopservice",
        "-n", APP_COMPONENT,
    ]

try:
    result = run_adb(command)
except (OSError, subprocess.TimeoutExpired) as error:
    respond({"ok": False, "error": "adb command failed: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

stop_confirmed = (
    action == "stop"
    and result.returncode == 255
    and (
        result.stderr.strip() in {"Service stopped", "Service not stopped: was not running."}
        or (not result.stderr.strip()
            and result.stdout.strip().endswith(("Service stopped", "Service not stopped: was not running.")))
    )
)
if (result.returncode != 0 and not stop_confirmed) or "Error:" in result.stdout:
    message = (result.stderr or result.stdout).strip() or "adb command failed."
    respond({"ok": False, "error": message}, "502 Bad Gateway")
    raise SystemExit

respond({"ok": True, "message": "App " + action + " command sent via adb."})
