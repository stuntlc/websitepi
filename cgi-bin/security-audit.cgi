#!/usr/bin/env python3
"""Report HTTPS client enrollment and recent access."""
import json
import os
import sqlite3

from security_access import authorized, same_origin
from security_audit import history, inventory


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def main():
    try:
        if os.environ.get("REQUEST_METHOD") != "GET":
            respond({"ok": False, "error": "Use GET."}, "405 Method Not Allowed")
        elif not same_origin() or not authorized():
            respond({"ok": False, "error": "Trusted client certificate and device required."}, "403 Forbidden")
        else:
            respond({"ok": True, "clients": inventory(), "events": history()})
    except (OSError, ValueError, RuntimeError) as error:
        respond({"ok": False, "error": str(error)}, "500 Internal Server Error")
    except sqlite3.Error as error:
        respond({"ok": False, "error": "Could not read access history: " + str(error)}, "500 Internal Server Error")


if __name__ == "__main__":
    main()
