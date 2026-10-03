#!/usr/bin/env python3
import cgi
import json
import os
import re

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(root_dir, "logs", "oui-labels.json")

print("Content-Type: text/plain")
form = cgi.FieldStorage()
mac = form.getfirst("mac", "").strip().upper().replace("-", ":")
label = re.sub(r"[^\x20-\x7e]", "", form.getfirst("label", "")).strip()[:40]
if os.environ.get("REQUEST_METHOD") != "POST" or not re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", mac):
    print("Status: 400 Bad Request\n")
    print("POST a valid mac and label.")
    raise SystemExit

try:
    with open(path, encoding="utf-8") as handle:
        labels = json.load(handle)
except (OSError, ValueError):
    labels = {}
if label:
    labels[mac] = label
else:
    labels.pop(mac, None)
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(labels, handle, indent=1)
print("Status: 200 OK\n")
print("Saved")
