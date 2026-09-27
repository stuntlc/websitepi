#!/usr/bin/env python3
import cgi
import json
import os
import re
import telnetlib
import time

HOST = "10.0.0.50"
REMOTE_USER = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
PASSWORD = os.environ.get("BTMIC_SSH_PASSWORD", os.environ.get("WEBSSH_PASSWORD", "jee"))
REMOTE_SCRIPT = "/home/q/btmic.sh"


def _read_until_idle(telnet, end_marker, timeout):
    buf = b""
    deadline = time.time() + timeout
    last_growth = time.time()
    while time.time() < deadline:
        time.sleep(0.3)
        chunk = telnet.read_very_eager()
        if chunk:
            buf += chunk
            last_growth = time.time()
        elif end_marker in buf and time.time() - last_growth > 0.6:
            break
    return buf


def run_remote(command, timeout=20):
    end_marker = ("BTMIC_END_%d" % int(time.time() * 1000)).encode("ascii")
    try:
        telnet = telnetlib.Telnet(HOST, 23, 8)
        telnet.read_until(b"login: ", 8)
        telnet.write(REMOTE_USER.encode("ascii") + b"\n")
        telnet.read_until(b"Password: ", 8)
        telnet.write(PASSWORD.encode("ascii") + b"\n")
        time.sleep(1)
        prompt = telnet.read_very_eager().strip(b"\r\n")
        telnet.write(command.encode("utf-8", errors="replace") + b"\n")
        telnet.write(b"echo " + end_marker + b":$?\n")
        buf = _read_until_idle(telnet, end_marker, timeout)
        telnet.close()
    except (OSError, EOFError) as error:
        raise ConnectionError(str(error)) from error
    if prompt:
        buf = buf.replace(prompt, b"")
    text = buf.decode("utf-8", errors="replace").replace("\r", "")
    matches = re.findall(re.escape(end_marker.decode("ascii")) + r":(\d+)", text)
    returncode = int(matches[-1]) if matches else 1
    output = re.sub(re.escape(end_marker.decode("ascii")) + r":\d+", "", text)
    return returncode, output.strip()


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print()
    print(json.dumps(payload))


form = cgi.FieldStorage()
action = form.getfirst("action", "")

commands = {
    "stream-start": (
        "rm -f /tmp/btmic-stream.pid; "
        "setsid sh -c 'printf \"%s\\n\" stream | " + REMOTE_SCRIPT + "' "
        ">/tmp/btmic-stream.log 2>&1 </dev/null & echo $! >/tmp/btmic-stream.pid"
    ),
    "record-start": (
        "rm -f /tmp/btmic-record.pid; "
        "setsid sh -c 'printf \"%s\\n\" record 1 86400 | " + REMOTE_SCRIPT + "' "
        ">/tmp/btmic-record.log 2>&1 </dev/null & echo $! >/tmp/btmic-record.pid"
    ),
    "stop": (
        "for pidfile in /tmp/btmic-stream.pid /tmp/btmic-record.pid; do "
        "if test -s \"$pidfile\"; then "
        "pid=$(cat \"$pidfile\"); kill -- -\"$pid\" 2>/dev/null || kill \"$pid\" 2>/dev/null || true; "
        "rm -f \"$pidfile\"; fi; done"
    ),
    "list": r"find /home/q/recorded -maxdepth 1 -type f \( -name '*.mp3' -o -name '*.wav' \) -printf '%f\n' 2>/dev/null | sort",
}

if action not in commands:
    respond({"ok": False, "error": "Unknown action."}, "400 Bad Request")
    raise SystemExit

try:
    returncode, output = run_remote(commands[action], timeout=30 if action == "list" else 20)
except ConnectionError as error:
    respond({"ok": False, "error": "Pi5 connection failed: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

if returncode != 0:
    message = output.strip() or "Remote command failed."
    respond({"ok": False, "error": message}, "502 Bad Gateway")
    raise SystemExit

if action == "list":
    recordings = [line for line in output.splitlines() if line]
    respond({"ok": True, "recordings": recordings})
else:
    respond({"ok": True, "message": "Pi5 mic action started." if action != "stop" else "Pi5 mic stopped."})