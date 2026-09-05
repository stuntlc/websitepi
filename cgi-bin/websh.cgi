#!/usr/bin/env python3
import cgi
import http.cookies
import os
import subprocess
import time

SESSION_DIR = "/tmp/websitepi-websh-sessions"

cookies = http.cookies.SimpleCookie(os.environ.get("HTTP_COOKIE", ""))
session = cookies.get("websh_session")
valid_session = False
if session and session.value.replace("_", "").replace("-", "").isalnum():
    session_path = os.path.join(SESSION_DIR, session.value)
    try:
        with open(session_path, encoding="ascii") as session_file:
            valid_session = time.time() - int(session_file.read()) < 1800
    except (FileNotFoundError, ValueError, OSError):
        pass

if not valid_session:
    print("Status: 401 Unauthorized")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("WebShell login required.")
    raise SystemExit

print("Content-Type: text/plain; charset=utf-8")
print()

form = cgi.FieldStorage()
target = form.getfirst("target", "")
command = form.getfirst("command", "")

if target not in {"modem", "pi", "phone"}:
    print("Invalid shell target.")
    raise SystemExit
if not command.strip():
    print("Enter a command.")
    raise SystemExit
if len(command) > 2000 or any(ord(character) < 32 and character not in "\t\n" for character in command):
    print("Command is too long or contains an unsupported control character.")
    raise SystemExit

try:
    if target == "modem":
        command = command.rstrip("\r\n") + "\r\n"
        process = subprocess.run(
            ["timeout", "10", "telnet", "10.0.0.1", "8888"],
            input=command,
            capture_output=True,
            text=True,
            timeout=12,
        )
    elif target == "pi":
        password = os.environ.get("WEBSSH_PASSWORD", "jee")
        process = subprocess.run(
            ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=accept-new", "q@10.0.0.11", command],
            capture_output=True,
            text=True,
            timeout=15,
        )
    else:
        process = subprocess.run(
            ["adb", "shell", command],
            capture_output=True,
            text=True,
            timeout=15,
        )
except FileNotFoundError as error:
    print("Required command is unavailable: " + error.filename)
    raise SystemExit
except subprocess.TimeoutExpired:
    print("Command timed out.")
    raise SystemExit

output = (process.stdout + process.stderr).replace("\r", "")
if output.strip():
    print(output.rstrip())
elif target == "modem":
    print("Modem closed the Telnet session without returning output.")
else:
    print("Command returned no output.")
if process.returncode != 0:
    print("\n[exit status: %s]" % process.returncode)
