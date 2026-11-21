#!/usr/bin/env python3
import os
import select
import subprocess
import sys
import tempfile
import time
from btmic_ssh import restricted, ssh_command

if os.environ.get("REQUEST_METHOD"):
    from security_gate import require_access
    if not require_access():
        raise SystemExit

started = time.monotonic()

with tempfile.TemporaryFile() as errors:
    try:
        process = subprocess.Popen(
            ssh_command("websitepi-btmic stream" if restricted() else
                        "exec curl --fail --silent --show-error --no-buffer --connect-timeout 8 http://127.0.0.1:8000/live.mp3"),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
        )
    except (OSError, ValueError) as error:
        print("Status: 502 Bad Gateway")
        print("Content-Type: text/plain; charset=utf-8\n")
        print("Pi5 live stream unavailable: " + str(error))
        raise SystemExit

    try:
        readable, _, _ = select.select([process.stdout], [], [], 20)
        first = process.stdout.read1(8192) if readable else b""
        if not first:
            errors.seek(0)
            detail = errors.read(4096).decode("utf-8", errors="replace").strip()
            print("Status: 502 Bad Gateway")
            print("Content-Type: text/plain; charset=utf-8\n")
            print("Pi5 live stream unavailable: " + (detail or "No audio received within 20 seconds."))
            raise SystemExit
        print("Content-Type: audio/mpeg")
        print("Cache-Control: no-cache, no-store")
        print("X-Accel-Buffering: no")
        print("X-BTMIC-Trace: first-audio-ms=%.1f" % ((time.monotonic() - started) * 1000))
        print()
        sys.stdout.flush()
        output = sys.stdout.buffer
        output.write(first)
        output.flush()
        while True:
            chunk = process.stdout.read1(8192)
            if not chunk:
                break
            output.write(chunk)
            output.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
