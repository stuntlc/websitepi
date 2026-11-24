#!/usr/bin/env python3
"""Report current FM audio, relay GPIO and phone flashlight state."""
import json
import os

from device_status import read_states
from security_gate import require_access


if require_access("json"):
    if os.environ.get("REQUEST_METHOD") != "GET":
        print("Status: 405 Method Not Allowed")
        print("Content-Type: application/json; charset=utf-8\n")
        print(json.dumps({"ok": False, "error": "Use GET."}))
    else:
        print("Content-Type: application/json; charset=utf-8")
        print("Cache-Control: no-store\n")
        print(json.dumps({"ok": True, "devices": read_states()}))
