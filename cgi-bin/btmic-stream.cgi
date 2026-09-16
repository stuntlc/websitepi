#!/usr/bin/env python3
import cgi
import os
import socket
import sys
import time

HOST = "10.0.0.50"
PORT = 8000
request_started = time.monotonic()
pi_connected = None
pi_headers = None

# The Pi5 stream sends its own HTTP response; the CGI server supplies the browser-facing headers.
try:
    connection = socket.create_connection((HOST, PORT), timeout=10)
    pi_connected = time.monotonic()
    connection.settimeout(None)
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("Pi5 stream closed before sending headers.")
        response += chunk
    _, body = response.split(b"\r\n\r\n", 1)
    pi_headers = time.monotonic()
except (OSError, ConnectionError) as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 live stream unavailable: " + str(error))
    raise SystemExit

print("Content-Type: audio/mpeg")
print("Cache-Control: no-cache, no-store")
print("X-Accel-Buffering: no")
print("Server-Timing: pi-connect;dur=%.1f, pi-headers;dur=%.1f" % (
    (pi_connected - request_started) * 1000,
    (pi_headers - request_started) * 1000,
))
print("X-BTMIC-Trace: pi-connect-ms=%.1f; pi-headers-ms=%.1f" % (
    (pi_connected - request_started) * 1000,
    (pi_headers - request_started) * 1000,
))
print()
sys.stdout.flush()
output = sys.stdout.buffer
if body:
    output.write(body)
    output.flush()

while True:
    chunk = connection.recv(65536)
    if not chunk:
        break
    output.write(chunk)
    output.flush()

connection.close()
