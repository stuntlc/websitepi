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
eth0_mac=$(ip -o link show eth0 2>/dev/null | awk '{for (field = 1; field <= NF; field++) if ($field == "link/ether") { print $(field + 1); exit }}')
eth0_ip=$(ip -o -4 addr show dev eth0 2>/dev/null | awk '{print $4; exit}')
usb0_peer=$(ip route show dev usb0 2>/dev/null | awk '/via/ {print $3; exit}')
eth0_gateway=$(ip route show default dev eth0 2>/dev/null | awk 'NR == 1 { print $3; exit }')
default_route=$(ip route show default 2>/dev/null | awk 'NR == 1 { print $3 "|" $5; exit }')

phone_neigh=$(adb shell ip neigh 2>/dev/null | tr -d '\r')
phone_ifconfig=$(adb shell ifconfig 2>/dev/null | tr -d '\r')

SCAN_DATA="$scan_data" SCAN_SOURCE="${scan_source:-none}" USB0_MAC="$usb0_mac" USB0_IP="$usb0_ip" USB0_PEER="$usb0_peer" ETH0_MAC="$eth0_mac" ETH0_IP="$eth0_ip" ETH0_GATEWAY="$eth0_gateway" DEFAULT_ROUTE="$default_route" PHONE_NEIGH="$phone_neigh" PHONE_IFCONFIG="$phone_ifconfig" python3 - <<'PY'
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

def parse_phone_interfaces(text):
    interfaces = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^([A-Za-z0-9_.-]+)\s+Link encap", line.strip())
        if header:
            current = header.group(1)
            interfaces[current] = {}
            continue
        if not current:
            continue
        ip_match = re.search(r"inet addr:([0-9.]+)", line)
        mac_match = re.search(r"HWaddr\s+([0-9A-Fa-f:]{17})", line)
        if ip_match:
            interfaces[current]["ip"] = ip_match.group(1)
        if mac_match:
            interfaces[current]["mac"] = mac_match.group(1).upper()
    return interfaces

def parse_legacy_interfaces(text):
    interfaces = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^([A-Za-z0-9_.:-]+)\s+Link encap", line.strip())
        if header:
            current = header.group(1)
            interfaces[current] = {}
            continue
        if not current:
            continue
        ip_match = re.search(r"inet addr:([0-9.]+)", line)
        mac_match = re.search(r"HWaddr\s+([0-9A-Fa-f:]{17})", line)
        if ip_match:
            interfaces[current]["ip"] = ip_match.group(1)
        if mac_match:
            interfaces[current]["mac"] = mac_match.group(1).upper()
    return interfaces

def parse_modem_neighbors(text):
    neighbors = []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+\S+\s+([0-9A-Fa-f:]{17})\s+.*\s+(\S+)\s*$", line)
        if match:
            neighbors.append({"ip": match.group(1), "mac": match.group(2).upper(), "interface": match.group(3)})
    return neighbors

def read_modem(host="10.0.0.1", port=8888):
    import socket
    import time
    try:
        connection = socket.create_connection((host, port), timeout=4)
    except OSError as error:
        return "", "unreachable (%s)" % type(error).__name__
    chunks = []
    try:
        connection.settimeout(1.5)
        for command in (b"arp -n\n", b"ifconfig eth0\n", b"exit\n"):
            try:
                connection.sendall(command)
            except OSError:
                break
            deadline = time.time() + 2
            while time.time() < deadline:
                try:
                    data = connection.recv(4096)
                except socket.timeout:
                    break
                except OSError:
                    data = b""
                if not data:
                    break
                chunks.append(data)
    finally:
        connection.close()
    raw = re.sub(rb"\xff[\xfb-\xfe].|\xff.", b"", b"".join(chunks))
    text = raw.decode("latin-1").replace("\r", "")
    return text, ("connected" if text.strip() else "no data")

modem_text, modem_status = read_modem()
os.environ["MODEM_OUTPUT"] = modem_text
os.environ["MODEM_STATUS"] = modem_status

