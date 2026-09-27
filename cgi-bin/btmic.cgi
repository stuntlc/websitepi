#!/usr/bin/env python3
import cgi
import json
import os
import subprocess

HOST = "10.0.0.50"
REMOTE_USER = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
REMOTE_SCRIPT = "/home/q/btmic.sh"


def run_remote(command, timeout=20):
    try:
        process = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", REMOTE_USER + "@" + HOST, command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except OSError as error:
        raise ConnectionError(str(error)) from error
    return process.returncode, (process.stdout + process.stderr).strip()


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
except subprocess.TimeoutExpired:
    respond({"ok": False, "error": "Pi5 command timed out."}, "502 Bad Gateway")
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