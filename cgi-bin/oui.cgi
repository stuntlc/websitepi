#!/bin/bash
printf 'Content-Type: application/json\r\n\r\n'

if command -v arp-scan >/dev/null 2>&1; then
    scan_data=$(arp-scan --localnet 2>/dev/null | awk '/^[0-9]+\./ { vendor=$0; sub(/^[^ ]+[[:space:]]+[^ ]+[[:space:]]+/, "", vendor); print $1 "|" $2 "|" vendor }')
    scan_source="arp-scan"
fi
if [ -z "$scan_data" ] && command -v arp >/dev/null 2>&1; then
    scan_data=$(arp -n 2>/dev/null | awk 'NR > 1 && $1 ~ /^[0-9]+\./ && $3 ~ /:/ { print $1 "|" $3 "|" }')
    scan_source="arp"
fi
if [ -z "$scan_data" ] && command -v ip >/dev/null 2>&1; then
    scan_data=$(ip neigh show 2>/dev/null | awk '$1 ~ /^[0-9]+\./ { for (field = 1; field <= NF; field++) if ($field == "lladdr") { print $1 "|" $(field + 1) "|"; break } }')
    scan_source="ip-neigh"
fi

usb0_mac=$(ip -o link show usb0 2>/dev/null | awk '{for (field = 1; field <= NF; field++) if ($field == "link/ether") { print $(field + 1); exit }}')
usb0_ip=$(ip -o -4 addr show dev usb0 2>/dev/null | awk '{print $4; exit}')
default_route=$(ip route show default 2>/dev/null | awk 'NR == 1 { print $3 "|" $5; exit }')

SCAN_DATA="$scan_data" SCAN_SOURCE="${scan_source:-none}" USB0_MAC="$usb0_mac" USB0_IP="$usb0_ip" DEFAULT_ROUTE="$default_route" python3 - <<'PY'
import json
import os
import re
from datetime import datetime, timezone

oui_files = (
    "/usr/share/arp-scan/ieee-oui.txt",
    "/usr/share/ieee-data/oui.txt",
    "/usr/share/wireshark/manuf",
    "/usr/share/nmap/nmap-mac-prefixes",
)
vendors = {}
database_files = []
for filename in oui_files:
    try:
        loaded = False
        with open(filename, encoding="utf-8", errors="ignore") as oui_file:
            for line in oui_file:
                ieee_match = re.match(r"^\s*([0-9A-Fa-f]{6})\s+\(base 16\)\s+(.+?)\s*$", line)
                manuf_match = re.match(r"^\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){2}|[0-9A-Fa-f]{6})\s+(?:\([^)]*\)\s+)?(.+?)\s*$", line)
                match = ieee_match or manuf_match
                if match:
                    prefix = re.sub(r"[-:]", "", match.group(1)).upper()[:6]
                    vendors.setdefault(prefix, match.group(2).strip())
                    loaded = True
        if loaded:
            database_files.append(filename)
    except OSError:
        continue

devices = []
seen = set()

def device_type(vendor):
    name = vendor.lower()
    groups = (
        (("apple", "iphone", "ipad"), "Apple device"),
        (("samsung", "xiaomi", "huawei", "oneplus", "motorola"), "Android phone/tablet"),
        (("raspberry", "rasp pi"), "Raspberry Pi"),
        (("google", "nest"), "Google/Nest device"),
        (("amazon", "ring"), "Amazon/IoT device"),
        (("intel", "realtek", "broadcom", "mediatek"), "Network device"),
        (("microsoft", "dell", "lenovo", "hewlett", "hp", "asus"), "Computer"),
    )
    for names, label in groups:
        if any(name in vendor_name for vendor_name in names):
            return label
    return "Unknown device"

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
    oui = mac.replace(":", "")[:6]
    vendor = vendor.strip() or vendors.get(oui, "Unknown vendor")
    devices.append({"ip": ip, "mac": mac, "oui": oui, "vendor": vendor, "device_type": device_type(vendor)})

devices.sort(key=lambda device: tuple(int(part) for part in device["ip"].split(".")))
print(json.dumps({
    "scanned_at": datetime.now(timezone.utc).isoformat(),
    "source": os.environ.get("SCAN_SOURCE", "arp"),
    "oui_database": database_files[0] if database_files else "none",
    "usb0": {"ip": os.environ.get("USB0_IP", ""), "mac": os.environ.get("USB0_MAC", "")},
    "default_route": dict(zip(("gateway", "interface"), os.environ.get("DEFAULT_ROUTE", "|").split("|"))),
    "devices": devices,
}))
PY
