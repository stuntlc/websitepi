#!/usr/bin/env python3
import base64
import cgi
import os
import re
import string
import subprocess
import sys

HOST = "10.0.0.50"
REMOTE_USER = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
REC_DIR = "/home/q/recorded"
BASE64_CHARS = set(string.ascii_letters + string.digits + "+/=")

form = cgi.FieldStorage()
name = form.getfirst("name", "")
if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:mp3|wav)", name):
    print("Status: 400 Bad Request")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Invalid recording name.")
    raise SystemExit

remote_path = REC_DIR + "/" + name
not_found = "BTMIC_FILE_NOTFOUND"
quoted = remote_path.replace("'", "'\\''")
remote_command = "test -f '" + quoted + "' && base64 '" + quoted + "' || echo " + not_found

try:
    process = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", REMOTE_USER + "@" + HOST, remote_command],
        capture_output=True,
        text=True,
        timeout=60,
    )
except (OSError, subprocess.TimeoutExpired) as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 connection failed: " + str(error))
    raise SystemExit

if process.returncode != 0:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 connection failed: " + (process.stderr.strip() or "ssh exited with status %d" % process.returncode))
    raise SystemExit

text = process.stdout
if not_found in text:
    print("Status: 404 Not Found")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Recording not found.")
    raise SystemExit

b64_data = "".join(character for character in text if character in BASE64_CHARS)
try:
    audio_bytes = base64.b64decode(b64_data + "=" * (-len(b64_data) % 4))
except (ValueError, base64.binascii.Error):
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 returned malformed recording data.")
    raise SystemExit

content_type = "audio/mpeg" if name.lower().endswith(".mp3") else "audio/wav"
print("Content-Type: " + content_type)
print("Content-Disposition: inline; filename=\"" + name + "\"")
print("Cache-Control: no-cache")
print()
sys.stdout.flush()
os.write(1, audio_bytes)