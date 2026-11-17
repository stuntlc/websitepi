#!/usr/bin/env python3
"""Open a YouTube video in the connected phone's default browser."""
import cgi
import json
import os
import re
import shlex
import subprocess
from urllib.parse import parse_qs, urlsplit


ADB = os.environ.get("ADB", "adb")
PHONE = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")


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
    url = video_url(cgi.FieldStorage().getfirst("url", "").strip())
    if not url:
        respond({"ok": False, "error": "Enter a valid YouTube video link."}, "400 Bad Request")
        return
    try:
        browser = run_adb(
            "shell", "cmd", "package", "resolve-activity", "--brief",
            "-a", "android.intent.action.MAIN", "-c", "android.intent.category.APP_BROWSER"
        )
        if browser.returncode != 0:
            raise RuntimeError((browser.stderr or browser.stdout).strip() or "Browser lookup failed.")
        lines = browser.stdout.strip().splitlines()
        component = lines[-1].strip() if lines else ""
        if not COMPONENT.fullmatch(component) or component.startswith("android/"):
            raise RuntimeError("No default browser found on the phone. Set a default browser first.")
        result = run_adb(
            "shell", "am", "start", "-n", component,
            "-a", "android.intent.action.VIEW", "-d", shlex.quote(url)
        )
        if result.returncode != 0 or "Error:" in result.stdout or "Error:" in result.stderr:
            raise RuntimeError((result.stderr or result.stdout).strip() or "Browser launch failed.")
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        respond({"ok": False, "error": "Phone video failed: " + str(error)}, "502 Bad Gateway")
        return
    respond({"ok": True, "message": "Video opened in the phone browser. Press play if needed."})


if __name__ == "__main__":
    main()
