#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
import urllib.request

MODEM = "http://192.168.100.254"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENABLE_SCRIPT = os.path.join(ROOT, "piscripts", "realtek")

def fetch(page):
    try:
        with urllib.request.urlopen(MODEM + "/" + page, timeout=5) as response:
            return response.read().decode("latin-1")
    except Exception:
        return None

def rows(html, columns):
    result = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) == len(columns) and re.fullmatch(r"[0-9A-Fa-f:]{17}|[0-9A-Fa-f]{12}", cells[columns.index("mac")] if "mac" in columns else ""):
            result.append(dict(zip(columns, cells)))
    return result

def norm(mac):
    mac = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    return ":".join(mac[i:i + 2] for i in range(0, 12, 2))

enable_log = ""
enabled_now = False
if fetch("wlstatbl.asp") is None:
    # Modem web server is down: start it over the serial console (needs permission on /dev/ttyUSB0).
    try:
        result = subprocess.run(["/bin/sh", ENABLE_SCRIPT], capture_output=True, text=True, timeout=20)
        enable_log = (result.stdout + result.stderr).strip()
        enabled_now = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        enable_log = str(error)
    for _ in range(10):
        time.sleep(1)
        if fetch("wlstatbl.asp") is not None:
            break

wifi_html = fetch("wlstatbl.asp")
dhcp_html = fetch("dhcptbl.asp")
log_html = fetch("syslog.asp")

wifi = rows(wifi_html, ["mac", "ssid", "mode", "tx_packets", "rx_packets", "tx_rate", "power_saving", "expired"])
dhcp = []
for row in re.findall(r"<tr[^>]*>(.*?)</tr>", dhcp_html or "", re.S | re.I):
    cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
    if len(cells) == 3 and re.fullmatch(r"\d+(?:\.\d+){3}", cells[0]):
        dhcp.append({"ip": cells[0], "mac": cells[1], "expires": cells[2]})
for row in wifi:
    row["mac"] = norm(row["mac"])
for row in dhcp:
    row["mac"] = norm(row["mac"])
wifi_macs = {row["mac"] for row in wifi}
for row in dhcp:
    row["wifi"] = row["mac"] in wifi_macs

log_match = re.search(r"<textarea[^>]*>(.*?)</textarea>", log_html or "", re.S | re.I)
log = [line.strip() for line in (log_match.group(1).splitlines() if log_match else []) if line.strip()][-50:]

print("Content-Type: application/json\r\n")
print(json.dumps({
    "reachable": wifi_html is not None,
    "enabled_now": enabled_now,
    "enable_log": enable_log,
    "wifi_stations": wifi,
    "dhcp_leases": dhcp,
    "syslog": log,
}))
