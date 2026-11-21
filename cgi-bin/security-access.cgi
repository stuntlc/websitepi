#!/usr/bin/env python3
"""Report access for a trusted client certificate and LAN device."""
import json
import os

from security_access import authorized, same_origin


def respond(payload):
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def main():
    try:
        if not same_origin():
            raise PermissionError("Cross-origin requests are not allowed.")
        method = os.environ.get("REQUEST_METHOD", "")
        if method == "GET":
            respond({"ok": True, "authorized": authorized()})
        else:
            raise ValueError("Use GET.")
    except (OSError, ValueError, RuntimeError) as error:
        respond({"ok": False, "error": str(error)})


if __name__ == "__main__":
    main()
