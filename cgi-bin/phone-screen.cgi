#!/usr/bin/env python3
"""Return a screenshot from the connected phone."""
import os
import subprocess
import sys


def fail(message):
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(message)


def main():
    adb = os.environ.get("ADB", "adb")
    phone = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
    try:
        result = subprocess.run(
            [adb, "-s", phone, "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        fail("Phone screenshot failed: " + str(error))
        return
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", "replace").strip() or "adb command failed."
        fail("Phone screenshot failed: " + error)
        return
    if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        fail("Phone screenshot failed: invalid image returned by adb.")
        return
    sys.stdout.buffer.write(
        b"Content-Type: image/png\r\nCache-Control: no-store\r\n\r\n" + result.stdout
    )


if __name__ == "__main__":
    main()
