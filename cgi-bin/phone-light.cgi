#!/usr/bin/env python3
"""Control the phone flashlight signal service from an authorized browser."""
import json
import os
import socket
import sys
from urllib.parse import parse_qs

from security_access import authorized, same_origin


def respond(payload):
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def main():
    try:
        if not same_origin() or not authorized():
            raise PermissionError("Trusted client certificate and device required.")
        method = os.environ.get("REQUEST_METHOD", "")
        if method == "GET":
            request = {"action": "status"}
        elif method == "POST":
            length = int(os.environ.get("CONTENT_LENGTH", "0"))
            if not 0 < length <= 512:
                raise ValueError("Invalid request length.")
            if os.environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                raise ValueError("Invalid request content type.")
            form = parse_qs(sys.stdin.read(length), keep_blank_values=True, strict_parsing=True)
            if set(form) == {"action"} and form["action"] == ["stop"]:
                request = {"action": "stop"}
            elif set(form) == {"action", "mode", "message"} and form["action"] == ["start"] and len(form["mode"]) == len(form["message"]) == 1:
                request = {"action": "start", "mode": form["mode"][0], "message": form["message"][0]}
            else:
                raise ValueError("Invalid flashlight action.")
        else:
            raise ValueError("Use GET or POST.")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(25)
            connection.connect("/run/websitepi-light/control.sock")
            connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
            data = bytearray()
            while b"\n" not in data:
                chunk = connection.recv(4096)
                if not chunk:
                    raise RuntimeError("Flashlight service closed without a response.")
                data.extend(chunk)
                if len(data) > 4096:
                    raise ValueError("Flashlight response is too large.")
        response = json.loads(data.split(b"\n", 1)[0])
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise ValueError("Invalid flashlight service response.")
        respond(response)
    except (OSError, ValueError, RuntimeError) as error:
        respond({"ok": False, "error": str(error)})


if __name__ == "__main__":
    main()
