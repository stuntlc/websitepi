#!/usr/bin/env python3
import os
import shlex
import shutil
import subprocess

stream_url = os.environ.get("PHONE_AUDIO_URL", "").strip()
command_text = os.environ.get("PHONE_AUDIO_COMMAND", "").strip()
content_type = os.environ.get("PHONE_AUDIO_CONTENT_TYPE", "audio/mpeg")

if not stream_url and not command_text:
    print("Status: 503 Service Unavailable")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Phone audio is not configured. Set PHONE_AUDIO_URL or PHONE_AUDIO_COMMAND.")
    raise SystemExit

try:
    if stream_url:
        command = ["curl", "--fail", "--location", "--silent", "--show-error", stream_url]
    else:
        command = shlex.split(command_text)
    if not command or not shutil.which(command[0]):
        raise FileNotFoundError(command[0] if command else "curl")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
except (OSError, ValueError) as error:
    print("Status: 503 Service Unavailable")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Phone audio source is unavailable: " + str(error))
    raise SystemExit

print("Content-Type: " + content_type)
print("Cache-Control: no-store")
print("X-Accel-Buffering: no")
print()

try:
    while True:
        data = process.stdout.read(8192)
        if not data:
            break
        os.write(1, data)
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=3)