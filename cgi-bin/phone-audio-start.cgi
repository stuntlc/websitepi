#!/usr/bin/env python3
import os
import subprocess
import sys

adb = os.environ.get("ADB", "adb")
phone = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
package = os.environ.get("PHONE_AUDIO_APP_PACKAGE", "io.github.teamclouday.AndroidMic")
activity = os.environ.get("PHONE_AUDIO_APP_ACTIVITY", "io.github.teamclouday.androidMic.ui.MainActivity")
port = os.environ.get("PHONE_AUDIO_ADB_PORT", "666")
component = package + "/" + activity

try:
    subprocess.run(
        [adb, "-s", phone, "reverse", "tcp:" + port, "tcp:" + port],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    result = subprocess.run(
        [adb, "-s", phone, "shell", "am", "start", "-n", component],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
    print("Status: 502 Bad Gateway")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Could not prepare or launch phone audio app: " + str(error))
    sys.exit(1)

print("Content-Type: text/plain; charset=utf-8")
print("Cache-Control: no-store")
print()
message = result.stdout.replace("\r", "").strip()
print("ADB reverse ready on tcp:" + port + "\nStarted " + component + ("\n" + message if message else ""))
