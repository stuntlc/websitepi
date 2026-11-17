#!/usr/bin/env python3
"""Open a YouTube video in the connected phone's default browser."""
import cgi
from contextlib import contextmanager
import json
import os
import re
import shlex
import subprocess
import time
from urllib.parse import parse_qs, urlsplit

from phone_fullscreen import enter_fullscreen

ADB = os.environ.get("ADB", "adb")
PHONE = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")
LOCK_PATH = "/tmp/websitepi-phone-ui.lock"
ROTATION_PATH = "/tmp/websitepi-video-rotation.json"


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def video_url(value):
    try:
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or url.username or url.password or url.port:
            return None
        host = (url.hostname or "").lower()
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if url.path == "/watch":
                ids = parse_qs(url.query).get("v", [])
                video_id = ids[0] if len(ids) == 1 else ""
            else:
                parts = url.path.split("/")
                video_id = parts[2] if len(parts) == 3 and parts[1] in ("shorts", "embed", "live") else ""
        elif host in ("youtu.be", "www.youtu.be"):
            video_id = url.path[1:]
        else:
            return None
    except ValueError:
        return None
    if not VIDEO_ID.fullmatch(video_id):
        return None
    return "https://www.youtube.com/watch?v=" + video_id + "&autoplay=1"


def run_adb(*args):
    return subprocess.run(
        [ADB, "-s", PHONE, *args], capture_output=True, text=True, timeout=15
    )


def adb_checked(*args):
    result = run_adb(*args)
    if result.returncode != 0 or "Error:" in result.stdout or "Error:" in result.stderr:
        raise RuntimeError((result.stderr or result.stdout).strip() or "adb command failed.")
    return result


@contextmanager
def phone_lock():
    import fcntl
    with open(LOCK_PATH, "w") as lock:
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Phone controls are busy. Try again.")
                time.sleep(0.1)
        yield


def save_and_set_landscape():
    if not os.path.exists(ROTATION_PATH):
        auto = adb_checked("shell", "settings", "get", "system", "accelerometer_rotation").stdout.strip()
        rotation = adb_checked("shell", "settings", "get", "system", "user_rotation").stdout.strip()
        if auto not in ("0", "1") or rotation not in ("0", "1", "2", "3"):
            raise RuntimeError("Could not read the phone's rotation settings.")
        with open(ROTATION_PATH, "x") as state:
            json.dump({"auto": auto, "rotation": rotation}, state)
    adb_checked("shell", "settings", "put", "system", "accelerometer_rotation", "0")
    adb_checked("shell", "settings", "put", "system", "user_rotation", "1")


def restore_rotation():
    if not os.path.exists(ROTATION_PATH):
        return
    with open(ROTATION_PATH) as state:
        saved = json.load(state)
    if saved.get("auto") not in ("0", "1") or saved.get("rotation") not in ("0", "1", "2", "3"):
        raise RuntimeError("Saved phone rotation settings are invalid.")
    adb_checked("shell", "settings", "put", "system", "user_rotation", saved["rotation"])
    adb_checked("shell", "settings", "put", "system", "accelerometer_rotation", saved["auto"])
    os.remove(ROTATION_PATH)


def main():
    if os.environ.get("REQUEST_METHOD") != "POST":
        respond({"ok": False, "error": "Use POST to open a video."}, "405 Method Not Allowed")
        return
    try:
        length = int(os.environ.get("CONTENT_LENGTH", "0"))
    except ValueError:
        length = 0
    if length <= 0 or length > 8192:
        respond({"ok": False, "error": "Invalid request length."}, "400 Bad Request")
        return
    form = cgi.FieldStorage()
    action = form.getfirst("action", "play")
    if action not in ("play", "stop", "fullscreen"):
        respond({"ok": False, "error": "Unknown video action."}, "400 Bad Request")
        return
    url = video_url(form.getfirst("url", "").strip()) if action != "stop" else None
    if action != "stop" and not url:
        respond({"ok": False, "error": "Enter a valid YouTube video link."}, "400 Bad Request")
        return
    try:
        with phone_lock():
            browser = adb_checked(
                "shell", "cmd", "package", "resolve-activity", "--brief",
                "-a", "android.intent.action.VIEW", "-c", "android.intent.category.BROWSABLE",
                "-d", "https://example.com"
            )
            lines = browser.stdout.strip().splitlines()
            component = lines[-1].strip() if lines else ""
            if not COMPONENT.fullmatch(component) or component.startswith("android/"):
                raise RuntimeError("No default browser found on the phone. Set a default browser first.")
            package = component.split("/", 1)[0]
            if action == "stop":
                adb_checked("shell", "am", "force-stop", package)
                restore_rotation()
            elif action == "play":
                try:
                    save_and_set_landscape()
                    adb_checked(
                        "shell", "am", "start", "-n", component,
                        "-a", "android.intent.action.VIEW", "-d", shlex.quote(url)
                    )
                except (OSError, subprocess.TimeoutExpired, RuntimeError):
                    restore_rotation()
                    raise
            else:
                video_id = parse_qs(urlsplit(url).query)["v"][0]
                ready = enter_fullscreen(run_adb, package, video_id)
                respond({"ok": True, "ready": ready})
                return
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError) as error:
        respond({"ok": False, "error": "Phone video failed: " + str(error)}, "502 Bad Gateway")
        return
    message = ("Phone browser stopped." if action == "stop"
               else "Video opened in the phone browser. Press play if needed.")
    respond({"ok": True, "message": message})


if __name__ == "__main__":
    main()
