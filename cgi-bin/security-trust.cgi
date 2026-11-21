#!/usr/bin/env python3
"""Maintain the SEC trusted-device inventory; this does not enforce access."""
import fcntl
import json
import os
import re
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

from security_access import authorized, PROTECTED_PATH
from websitepi_paths import log_directory


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(log_directory(ROOT), "security-trust.json")
MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


def valid_mac(mac):
    return bool(MAC.fullmatch(mac)) and mac != "00:00:00:00:00:00" and not int(mac[:2], 16) & 1


def read_trust(path, required=False):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        if required:
            raise
        return []
    if not isinstance(data, list) or any(not isinstance(mac, str) or not valid_mac(mac) for mac in data):
        raise ValueError("Invalid trusted-device inventory.")
    if len(set(data)) != len(data):
        raise ValueError("Duplicate trusted-device inventory entries.")
    return data


def update_trust(path, mac, action):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    with open(path + ".lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        devices = read_trust(path)
        if action == "remove" and mac in read_trust(PROTECTED_PATH, required=True):
            raise PermissionError("This device is protected and cannot be removed from trust.")
        if action == "add" and mac not in devices:
            devices.append(mac)
        elif action == "remove" and mac in devices:
            devices.remove(mac)
        fd, temporary = tempfile.mkstemp(prefix=".security-trust-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(sorted(devices), handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return sorted(devices)


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def main():
    method = os.environ.get("REQUEST_METHOD", "")
    if method not in ("GET", "POST"):
        respond({"ok": False, "error": "Use GET or POST."}, "405 Method Not Allowed")
        return
    origin = os.environ.get("HTTP_ORIGIN")
    try:
        parsed_origin = urlsplit(origin) if origin else None
        cross_origin = parsed_origin and (parsed_origin.scheme not in ("http", "https") or
                                           parsed_origin.netloc.lower() != os.environ.get("HTTP_HOST", "").lower())
    except ValueError:
        cross_origin = True
    if os.environ.get("HTTP_SEC_FETCH_SITE") == "cross-site" or cross_origin:
        respond({"ok": False, "error": "Cross-origin requests are not allowed."}, "403 Forbidden")
        return
    try:
        if not authorized():
            respond({"ok": False, "error": "Trusted client certificate and device required."}, "403 Forbidden")
            return
        protected = read_trust(PROTECTED_PATH, required=True)
        if method == "POST":
            length = int(os.environ.get("CONTENT_LENGTH", "0"))
            if not 0 < length <= 2048:
                raise ValueError("Invalid request length.")
            if os.environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                raise ValueError("Invalid request content type.")
            form = parse_qs(sys.stdin.read(length), keep_blank_values=True, strict_parsing=True)
            if set(form) != {"mac", "action"} or any(len(values) != 1 for values in form.values()):
                raise ValueError("Invalid request fields.")
            mac = form["mac"][0].strip().upper()
            action = form["action"][0]
            if not valid_mac(mac) or action not in ("add", "remove"):
                raise ValueError("Invalid MAC address or action.")
            devices = update_trust(PATH, mac, action)
        else:
            devices = read_trust(PATH)
        respond({"ok": True, "devices": devices, "protected": protected})
    except PermissionError as error:
        respond({"ok": False, "error": str(error)}, "403 Forbidden")
    except ValueError as error:
        respond({"ok": False, "error": str(error)}, "400 Bad Request")
    except OSError as error:
        respond({"ok": False, "error": "Could not read or save trusted devices: " + str(error)}, "500 Internal Server Error")


if __name__ == "__main__":
    main()
