#!/usr/bin/env python3
import cgi
import os
import re
import subprocess

print("Content-Type: text/plain")

form = cgi.FieldStorage()
number = form.getfirst("number", "").strip()
message = form.getfirst("message", "").strip()

if not re.fullmatch(r"[+0-9(). -]{3,32}", number):
    print("Status: 400 Bad Request\n")
    print("Enter a valid phone number.")
    raise SystemExit
if not message or len(message) > 1000:
    print("Status: 400 Bad Request\n")
    print("Enter a message up to 1000 characters.")
    raise SystemExit

script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sms", "smsend")
try:
    result = subprocess.run(["/bin/bash", script, number, message], capture_output=True, text=True, timeout=45)
except subprocess.TimeoutExpired:
    print("Status: 504 Gateway Timeout\n")
    print("The modem did not finish sending the SMS.")
    raise SystemExit

print(("Status: 200 OK" if result.returncode == 0 else "Status: 502 Bad Gateway") + "\n")
print((result.stdout + result.stderr).strip())