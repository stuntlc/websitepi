#!/usr/bin/env python3
import cgi
import os
import socket
import sys

HOST = "10.0.0.50"
PORT = 8000

# The Pi5 stream sends its own HTTP response; the CGI server supplies the browser-facing headers.
try:
    connection = socket.create_connection((HOST, PORT), timeout=10)
    connection.settimeout(None)
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = connection.recv(4096)
        if not chunk:
            raise ConnectionError("Pi5 stream closed before sending headers.")
        response += chunk
    _, body = response.split(b"\r\n\r\n", 1)
except (OSError, ConnectionError) as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Pi5 live stream unavailable: " + str(error))
    raise SystemExit

print("Content-Type: audio/mpeg")
print("Cache-Control: no-cache, no-store")
print("X-Accel-Buffering: no")
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
