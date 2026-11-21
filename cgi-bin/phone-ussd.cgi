#!/usr/bin/env python3
"""Read the Orange prepaid data response and dismiss its USSD dialog."""
import json
import os
import re
import signal
import subprocess
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from phone_lock import phone_lock


PHONE_PACKAGE = "com.android.phone"
USSD_URI = "tel:%23123%2A1%23"


def adb(*args):
    command = [os.environ.get("ADB", "adb")]
    serial = os.environ.get("PHONE_ADB_SERIAL")
    if serial:
        command.extend(["-s", serial])
    result = subprocess.run(command + list(args), capture_output=True, text=True, timeout=30)
    if result.returncode or (args[:3] == ("shell", "am", "start") and
                             ("Error:" in result.stdout or "Error:" in result.stderr)):
        raise RuntimeError((result.stderr or result.stdout).strip() or "ADB command failed.")
    return result.stdout


def phone_ui():
    output = adb("exec-out", "uiautomator", "dump", "/dev/tty")
    start = output.find("<?xml")
    end = output.find("</hierarchy>")
    if start < 0 or end < 0:
        raise RuntimeError("Could not read the phone screen.")
    return ET.fromstring(output[start:end + len("</hierarchy>")])


def phone_dialog(root):
    nodes = [node for node in root.iter("node") if node.get("package") == PHONE_PACKAGE]
    messages = [node.get("text", "").strip() for node in nodes
                if node.get("resource-id") == "android:id/message"]
    if len(messages) > 1:
        raise RuntimeError("Multiple phone dialogs are visible.")
    return (messages[0], nodes) if messages else (None, nodes)


def request_pending(message):
    return message.lower().startswith("ussd code running")


def close_dialog():
    deadline = time.monotonic() + 25
    clear_checks = 0
    while time.monotonic() < deadline:
        message, nodes = phone_dialog(phone_ui())
        if message is None:
            clear_checks += 1
            if clear_checks == 2:
                return
        elif request_pending(message):
            clear_checks = 0
        else:
            clear_checks = 0
            buttons = [node for node in nodes
                       if node.get("clickable") == "true" and
                       ((node.get("resource-id") == "android:id/button2" and
                         node.get("text", "").strip().lower() == "cancel") or
                        (node.get("resource-id") == "android:id/button1" and
                         node.get("text", "").strip().lower() == "ok" and
                         "invalid mmi code" in message.lower()))]
            if len(buttons) != 1:
                raise RuntimeError("Cannot safely identify the USSD close button.")
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", buttons[0].get("bounds", ""))
            if not bounds:
                raise RuntimeError("Invalid USSD close button bounds.")
            left, top, right, bottom = map(int, bounds.groups())
            if right <= left or bottom <= top:
                raise RuntimeError("Invalid USSD close button bounds.")
            adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))
        time.sleep(1)
    raise RuntimeError("USSD dialog did not close.")


def read_balance():
    with phone_lock():
        message, _ = phone_dialog(phone_ui())
        if message is not None:
            raise RuntimeError("A phone dialog is already open; close it before checking balance.")
        error = None
        balance = None
        try:
            try:
                adb("shell", "am", "start", "-a", "android.intent.action.CALL", "-d", USSD_URI)
                deadline = time.monotonic() + 35
                while time.monotonic() < deadline:
                    message, _ = phone_dialog(phone_ui())
                    if message and not request_pending(message):
                        lines = [line.strip() for line in message.splitlines()
                                 if re.match(r"^(?:option\s*:\s*)?data\s*[, :]", line.strip(), re.I)]
                        if len(lines) != 1:
                            raise RuntimeError("Orange returned an unexpected response; no data balance was read.")
                        balance = re.sub(r"^option\s*:\s*", "", lines[0], flags=re.I)
                        break
                    time.sleep(1)
                if balance is None:
                    raise RuntimeError("Orange did not respond in time; a delayed phone dialog may still appear.")
            except (OSError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as exc:
                error = exc
        finally:
            try:
                close_dialog()
            except (OSError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as exc:
                detail = "Could not verify that the USSD dialog closed: " + str(exc)
                if error is not None:
                    detail = str(error) + " " + detail
                raise RuntimeError(detail) from exc
        if error is not None:
            raise RuntimeError(str(error)) from error
        return balance


def main():
    if os.environ.get("REQUEST_METHOD") != "POST":
        respond({"ok": False, "error": "Use POST to check the balance."}, "405 Method Not Allowed")
        return
    origin = os.environ.get("HTTP_ORIGIN")
    if os.environ.get("HTTP_SEC_FETCH_SITE") == "cross-site" or (
            origin and (urlsplit(origin).scheme not in ("http", "https") or
                        urlsplit(origin).netloc.lower() != os.environ.get("HTTP_HOST", "").lower())):
        respond({"ok": False, "error": "Cross-origin requests are not allowed."}, "403 Forbidden")
        return

    from security_gate import require_access
    if not require_access("json"):
        return

    def interrupted(signum, frame):
        raise RuntimeError("SIM check was interrupted.")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        balance = read_balance()
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as error:
        respond({"ok": False, "error": str(error)}, "502 Bad Gateway")
        return
    respond({"ok": True, "data": balance, "checked_at": int(time.time())})


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
