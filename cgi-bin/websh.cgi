#!/usr/bin/env python3
import cgi
import http.cookies
import os
import subprocess
import telnetlib
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
if target == "modem" and not command.isascii():
    print("Modem commands must use standard ASCII characters.")
    raise SystemExit

try:
    if target == "modem":
        modem = telnetlib.Telnet("10.0.0.1", 8888, 8)
        modem.write((command.rstrip("\r\n") + "\r\n").encode("ascii"))
        time.sleep(1)
        modem_output = modem.read_very_eager().decode("utf-8", errors="replace")
        modem.close()
        output = modem_output.replace("\r", "")
        print(output.rstrip() or "Modem returned no output.")
        raise SystemExit
    elif target == "pi":
        password = os.environ.get("WEBSSH_PASSWORD", "jee")
        username = os.environ.get("WEBSSH_USER", "q")
        pi = telnetlib.Telnet("10.0.0.11", 23, 8)
        pi.read_until(b"login: ", 8)
        pi.write(username.encode("ascii") + b"\n")
        pi.read_until(b"Password: ", 8)
        pi.write(password.encode("ascii") + b"\n")
        # Skip straight past the login shell's MOTD/banner into a bare, promptless /bin/sh.
        ready_marker = "WEBSH_READY_%d" % int(time.time() * 1000)
        pi.write(b"PS1= exec /bin/sh\n")
        pi.write(("echo " + ready_marker + "\n").encode("ascii"))
        pi.read_until(ready_marker.encode("ascii"), 8)  # consume echoed input line
        ready_buf = pi.read_until(ready_marker.encode("ascii"), 8)  # consume banner + actual output
        if ready_marker.encode("ascii") not in ready_buf:
            raise ConnectionError("Pi shell did not become ready.")
        marker = "WEBSH_DONE_%d" % int(time.time() * 1000)
        pi.write(command.rstrip("\r\n").encode("utf-8", errors="replace") + b"\n")
        pi.write(("echo " + marker + "\n").encode("ascii"))
        pi.read_until(marker.encode("ascii"), 15)
        pi_raw = pi.read_until(marker.encode("ascii"), 15)
        pi.close()
        pi_output = pi_raw.decode("utf-8", errors="replace").replace("\r", "")
        lines = pi_output.split("\n")
        pi_output = "\n".join(line for line in lines if marker not in line and line.strip() != command.strip())
        output = pi_output.strip()
        print(output or "Command returned no output.")
        raise SystemExit
    else:
        process = subprocess.run(
            ["adb", "shell", command],
            capture_output=True,
            text=True,
            timeout=15,
        )
except OSError as error:
    if target == "modem":
        print("Could not connect to modem Telnet: " + str(error))
        raise SystemExit
    if target == "pi":
        print("Could not connect to Pi Telnet: " + str(error))
        raise SystemExit
    if isinstance(error, FileNotFoundError):
        print("Required command is unavailable: " + error.filename)
        raise SystemExit
    raise
except EOFError:
    print("Pi Telnet session closed unexpectedly (check login/password).")
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
