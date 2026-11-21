#!/usr/bin/env python3
"""Opt-in, memory-only inspection of Wi-Fi traffic routed through the Pi."""
import collections
import ipaddress
import json
import os
import select
import socket
import stat
import struct
import threading
import time

import maxminddb
from realtek_wifi import read_wifi_counters


SOCKET_PATH = "/run/websitepi-inspect/control.sock"
GEOIP_PATH = "/var/lib/websitepi-sec/dbip-country-lite.mmdb"
MAX_EVENTS = 300


def decode_frame(frame):
    if len(frame) < 14:
        return None
    dst_mac = ":".join("%02X" % byte for byte in frame[:6])
    src_mac = ":".join("%02X" % byte for byte in frame[6:12])
    ether_type = struct.unpack_from("!H", frame, 12)[0]
    offset = 14
    if ether_type in (0x8100, 0x88A8):
        if len(frame) < 18:
            return None
        ether_type = struct.unpack_from("!H", frame, 16)[0]
        offset = 18
    if ether_type != 0x0800 or len(frame) < offset + 20:
        return None
    header_len = (frame[offset] & 15) * 4
    total_len = struct.unpack_from("!H", frame, offset + 2)[0]
    fragments = struct.unpack_from("!H", frame, offset + 6)[0]
    if frame[offset] >> 4 != 4 or header_len < 20 or total_len < header_len or fragments & 0x3FFF:
        return None
    if len(frame) < offset + total_len:
        return None
    return {
        "src_mac": src_mac, "dst_mac": dst_mac,
        "src": socket.inet_ntoa(frame[offset + 12:offset + 16]),
        "dst": socket.inet_ntoa(frame[offset + 16:offset + 20]),
        "protocol": frame[offset + 9],
        "payload": frame[offset + header_len:offset + total_len],
    }


def dns_name(data, offset):
    labels = []
    seen = set()
    end = None
    while True:
        if offset >= len(data) or offset in seen or len(seen) > 128:
            raise ValueError("Invalid DNS name")
        seen.add(offset)
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Truncated DNS pointer")
            if end is None:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
        elif length & 0xC0:
            raise ValueError("Invalid DNS label")
        elif length == 0:
            if end is None:
                end = offset + 1
            name = ".".join(labels)
            if len(name) > 253:
                raise ValueError("DNS name too long")
            return name, end
        else:
            offset += 1
            if offset + length > len(data):
                raise ValueError("Truncated DNS label")
            labels.append(data[offset:offset + length].decode("ascii"))
            offset += length


def parse_dns(data):
    if len(data) < 12:
        raise ValueError("Truncated DNS header")
    ident, flags, questions, answers, _, _ = struct.unpack_from("!6H", data)
    if questions != 1 or answers > 128:
        raise ValueError("Unsupported DNS message")
    name, offset = dns_name(data, 12)
    if offset + 4 > len(data) or not name:
        raise ValueError("Invalid DNS question")
    offset += 4
    addresses = []
    for _ in range(answers):
        _, offset = dns_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("Truncated DNS answer")
        record_type, record_class, _, length = struct.unpack_from("!HHIH", data, offset)
        offset += 10
        if offset + length > len(data):
            raise ValueError("Truncated DNS record")
        if record_class == 1 and (record_type, length) in ((1, 4), (28, 16)):
            family = socket.AF_INET if record_type == 1 else socket.AF_INET6
            addresses.append(socket.inet_ntop(family, data[offset:offset + length]))
        offset += length
    return ident, bool(flags & 0x8000), name, addresses


