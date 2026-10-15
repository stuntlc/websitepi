#!/usr/bin/env python3
"""Serve the Google Maps browser key from outside the web root (/home/q/.websitepi/google_maps_key).

The key still reaches the browser (Maps JS needs it), but it is not in git or the page source.
Lock it down with HTTP referrer + API restrictions in Google Cloud as well.
"""
import json
import os
from urllib.parse import urlparse

KEY_FILE = "/home/q/.websitepi/google_maps_key"


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


referer = os.environ.get("HTTP_REFERER", "")
host = os.environ.get("HTTP_HOST", "")
if not referer or urlparse(referer).netloc != host:
    respond({"ok": False, "error": "forbidden"}, "403 Forbidden")
else:
    try:
        with open(KEY_FILE) as f:
            respond({"ok": True, "key": f.read().strip()})
    except OSError:
        respond({"ok": False, "error": "key file missing"}, "500 Internal Server Error")
