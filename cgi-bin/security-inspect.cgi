#!/usr/bin/env python3
"""Control the local Wi-Fi inspection service from an authorized browser."""
import json
import os
import socket
import sys
from urllib.parse import parse_qs

from security_access import authorized, same_origin


SOCKET_PATH = "/run/websitepi-inspect/control.sock"


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
            action = "status"
        elif method == "POST":
            length = int(os.environ.get("CONTENT_LENGTH", "0"))
            if not 0 < length <= 128:
                raise ValueError("Invalid request length.")
            if os.environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
                raise ValueError("Invalid request content type.")
            form = parse_qs(sys.stdin.read(length), keep_blank_values=True, strict_parsing=True)
            if set(form) != {"action"} or form["action"] not in (["start"], ["stop"]):
                raise ValueError("Invalid inspection action.")
            action = form["action"][0]
        else:
            raise ValueError("Use GET or POST.")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(15)
            connection.connect(SOCKET_PATH)
            connection.sendall((action + "\n").encode("ascii"))
            data = bytearray()
            while b"\n" not in data:
                chunk = connection.recv(65536)
                if not chunk:
                    raise RuntimeError("Inspection service closed without a response.")
                data.extend(chunk)
                if len(data) > 1024 * 1024:
                    raise RuntimeError("Inspection response is too large.")
        result = json.loads(data.split(b"\n", 1)[0])
        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            raise ValueError("Invalid inspection service response.")
        respond(result)
    except (OSError, ValueError, RuntimeError) as error:
        respond({"ok": False, "error": str(error)})


if __name__ == "__main__":
    main()
