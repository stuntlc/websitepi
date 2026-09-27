#!/usr/bin/env python3
import base64
import cgi
import os
import re
import string
import sys
import telnetlib
import time

HOST = "10.0.0.50"
REMOTE_USER = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
PASSWORD = os.environ.get("BTMIC_SSH_PASSWORD", os.environ.get("WEBSSH_PASSWORD", "jee"))
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
not_found = b"BTMIC_FILE_NOTFOUND"
end_marker = ("BTMIC_FILE_END_%d" % int(time.time() * 1000)).encode("ascii")

try:
    telnet = telnetlib.Telnet(HOST, 23, 8)
    telnet.read_until(b"login: ", 8)
    telnet.write(REMOTE_USER.encode("ascii") + b"\n")
    telnet.read_until(b"Password: ", 8)
    telnet.write(PASSWORD.encode("ascii") + b"\n")
    time.sleep(1)
    prompt = telnet.read_very_eager().strip(b"\r\n")
    quoted = remote_path.replace("'", "'\\''")
    telnet.write(
        ("test -f '" + quoted + "' && base64 '" + quoted + "' || echo " + not_found.decode("ascii") + "\n").encode("utf-8")
    )
    telnet.write(b"echo " + end_marker + b"\n")

    buf = b""
    deadline = time.time() + 60
    last_growth = time.time()
    while time.time() < deadline:
        time.sleep(0.3)
        chunk = telnet.read_very_eager()
        if chunk:
            buf += chunk
            last_growth = time.time()
        elif end_marker in buf and time.time() - last_growth > 0.6:
            break
    telnet.close()
except (OSError, EOFError) as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 connection failed: " + str(error))
    raise SystemExit

if not_found in buf:
    print("Status: 404 Not Found")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Recording not found.")
    raise SystemExit

if prompt:
    buf = buf.replace(prompt, b"")
text = buf.decode("ascii", errors="ignore")
end_index = text.find(end_marker.decode("ascii"))
payload = text[:end_index] if end_index != -1 else text
b64_data = "".join(character for character in payload if character in BASE64_CHARS)
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