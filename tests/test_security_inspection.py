"""Tests for memory-only Wi-Fi DNS and IP inspection."""
import socket
import struct
import sys
import types
from pathlib import Path
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piscripts"))
with mock.patch.dict(sys.modules, {"maxminddb": types.ModuleType("maxminddb")}):
    import security_inspection


def frame(src_mac, dst_mac, src, dst, payload, source_port=43000, dest_port=53):
    mac = lambda value: bytes.fromhex(value.replace(":", ""))
    udp = struct.pack("!HHHH", source_port, dest_port, len(payload) + 8, 0) + payload
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, len(udp) + 20, 1, 0, 64, 17, 0,
                         socket.inet_aton(src), socket.inet_aton(dst))
    return mac(dst_mac) + mac(src_mac) + b"\x08\x00" + header + udp


class Geo:
    def get(self, address):
        return {"country": {"names": {"en": "Example country"}}}

    def close(self):
        pass


class SecurityInspectionTests(unittest.TestCase):
    def test_station_read_failure_clears_the_association_list(self):
        inspector = security_inspection.Inspector()
        inspector.active = True
        inspector.stations = {"02:11:22:33:44:55"}
        with mock.patch.object(security_inspection, "read_wifi_counters", side_effect=OSError("serial unavailable")), \
                mock.patch.object(security_inspection.threading, "Thread") as thread:
            thread.side_effect = lambda target, daemon: mock.Mock(start=target)
            inspector.refresh_stations()
        self.assertEqual(inspector.stations, set())
        self.assertIn("serial unavailable", inspector.station_error)
        self.assertFalse(inspector.refreshing)

    def test_records_wifi_dns_and_destination_but_not_wired_traffic(self):
        inspector = security_inspection.Inspector()
        inspector.active = True
        inspector.geo = Geo()
        inspector.stations = {"02:11:22:33:44:55"}
        query = struct.pack("!6H", 42, 0x100, 1, 0, 0, 0) + b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
        wired = frame("02:11:22:33:44:66", "02:AA:BB:CC:DD:EE", "10.0.0.3", "8.8.8.8", query)
        wifi = frame("02:11:22:33:44:55", "02:AA:BB:CC:DD:EE", "10.0.0.2", "8.8.8.8", query)
        inspector.packet(wired)
        self.assertEqual(list(inspector.events), [])
        inspector.packet(wifi)
        self.assertEqual([event["kind"] for event in inspector.events], ["destination", "dns"])
        self.assertEqual(inspector.events[-1]["domain"], "example.com")
        inspector.stop()
        self.assertEqual(list(inspector.events), [])
        self.assertEqual(inspector.pending, {})

    def test_dns_answer_and_bad_compression(self):
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
        answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton("1.1.1.1")
        response = struct.pack("!6H", 42, 0x8180, 1, 1, 0, 0) + question + answer
        ident, is_response, name, addresses = security_inspection.parse_dns(response)
        self.assertEqual((ident, is_response, name, addresses), (42, True, "example.com", ["1.1.1.1"]))
        with self.assertRaises(ValueError):
            security_inspection.dns_name(b"\xc0\x00", 0)

    def test_only_matching_wifi_dns_answers_are_recorded(self):
        inspector = security_inspection.Inspector()
        inspector.active = True
        inspector.geo = Geo()
        inspector.stations = {"02:11:22:33:44:55"}
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
        query = struct.pack("!6H", 42, 0x100, 1, 0, 0, 0) + question
        answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton("1.1.1.1")
        response = struct.pack("!6H", 42, 0x8180, 1, 1, 0, 0) + question + answer
        inspector.packet(frame("02:AA:BB:CC:DD:EE", "02:11:22:33:44:55", "8.8.8.8", "10.0.0.2", response, 53, 43000))
        self.assertEqual(list(inspector.events), [])
        inspector.packet(frame("02:11:22:33:44:55", "02:AA:BB:CC:DD:EE", "10.0.0.2", "8.8.8.8", query))
        inspector.packet(frame("02:AA:BB:CC:DD:EE", "02:11:22:33:44:55", "8.8.8.8", "10.0.0.2", response, 53, 43000))
        self.assertEqual(inspector.events[-1]["kind"], "answer")
        self.assertEqual(inspector.events[-1]["ip"], "1.1.1.1")
