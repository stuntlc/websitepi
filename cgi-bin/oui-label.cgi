#!/usr/bin/env python3
import cgi
import fcntl
import json
import os
import re
import tempfile

from websitepi_paths import log_directory

if os.environ.get("REQUEST_METHOD"):
    from security_gate import require_access
    if not require_access():
        raise SystemExit

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(log_directory(root_dir), "oui-labels.json")

form = cgi.FieldStorage()
mac = form.getfirst("mac", "").strip().upper().replace("-", ":")
label = re.sub(r"[^\x20-\x7e]", "", form.getfirst("label", "")).strip()[:40]
if os.environ.get("REQUEST_METHOD") != "POST" or not re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", mac):
    print("Status: 400 Bad Request")
    print("Content-Type: text/plain\n")
    print("POST a valid mac and label.")
    raise SystemExit

try:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path, encoding="utf-8") as handle:
                labels = json.load(handle)
        except FileNotFoundError:
            labels = {}
        if not isinstance(labels, dict):
            raise ValueError("Invalid saved device names.")
        if label:
            labels[mac] = label
        else:
            labels.pop(mac, None)
        fd, temporary = tempfile.mkstemp(prefix=".oui-labels-", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(labels, handle, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
except (OSError, ValueError) as error:
    print("Status: 500 Internal Server Error")
    print("Content-Type: text/plain\n")
    print("Could not save device name: " + str(error))
    raise SystemExit
print("Content-Type: text/plain\n")
print("Saved")
