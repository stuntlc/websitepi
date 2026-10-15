#!/usr/bin/env python3
"""Proxy Google Air Quality heatmap tiles so the key stays server-side (/home/q/.websitepi/google_maps_key)."""
import os
import re
import sys
import urllib.request
from urllib.parse import parse_qs

KEY_FILE = "/home/q/.websitepi/google_maps_key"


def fail(status):
    print("Status: " + status)
    print("Content-Type: text/plain")
    print()
    sys.exit(0)


q = parse_qs(os.environ.get("QUERY_STRING", ""))
z, x, y = (q.get(k, [""])[0] for k in ("z", "x", "y"))
if not all(re.fullmatch(r"\d{1,3}", v) for v in (z, x, y)):
    fail("400 Bad Request")
try:
    with open(KEY_FILE) as f:
        key = f.read().strip()
    url = "https://airquality.googleapis.com/v1/mapTypes/US_AQI/heatmapTiles/%s/%s/%s?key=%s" % (z, x, y, key)
    with urllib.request.urlopen(url, timeout=15) as r:
        data = r.read()
except Exception:
    fail("502 Bad Gateway")
sys.stdout.write("Content-Type: image/png\nCache-Control: max-age=1800\n\n")
sys.stdout.flush()
sys.stdout.buffer.write(data)
