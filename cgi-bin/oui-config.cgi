#!/usr/bin/env python3
import cgi
import json
import os
import re

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(root_dir, "logs", "oui-config.json")

def respond(status, payload):
    print("Content-Type: application/json")
    print("Status: %s\n" % status)
    print(json.dumps(payload))
    raise SystemExit

try:
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
except (OSError, ValueError):
    config = {}

if os.environ.get("REQUEST_METHOD", "GET") != "POST":
    respond("200 OK", {"sms_number": config.get("sms_number", ""), "sms_enabled": bool(config.get("sms_enabled"))})

form = cgi.FieldStorage()
number = re.sub(r"[\s().-]", "", form.getfirst("number", "").strip())
enabled = form.getfirst("enabled", "") == "1"
if number.startswith("00"):
    number = "+" + number[2:]
elif re.fullmatch(r"0[1-9]\d{8}", number):
    number = "+32" + number[1:]
if number and not re.fullmatch(r"\+[1-9]\d{6,14}", number):
    respond("400 Bad Request", {"error": "Enter a valid international phone number (for example +32470123456)."})
if enabled and not number:
    respond("400 Bad Request", {"error": "Enter a number before enabling SMS alerts."})

config = {"sms_number": number, "sms_enabled": enabled}
os.makedirs(os.path.dirname(config_path), exist_ok=True)
with open(config_path, "w", encoding="utf-8") as handle:
    json.dump(config, handle)
respond("200 OK", config)
