"""Client-certificate and trusted-MAC gate for protected controls."""
import json
import os
import re
from urllib.parse import urlsplit

from websitepi_paths import log_directory


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRUST_PATH = os.path.join(log_directory(ROOT), "security-trust.json")
PROTECTED_PATH = "/etc/websitepi-sec/protected-macs.json"
CLIENTS_PATH = "/etc/websitepi-sec/client-certificates.json"
FINGERPRINT = re.compile(r"[0-9a-f]{64}")
MAC = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


def trusted_devices():
    trusted = set()
    for path in (TRUST_PATH, PROTECTED_PATH):
        with open(path, encoding="utf-8") as handle:
            devices = json.load(handle)
        if not isinstance(devices, list) or any(not isinstance(mac, str) or not MAC.fullmatch(mac) for mac in devices):
            raise ValueError("Invalid trusted-device inventory.")
        trusted.update(devices)
    return trusted


def peer_mac(address):
    with open("/proc/net/arp", encoding="ascii") as handle:
        for line in handle:
            fields = line.split()
            if len(fields) >= 6 and fields[0] == address and fields[5] == "eth0":
                try:
                    complete = int(fields[2], 16) & 2
                except ValueError:
                    continue
                mac = fields[3].upper()
                if complete and MAC.fullmatch(mac):
                    return mac
    return None


def same_origin(environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("HTTP_SEC_FETCH_SITE") == "cross-site":
        return False
    origin = environ.get("HTTP_ORIGIN")
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        scheme = "https" if environ.get("WEBSITEPI_SEC_TLS") == "1" else "http"
        return parsed.scheme == scheme and parsed.netloc.lower() == environ.get("HTTP_HOST", "").lower()
    except ValueError:
        return False


def current_mac(environ=None):
    environ = os.environ if environ is None else environ
    mac = peer_mac(environ.get("REMOTE_ADDR", ""))
    return mac if mac and mac in trusted_devices() else None


def authorized(environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("WEBSITEPI_SEC_TLS") != "1":
        return False
    fingerprint = environ.get("WEBSITEPI_SEC_CLIENT_SHA256", "")
    if not FINGERPRINT.fullmatch(fingerprint):
        return False
    mac = current_mac(environ)
    if not mac:
        return False
    with open(CLIENTS_PATH, encoding="utf-8") as handle:
        clients = json.load(handle)
    if not isinstance(clients, dict) or any(
        not isinstance(key, str) or not FINGERPRINT.fullmatch(key) or
        not isinstance(value, str) or not MAC.fullmatch(value)
        for key, value in clients.items()
    ):
        raise ValueError("Invalid client-certificate inventory.")
    return clients.get(fingerprint) == mac
