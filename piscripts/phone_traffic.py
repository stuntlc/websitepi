"""Read phone interface byte counters over ADB."""
import subprocess


def phone_traffic(interface):
    paths = ["/sys/class/net/%s/statistics/%s_bytes" % (interface, direction)
             for direction in ("rx", "tx")]
    try:
        result = subprocess.run(["adb", "shell", "cat"] + paths, capture_output=True, text=True, timeout=8)
        if result.returncode:
            return {"error": (result.stderr or result.stdout).strip() or "ADB counter read failed"}
        values = result.stdout.split()
        if len(values) != 2 or not all(value.isdigit() for value in values):
            return {"error": "Invalid counter data for " + interface}
        return {"rx_bytes": int(values[0]), "tx_bytes": int(values[1])}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}
