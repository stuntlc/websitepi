#!/usr/bin/env python3
"""Fail closed when protected CGI endpoints lack an authorized HTTPS session."""
import json
import sys

from security_access import authorized, same_origin


def require_access(response_type="text"):
    try:
        allowed = same_origin() and authorized()
        error = "A trusted client certificate and trusted device are required over HTTPS."
    except (OSError, ValueError, RuntimeError) as exc:
        allowed = False
        error = "SEC access check failed: " + str(exc)
    if allowed:
        return True
    print("Status: 403 Forbidden")
    if response_type == "json":
        print("Content-Type: application/json; charset=utf-8\n")
        print(json.dumps({"ok": False, "error": error}))
    else:
        print("Content-Type: text/plain; charset=utf-8\n")
        print("ERROR: " + error)
    return False


if __name__ == "__main__":
    raise SystemExit(0 if require_access(sys.argv[1] if len(sys.argv) > 1 else "text") else 1)
