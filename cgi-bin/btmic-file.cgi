#!/usr/bin/env python3
import cgi
import os
import re
import subprocess
import sys

HOST = "10.0.0.50"
REMOTE_USER = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
PASSWORD = os.environ.get("BTMIC_SSH_PASSWORD", os.environ.get("WEBSSH_PASSWORD", "jee"))
REC_DIR = "/home/q/recorded"

form = cgi.FieldStorage()
name = form.getfirst("name", "")
if not re.fullmatch(r"[A-Za-z0-9_.-]+\.(?:mp3|wav)", name):
    print("Status: 400 Bad Request")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Invalid recording name.")
    raise SystemExit

remote_path = REC_DIR + "/" + name
try:
    process = subprocess.Popen(
        [
            "sshpass",
            "-p",
            PASSWORD,
            "ssh",
            "-o",
            "StrictHostKeyChecking=accept-new",
            REMOTE_USER + "@" + HOST,
            "test -f '" + remote_path + "' && cat '" + remote_path + "'",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
except OSError as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 connection failed: " + str(error))
    raise SystemExit

first_chunk = process.stdout.read(4)
if process.poll() not in (None, 0) and not first_chunk:
    print("Status: 404 Not Found")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Recording not found.")
    raise SystemExit

content_type = "audio/mpeg" if name.lower().endswith(".mp3") else "audio/wav"
print("Content-Type: " + content_type)
print("Content-Disposition: inline; filename=\"" + name + "\"")
print("Cache-Control: no-cache")
print()
sys.stdout.flush()
if first_chunk:
    os.write(1, first_chunk)
while True:
    chunk = process.stdout.read(65536)
    if not chunk:
        break
    os.write(1, chunk)
process.wait()