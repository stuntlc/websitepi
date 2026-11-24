"""Read the dashboard's device states without changing the hardware."""
import os
import re
import shutil
import subprocess
import sys


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=True)
    if result.stderr.strip():
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def relay_state():
    gpio = shutil.which("pinctrl") or shutil.which("raspi-gpio")
    if not gpio:
        raise RuntimeError("GPIO status command unavailable.")
    output = command(gpio, "get", "12")
    if os.path.basename(gpio) == "pinctrl":
        match = re.search(r"\b12:\s*(?:op|ip)\b[^\n|]*\|\s*(hi|lo)\b", output)
        if not match:
            raise ValueError("Relay GPIO level unavailable.")
        return match.group(1) == "hi"
    match = re.search(r"\bGPIO 12:\s*level=([01])\s+fsel=[01]\s+func=(?:INPUT|OUTPUT)\b", output)
    if not match:
        raise ValueError("Relay GPIO level unavailable.")
    return match.group(1) == "1"


def adb(*args):
    serial = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
    return command(os.environ.get("ADB", "adb"), *(["-s", serial] if serial else []), "shell", *args)


def flashlight_state():
    value = adb("cat", "/sys/class/leds/flashlight/brightness")
    if not value.isdecimal():
        raise ValueError("Invalid phone flashlight brightness.")
    return int(value) > 0


def fm_state():
    output = adb("dumpsys", "media.audio_policy")
    match = re.search(r"(?ms)^ Inputs \((\d+)\):\s*\n(.*?)(?=^ Total Effects\b)", output)
    if not match:
        raise ValueError("FM audio input status unavailable.")
    count = int(match.group(1))
    inputs = re.split(r"(?m)^  \d+\. Port ID:", match.group(2))[1:]
    if len(inputs) != count:
        raise ValueError("Invalid phone audio input status.")
    for entry in inputs:
        if "AUDIO_DEVICE_IN_FM_TUNER" not in entry:
            continue
        clients = re.split(r"(?m)^      \d+\. Port ID:", entry)[1:]
        for client in clients:
            if re.search(r"\bState: Active\b", client) and "AUDIO_SOURCE_FM_TUNER" in client:
                return True
    return False


def read_states():
    states = {}
    for name, reader in (("fm", fm_state), ("led", relay_state), ("flash", flashlight_state)):
        try:
            states[name] = {"on": reader(), "error": ""}
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print("Device status {}: {}".format(name, error), file=sys.stderr)
            states[name] = {"on": None, "error": str(error)}
    return states
