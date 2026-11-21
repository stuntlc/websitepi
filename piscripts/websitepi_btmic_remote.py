#!/usr/bin/env python3
"""Forced SSH command for the website's limited Pi 5 microphone access."""
import base64
import fcntl
import os
import re
import stat
import subprocess
import sys
import time


RECORDINGS = "/home/q/recorded"
UNITS = ("websitepi-btmic-stream.service", "websitepi-btmic-record.service")
NAME = re.compile(r"[A-Za-z0-9_.-]+\.(?:mp3|wav)")


def systemctl(*arguments):
    return subprocess.run(["systemctl", "--user", *arguments], capture_output=True,
                          text=True, timeout=15, check=True)


def listener_in_unit(unit):
    group = systemctl("show", "--property=ControlGroup", "--value", unit).stdout.strip()
    if not group:
        raise RuntimeError("Bluetooth service has no control group")
    listeners = subprocess.run(["ss", "-H", "-ltnp", "sport = :8000"],
                               capture_output=True, text=True, timeout=5, check=True).stdout
    for line in listeners.splitlines():
        if "127.0.0.1:8000" not in line:
            continue
        for pid in re.findall(r"pid=(\d+)", line):
            try:
                with open("/proc/" + pid + "/cgroup", encoding="ascii") as source:
                    paths = [entry.rstrip().split(":", 2)[-1] for entry in source]
            except FileNotFoundError:
                continue
            if any(path == group or path.startswith(group + "/") for path in paths):
                return True
    return False


def start(unit):
    state = systemctl("show", "--property=ActiveState", "--value", unit).stdout.strip()
    if state == "active":
        if unit != UNITS[0] or listener_in_unit(unit):
            return
        raise RuntimeError("Bluetooth stream service is active but its listener is unavailable")
    if state not in ("inactive", "failed"):
        raise RuntimeError("Bluetooth service is busy: " + state)
    systemctl("start", unit)
    try:
        if unit == UNITS[0]:
            for _ in range(50):
                if listener_in_unit(unit):
                    return
                try:
                    systemctl("is-active", "--quiet", unit)
                except subprocess.CalledProcessError as error:
                    raise RuntimeError("Bluetooth stream failed; check the Pi 5 user service log") from error
                time.sleep(0.1)
            raise RuntimeError("Bluetooth audio listener did not become ready")
        time.sleep(1)
        systemctl("is-active", "--quiet", unit)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        try:
            systemctl("stop", unit)
        except (OSError, subprocess.SubprocessError) as stop_error:
            raise RuntimeError("Bluetooth start failed and service could not be stopped: " + str(stop_error)) from error
        raise


def send_recording(name):
    if not NAME.fullmatch(name):
        raise ValueError("Invalid recording name")
    try:
        fd = os.open(os.path.join(RECORDINGS, name), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        print("BTMIC_FILE_NOTFOUND")
        return
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Recording is not a regular file")
        base64.encode(source, sys.stdout.buffer)


def main(command):
    if command in ("websitepi-btmic stream-start", "websitepi-btmic record-start", "websitepi-btmic stop"):
        runtime = os.environ.get("XDG_RUNTIME_DIR", "")
        if runtime != "/run/user/" + str(os.getuid()):
            raise RuntimeError("Pi 5 user runtime directory is unavailable")
        fd = os.open(os.path.join(runtime, "websitepi-btmic.lock"),
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if command == "websitepi-btmic stop":
                systemctl("stop", *UNITS)
            else:
                start(UNITS[0] if command.endswith("stream-start") else UNITS[1])
    elif command == "websitepi-btmic list":
        try:
            with os.scandir(RECORDINGS) as entries:
                names = sorted(entry.name for entry in entries if NAME.fullmatch(entry.name)
                               and entry.is_file(follow_symlinks=False))
        except FileNotFoundError:
            names = []
        print("\n".join(names))
    elif command == "websitepi-btmic stream":
        os.execvp("curl", ["curl", "--fail", "--silent", "--show-error", "--no-buffer",
                           "--connect-timeout", "8", "http://127.0.0.1:8000/live.mp3"])
    elif command.startswith("websitepi-btmic file "):
        send_recording(command[len("websitepi-btmic file "):])
    else:
        raise ValueError("Command not permitted")


if __name__ == "__main__":
    try:
        main(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Bluetooth operation failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
