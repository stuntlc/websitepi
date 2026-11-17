#!/usr/bin/env python3
import cgi
import os
import re
import signal
import subprocess

print("Content-Type: text/plain")

form = cgi.FieldStorage()
number = re.sub(r"[\s().-]", "", form.getfirst("number", "").strip())
message = form.getfirst("message", "").strip()

if number.startswith("00"):
    number = "+" + number[2:]
elif re.fullmatch(r"0[1-9]\d{8}", number):
    number = "+32" + number[1:]

if not re.fullmatch(r"\+[1-9]\d{6,14}", number):
    print("Status: 400 Bad Request\n")
    print("Enter a valid international phone number (for example, +33637035216 or 0033637035216).")
    raise SystemExit
if not message or len(message) > 1000:
    print("Status: 400 Bad Request\n")
    print("Enter a message up to 1000 characters.")
    raise SystemExit
if not message.isascii() or any(ord(character) < 32 for character in message):
    print("Status: 400 Bad Request\n")
    print("Unsupported character. SMS text must use standard keyboard characters.")
    raise SystemExit

script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "piscripts", "smsend")
try:
    process = subprocess.Popen(
        ["/bin/bash", script, number, message], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    stdout, stderr = process.communicate(timeout=45)
except subprocess.TimeoutExpired:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        stdout, stderr = process.communicate(timeout=10)
        detail = (stdout + stderr).strip()
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        detail = "Forced termination; check the phone's rotation setting."
    print("Status: 504 Gateway Timeout\n")
    print("The modem did not finish sending the SMS.")
    if detail:
        print(detail)
    raise SystemExit
except OSError as error:
    print("Status: 502 Bad Gateway\n")
    print("Could not start the SMS command: " + str(error))
    raise SystemExit

print(("Status: 200 OK" if process.returncode == 0 else "Status: 502 Bad Gateway") + "\n")
print((stdout + stderr).strip())