#!/bin/bash
printf 'Content-Type: application/json\r\n\r\n'

if command -v arp-scan >/dev/null 2>&1; then
    scan_data=$(arp-scan --localnet 2>/dev/null | awk '/^[0-9]+\./ { vendor=$0; sub(/^[^ ]+[[:space:]]+[^ ]+[[:space:]]+/, "", vendor); print $1 "|" $2 "|" vendor "|" "arp-scan" }')
    scan_source="arp-scan"
else
    scan_data=$(arp -n 2>/dev/null | awk 'NR > 1 && $1 ~ /^[0-9]+\./ && $3 ~ /:/ { print $1 "|" $3 "||arp" }')
    scan_source="arp"
fi

SCAN_DATA="$scan_data" SCAN_SOURCE="$scan_source" python3 - <<'PY'
import json
import os
import re
from datetime import datetime, timezone

oui_files = (
    "/usr/share/ieee-data/oui.txt",
    "/usr/share/wireshark/manuf",
    "/usr/share/nmap/nmap-mac-prefixes",
)
vendors = {}
for filename in oui_files:
    try:
        with open(filename, encoding="utf-8", errors="ignore") as oui_file:
            for line in oui_file:
                match = re.match(r"^\s*([0-9A-Fa-f]{2}[-:]?){3}\s+(?:\([^)]*\)\s+)?(.+?)\s*$", line)
                if match:
                    prefix = re.sub(r"[-:]", "", line.split()[0]).upper()[:6]
                    if prefix not in vendors:
                        vendors[prefix] = match.group(2).strip()
    except OSError:
        continue

devices = []
seen = set()
for row in os.environ.get("SCAN_DATA", "").splitlines():
    ip, separator, rest = row.partition("|")
    if not separator:
        continue
    mac, separator, vendor = rest.partition("|")
    if not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", ip) or not re.match(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$", mac):
        continue
    mac = mac.upper()
    if mac in seen:
        continue
    seen.add(mac)
    vendor = vendor.strip() or vendors.get(mac.replace(":", "")[:6], "Unknown vendor")
    devices.append({"ip": ip, "mac": mac, "vendor": vendor})

devices.sort(key=lambda device: tuple(int(part) for part in device["ip"].split(".")))
print(json.dumps({
    "scanned_at": datetime.now(timezone.utc).isoformat(),
    "source": os.environ.get("SCAN_SOURCE", "arp"),
    "devices": devices,
}))
PY