phone_interfaces = parse_phone_interfaces(os.environ.get("PHONE_IFCONFIG", ""))
modem_interfaces = parse_legacy_interfaces(os.environ.get("MODEM_OUTPUT", ""))
modem_neighbors = parse_modem_neighbors(os.environ.get("MODEM_OUTPUT", ""))
for neighbor in modem_neighbors:
    neighbor["oui"] = neighbor["mac"].replace(":", "")[:6]
    neighbor["vendor"] = vendors.get(neighbor["oui"], "Unknown vendor")
phone_neighbors = []
for line in os.environ.get("PHONE_NEIGH", "").splitlines():
    fields = line.split()
    if len(fields) >= 5 and fields[0].count(".") == 3 and "lladdr" in fields:
        mac_index = fields.index("lladdr") + 1
        if mac_index < len(fields):
            phone_neighbors.append({"ip": fields[0], "mac": fields[mac_index].upper(), "interface": fields[2], "state": fields[-1]})

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
    vendor = vendor.strip()
    if vendor.startswith("(Unknown") or vendor.lower() == "unknown":
        vendor = ""
    vendor = vendor or vendors.get(oui, "Unknown vendor")
    role = "Pi 5 / static Ethernet" if ip == "10.0.0.50" else ""
    devices.append({"ip": ip, "mac": mac, "oui": oui, "vendor": vendor, "device_type": device_type(vendor), "role": role})

devices.sort(key=lambda device: tuple(int(part) for part in device["ip"].split(".")))

import subprocess

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(os.environ.get("SCRIPT_FILENAME") or "/home/q/websd/cgi-bin/oui.cgi")))
data_dir = os.path.join(root_dir, "logs")
config_path = os.path.join(data_dir, "oui-config.json")
known_path = os.path.join(data_dir, "oui-known.json")
alerts_path = os.path.join(data_dir, "oui-alerts.log")

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default

def save_json(path, value):
    os.makedirs(data_dir, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1)
    os.replace(temporary, path)

