#!/usr/bin/env python3
import os
import re
import subprocess
import time

print("Content-Type: text/plain; charset=utf-8")
print()

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
adb = os.environ.get("ADB", "adb")
phone = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")


def run(*arguments, timeout=15, input_text=None):
    return subprocess.run(
        [adb, "-s", phone, *arguments],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def latest_media():
    listing = run(
        "shell", "content", "query",
        "--uri", "content://media/external/images/media",
        "--projection", "_data:date_added",
        "--sort", "date_added",
    ).stdout.replace("\r", "")
    records = re.findall(r"_data=([^,\n]+), date_added=(\d+)", listing)
    return records[-1] if records else ("", "0")


def capture_camera(label, front=False):
    extra = ["--ez", "android.intent.extra.USE_FRONT_CAMERA", "true"] if front else []
    old_path, old_date = latest_media()
    run("shell", "am", "force-stop", "com.android.camera")
    run("shell", "am", "start", "-a", "android.media.action.IMAGE_CAPTURE", *extra)
    time.sleep(3)
    run("shell", "input", "keyevent", "KEYCODE_CAMERA")
    time.sleep(3)
    source, new_date = latest_media()
    if not source or int(new_date) <= int(old_date):
        raise RuntimeError("Camera did not create an image")
    source = source.strip()
    if not source.startswith("/storage/"):
        raise RuntimeError("Camera image path is unavailable")
    destination = os.path.join(root, "phone-" + label + ".jpg")
    subprocess.run([adb, "-s", phone, "pull", source, destination], capture_output=True, text=True, timeout=20, check=True)
    run("shell", "input", "keyevent", "KEYCODE_BACK")
    return "/phone-" + label + ".jpg"


try:
    run("wait-for-device", timeout=20)
    rear = capture_camera("rear")
    front = capture_camera("front", front=True)
    print("rear=" + rear)
    print("front=" + front)
    print("Phone rear and front photos captured.")
except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as error:
    try:
        run("shell", "input", "keyevent", "KEYCODE_BACK")
    except Exception:
        pass
    print("Camera capture failed: " + str(error))
