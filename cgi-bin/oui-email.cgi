#!/usr/bin/env python3
import cgi
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(root_dir, "logs", "oui-mail.json")

def respond(status, text):
    print("Content-Type: text/plain")
    print("Status: %s\n" % status)
    print(text)
    raise SystemExit

try:
    with open(config_path, encoding="utf-8") as handle:
        config = json.load(handle)
except (OSError, ValueError):
    respond("500 Internal Server Error", "Mail not configured. Create logs/oui-mail.json (see README).")

form = cgi.FieldStorage()
recipient = form.getfirst("to", "").strip() or config.get("default_to", "")
body = form.getfirst("message", "").strip()
if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient):
    respond("400 Bad Request", "Enter a valid email address.")
if not body or len(body) > 20000:
    respond("400 Bad Request", "Message is empty or too long.")

message = EmailMessage()
message["From"] = config.get("from") or config["user"]
message["To"] = recipient
message["Subject"] = "Skunk Works network report"
message.set_content(body)

try:
    host, port = config["server"], int(config.get("port", 587))
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)
        smtp.starttls(context=ssl.create_default_context())
    with smtp:
        smtp.login(config["user"], config["password"])
        smtp.send_message(message)
except (smtplib.SMTPException, OSError, KeyError) as error:
    respond("502 Bad Gateway", "Email failed: %s" % type(error).__name__)

respond("200 OK", "Email sent to %s" % recipient)