dhcp_names = {}
for lease_file in ("/var/lib/misc/dnsmasq.leases", "/var/lib/dhcp/dhcpd.leases"):
    try:
        with open(lease_file, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                fields = line.split()
                if len(fields) >= 4 and fields[1].count(":") == 5:
                    dhcp_names[fields[1].upper()] = fields[3] if fields[3] != "*" else ""
    except OSError:
        continue

now_iso = datetime.now(timezone.utc).isoformat()
config = load_json(config_path, {})
labels = load_json(os.path.join(data_dir, "oui-labels.json"), {})

import shutil
from concurrent.futures import ThreadPoolExecutor

names_path = os.path.join(data_dir, "oui-names.json")
name_cache = load_json(names_path, {})

def run_tool(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""

def lookup_names(ip):
    result = {"hostname": "", "workgroup": "", "source": ""}
    if shutil.which("nmblookup"):
        for line in run_tool(["nmblookup", "-A", ip]).splitlines():
            match = re.match(r"^\s+(\S+)\s+<00>\s+-\s+(<GROUP>\s+)?", line)
            if match:
                if match.group(2):
                    result["workgroup"] = result["workgroup"] or match.group(1)
                elif not result["hostname"]:
                    result["hostname"], result["source"] = match.group(1), "NetBIOS"
    if not result["hostname"] and shutil.which("avahi-resolve-address"):
        fields = run_tool(["avahi-resolve-address", ip]).split()
        if len(fields) >= 2:
            result["hostname"], result["source"] = fields[1].rstrip("."), "mDNS"
    if not result["hostname"]:
        fields = run_tool(["getent", "hosts", ip]).split()
        if len(fields) >= 2:
            result["hostname"], result["source"] = fields[1], "DNS"
    return result

# Cache per MAC: refresh found names hourly, retry misses every 10 minutes.
stale = []
now_ts = datetime.now(timezone.utc).timestamp()
for device in devices:
    cached = name_cache.get(device["mac"])
    max_age = 3600 if cached and cached.get("hostname") else 600
    if not cached or now_ts - cached.get("ts", 0) > max_age or cached.get("ip") != device["ip"]:
        stale.append(device)
with ThreadPoolExecutor(max_workers=8) as pool:
    for device, found in zip(stale[:16], pool.map(lookup_names, [d["ip"] for d in stale[:16]])):
        found.update({"ts": now_ts, "ip": device["ip"]})
        name_cache[device["mac"]] = found
if stale:
    try:
        save_json(names_path, name_cache)
    except OSError:
        pass
known = load_json(known_path, None)
baseline = known is None
known = known or {}
new_devices = []
for device in devices:
    first_digit = int(device["mac"][1], 16)
    device["randomized_mac"] = bool(first_digit & 0x2)
    found = name_cache.get(device["mac"], {})
    device["hostname"] = dhcp_names.get(device["mac"]) or found.get("hostname", "")
    device["hostname_source"] = "DHCP" if dhcp_names.get(device["mac"]) else found.get("source", "")
    device["workgroup"] = found.get("workgroup", "")
    label = labels.get(device["mac"], "")
    device["label"] = label
    if device["randomized_mac"] and device["vendor"] == "Unknown vendor":
        device["vendor"] = "Private/randomized MAC"
    entry = known.get(device["mac"])
    if entry is None:
        entry = {"first_seen": now_iso, "ip": device["ip"], "vendor": device["vendor"], "alerted": baseline}
        known[device["mac"]] = entry
    # Only unnamed devices alert, once each; naming a device marks it as yours.
    if not label and not entry.get("alerted"):
        entry["alerted"] = True
        new_devices.append(device)
    entry["last_seen"] = now_iso
    entry["ip"] = device["ip"]
    device["first_seen"] = entry["first_seen"]
    device["last_seen"] = entry["last_seen"]
    device["new"] = device in new_devices
    device["unnamed"] = not label

sms_results = []
if new_devices:
    number = config.get("sms_number", "")
    for device in new_devices:
        description = "%s %s %s %s%s" % (
            device["ip"], device["mac"], device["label"] or device["vendor"], device["device_type"],
            " (randomized MAC)" if device["randomized_mac"] else "")
        description = re.sub(r"[^\x20-\x7e]", "?", description)
        try:
            with open(alerts_path, "a", encoding="utf-8") as handle:
                handle.write("%s NEW %s\n" % (now_iso, description))
        except OSError:
            pass
        if config.get("sms_enabled") and re.fullmatch(r"\+[1-9]\d{6,14}", number or ""):
            try:
                result = subprocess.run(["/bin/bash", os.path.join(root_dir, "piscripts", "smsend"), number, "New unknown device on network: " + description],
                                        capture_output=True, text=True, timeout=45)
                sms_results.append({"ip": device["ip"], "ok": result.returncode == 0})
            except (subprocess.TimeoutExpired, OSError):
                sms_results.append({"ip": device["ip"], "ok": False})
try:
    save_json(known_path, known)
except OSError:
    pass

recent_alerts = []
try:
    with open(alerts_path, encoding="utf-8") as handle:
        recent_alerts = [line.strip() for line in handle.readlines()[-10:]]
except OSError:
    pass

print(json.dumps({
    "new_devices": new_devices,
    "sms_results": sms_results,
    "recent_alerts": recent_alerts,
    "config": {"sms_number": config.get("sms_number", ""), "sms_enabled": bool(config.get("sms_enabled"))},
    "scanned_at": datetime.now(timezone.utc).isoformat(),
    "source": os.environ.get("SCAN_SOURCE", "arp"),
    "oui_database": database_files[0] if database_files else "none",
    "eth0": {"ip": os.environ.get("ETH0_IP", ""), "mac": os.environ.get("ETH0_MAC", ""), "gateway": os.environ.get("ETH0_GATEWAY", "")},
    "usb0": {"ip": os.environ.get("USB0_IP", ""), "mac": os.environ.get("USB0_MAC", ""), "peer": os.environ.get("USB0_PEER", "")},
    "phone": {"interfaces": phone_interfaces, "neighbors": phone_neighbors},
    "modem": {"interfaces": modem_interfaces, "neighbors": modem_neighbors, "reachable": bool(modem_interfaces or modem_neighbors), "status": os.environ.get("MODEM_STATUS", "unavailable")},
    "default_route": dict(zip(("gateway", "interface"), os.environ.get("DEFAULT_ROUTE", "|").split("|"))),
    "devices": devices,
}))
PY