class Inspector:
    def __init__(self):
        self.active = False
        self.capture = None
        self.geo = None
        self.events = collections.deque(maxlen=MAX_EVENTS)
        self.pending = {}
        self.seen = collections.OrderedDict()
        self.lock = threading.Lock()
        self.stations = set()
        self.station_error = ""
        self.refreshing = False
        self.refresh_at = 0
        self.station_expires = 0
        self.generation = 0

    def start(self):
        if self.active:
            return
        geo = maxminddb.open_database(GEOIP_PATH)
        try:
            capture = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
            capture.bind(("eth0", 0))
            capture.setblocking(False)
        except OSError:
            geo.close()
            raise
        self.geo, self.capture = geo, capture
        self.active = True
        self.generation += 1
        self.refresh_at = 0
        self.station_error = "Waiting for Wi-Fi association data."

    def stop(self):
        self.active = False
        self.generation += 1
        if self.capture:
            self.capture.close()
        if self.geo:
            self.geo.close()
        self.capture = self.geo = None
        self.events.clear()
        self.pending.clear()
        self.seen.clear()
        with self.lock:
            self.stations.clear()
            self.station_error = ""
        self.refresh_at = 0
        self.station_expires = 0

    def refresh_stations(self):
        with self.lock:
            if self.active and self.station_expires and time.monotonic() >= self.station_expires:
                self.stations.clear()
                self.station_error = "Wi-Fi association data is stale."
                self.station_expires = 0
        if not self.active or self.refreshing or time.monotonic() < self.refresh_at:
            return
        self.refreshing = True
        generation = self.generation

        def worker():
            try:
                result = read_wifi_counters()
            except (OSError, RuntimeError, ValueError) as error:
                result = {"ok": False, "error": str(error)}
            with self.lock:
                if self.active and generation == self.generation:
                    self.stations = {item["mac"].upper() for item in result["stations"]} if result["ok"] else set()
                    self.station_error = "" if result["ok"] else result["error"]
                    self.refresh_at = time.monotonic() + 30
                    self.station_expires = time.monotonic() + 45 if result["ok"] else 0
                self.refreshing = False

        threading.Thread(target=worker, daemon=True).start()

    def country(self, address):
        if not ipaddress.ip_address(address).is_global:
            return "Not public"
        result = self.geo.get(address) or {}
        country = result.get("country") or {}
        return (country.get("names") or {}).get("en") or country.get("iso_code") or "Unknown"

    def record(self, mac, kind, **fields):
        self.events.append({"time": int(time.time()), "mac": mac, "kind": kind, **fields})

    def packet(self, frame):
        packet = decode_frame(frame)
        if not packet:
            return
        with self.lock:
            stations = self.stations.copy()
        outgoing = packet["src_mac"] in stations
        incoming = packet["dst_mac"] in stations
        if outgoing == incoming:
            return
        mac = packet["src_mac"] if outgoing else packet["dst_mac"]
        client = packet["src"] if outgoing else packet["dst"]
        remote = packet["dst"] if outgoing else packet["src"]
        if not ipaddress.ip_address(remote).is_global:
            return
        protocol = packet["protocol"]
        payload = packet["payload"]
        if protocol not in (6, 17) or len(payload) < (20 if protocol == 6 else 8):
            return
        source_port, dest_port = struct.unpack_from("!HH", payload)
        remote_port = dest_port if outgoing else source_port
        if outgoing:
            key = (mac, remote, protocol, remote_port)
            if key not in self.seen:
                self.seen[key] = None
                if len(self.seen) > 1000:
                    self.seen.popitem(last=False)
                self.record(mac, "destination", ip=remote, country=self.country(remote),
                            protocol="TCP" if protocol == 6 else "UDP", port=remote_port)
        if protocol != 17 or (dest_port if outgoing else source_port) != 53:
            return
        udp_length = struct.unpack_from("!H", payload, 4)[0]
        if udp_length < 8 or udp_length > len(payload):
            return
        try:
            ident, response, name, addresses = parse_dns(payload[8:udp_length])
        except (ValueError, UnicodeDecodeError, struct.error):
            return
        key = (mac, client, remote, source_port if outgoing else dest_port, ident)
        now = time.monotonic()
        if outgoing and not response:
            if len(self.pending) >= 1024:
                self.pending.clear()
            self.pending[key] = (name.lower(), now)
            self.record(mac, "dns", domain=name)
        elif incoming and response:
            query = self.pending.pop(key, None)
            if not query or now - query[1] > 30 or query[0] != name.lower():
                return
            for address in addresses[:32]:
                self.record(mac, "answer", domain=name, ip=address, country=self.country(address))

    def status(self):
        with self.lock:
            error = self.station_error
            station_count = len(self.stations)
        return {"ok": True, "active": self.active, "station_error": error,
                "stations": station_count, "events": list(self.events)}


def main():
    inspector = Inspector()
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o750, exist_ok=True)
    if os.path.lexists(SOCKET_PATH):
        if not stat.S_ISSOCK(os.lstat(SOCKET_PATH).st_mode):
            raise RuntimeError("Inspection socket path is not a socket")
        os.unlink(SOCKET_PATH)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o660)
    server.listen(5)
    try:
        while True:
            inspector.refresh_stations()
            readers = [server]
            if inspector.capture:
                readers.append(inspector.capture)
            readable, _, _ = select.select(readers, [], [], 0.5)
            if server in readable:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(2)
                    try:
                        request = connection.recv(1024).decode("ascii").strip()
                        if request == "start":
                            inspector.start()
                        elif request == "stop":
                            inspector.stop()
                        elif request != "status":
                            raise ValueError("Invalid inspection request")
                        response = inspector.status()
                    except (OSError, ValueError, RuntimeError, maxminddb.InvalidDatabaseError) as error:
                        response = {"ok": False, "error": str(error)}
                    connection.sendall(json.dumps(response).encode("utf-8") + b"\n")
            if inspector.capture and inspector.capture in readable:
                try:
                    inspector.packet(inspector.capture.recv(65535))
                except (OSError, ValueError, maxminddb.InvalidDatabaseError) as error:
                    inspector.stop()
                    inspector.station_error = "Inspection stopped: " + str(error)
    finally:
        inspector.stop()
        server.close()
        os.unlink(SOCKET_PATH)


if __name__ == "__main__":
    main()
