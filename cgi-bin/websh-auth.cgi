#!/usr/bin/env python3
import cgi
import http.cookies
import os
import secrets
import time

SESSION_DIR = "/tmp/websitepi-websh-sessions"
PASSWORD = os.environ.get("WEBSH_PASSWORD", "bootloader")

form = cgi.FieldStorage()
password = form.getfirst("password", "")

if password != PASSWORD:
    print("Status: 401 Unauthorized")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Invalid admin password.")
    raise SystemExit

os.makedirs(SESSION_DIR, mode=0o700, exist_ok=True)
token = secrets.token_urlsafe(32)
with open(os.path.join(SESSION_DIR, token), "w", encoding="ascii") as session_file:
    session_file.write(str(int(time.time())))
os.chmod(os.path.join(SESSION_DIR, token), 0o600)

cookie = http.cookies.SimpleCookie()
cookie["websh_session"] = token
cookie["websh_session"]["path"] = "/"
cookie["websh_session"]["httponly"] = True
cookie["websh_session"]["samesite"] = "Strict"
cookie["websh_session"]["max-age"] = 1800

print("Status: 200 OK")
print("Content-Type: text/plain; charset=utf-8")
print(cookie.output())
print()
print("Authenticated")
