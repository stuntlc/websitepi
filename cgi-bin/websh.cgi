#!/usr/bin/env python3
import cgi
import os
import re
import subprocess
import telnetlib
import time

from security_access import authorized, same_origin

try:
    allowed = same_origin() and authorized()
except (OSError, ValueError, RuntimeError) as error:
    allowed = False
if not allowed:
    print("Status: 403 Forbidden")
    print("Content-Type: text/plain; charset=utf-8\n")
    print("Authorize this trusted browser on SEC first.")
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
        # Every new connection dumps a startup banner + prompt before accepting input; discard it first.
        modem.read_until(b"# ", 5)
        modem.write((command.rstrip("\r\n") + "\r\n").encode("ascii"))
        time.sleep(1)
        modem_output = modem.read_very_eager().decode("utf-8", errors="replace")
        modem.close()
        output = re.sub(r"\x1b\[[0-9;]*m", "", modem_output.replace("\r", ""))
        print(output.rstrip() or "Modem returned no output.")
        raise SystemExit
    elif target == "pi":
        process = subprocess.run(
            ["/bin/sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=15,
            env=dict(os.environ, PATH="/usr/local/sbin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")),
        )
        output = (process.stdout + process.stderr).replace("\r", "")
        print(output.rstrip() or "Command returned no output.")
        if process.returncode != 0:
            print("\n[exit status: %s]" % process.returncode)
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
        print("Could not run Pi command: " + str(error))
        raise SystemExit
    if isinstance(error, FileNotFoundError):
        print("Required command is unavailable: " + error.filename)
        raise SystemExit
    raise
except EOFError:
    print("Modem Telnet session closed unexpectedly.")
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
