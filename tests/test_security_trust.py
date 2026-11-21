"""Tests for the non-enforcing trusted-device inventory."""
import importlib.machinery
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlencode


if os.name != "nt":
    path = Path(__file__).resolve().parents[1] / "cgi-bin" / "security-trust.cgi"
    sys.path.insert(0, str(path.parent))
    loader = importlib.machinery.SourceFileLoader("security_trust", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    security_trust = importlib.util.module_from_spec(spec)
    loader.exec_module(security_trust)


@unittest.skipIf(os.name == "nt", "The CGI uses Linux file locks")
class SecurityTrustTests(unittest.TestCase):
    def test_inventory_persists_additions_and_removals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trusted.json")
            protected = os.path.join(directory, "protected.json")
            Path(protected).write_text('["02:11:22:33:44:66"]', encoding="utf-8")
            mac = "02:11:22:33:44:55"
            with mock.patch.object(security_trust, "PROTECTED_PATH", protected):
                self.assertEqual(security_trust.read_trust(path), [])
                self.assertEqual(security_trust.update_trust(path, mac, "add"), [mac])
                self.assertEqual(security_trust.update_trust(path, mac, "add"), [mac])
                self.assertEqual(security_trust.read_trust(path), [mac])
                self.assertEqual(security_trust.update_trust(path, mac, "remove"), [])
                with self.assertRaises(PermissionError):
                    security_trust.update_trust(path, "02:11:22:33:44:66", "remove")
                os.remove(protected)
                with self.assertRaises(FileNotFoundError):
                    security_trust.update_trust(path, mac, "remove")

    def test_rejects_bad_addresses_and_corrupt_inventory(self):
        for mac in ("01:00:00:00:00:00", "00:00:00:00:00:00", "invalid"):
            self.assertFalse(security_trust.valid_mac(mac))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trusted.json")
            Path(path).write_text('["invalid"]', encoding="utf-8")
            with self.assertRaises(ValueError):
                security_trust.update_trust(path, "02:11:22:33:44:55", "add")
            self.assertEqual(Path(path).read_text(encoding="utf-8"), '["invalid"]')

    def test_post_and_cross_origin_rejection(self):
        body = urlencode({"mac": "02:11:22:33:44:55", "action": "add"})
        env = {"REQUEST_METHOD": "POST", "HTTP_HOST": "pi:8080",
               "CONTENT_TYPE": "application/x-www-form-urlencoded", "CONTENT_LENGTH": str(len(body))}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trusted.json")
            protected = os.path.join(directory, "protected.json")
            Path(protected).write_text("[]", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(security_trust, "PATH", path), \
                    mock.patch.object(security_trust, "PROTECTED_PATH", protected), \
                    mock.patch.object(security_trust, "authorized", return_value=True), \
                    mock.patch.dict(os.environ, dict(env, HTTP_ORIGIN="http://pi:8080"), clear=True), \
                    mock.patch("sys.stdin", io.StringIO(body)), contextlib.redirect_stdout(output):
                security_trust.main()
            self.assertEqual(json.loads(output.getvalue().split("\n\n", 1)[1])["devices"], ["02:11:22:33:44:55"])
            output = io.StringIO()
            with mock.patch.object(security_trust, "PATH", path), \
                    mock.patch.dict(os.environ, dict(env, HTTP_ORIGIN="http://other"), clear=True), \
                    mock.patch("sys.stdin", io.StringIO(body)), contextlib.redirect_stdout(output):
                security_trust.main()
            self.assertIn("403 Forbidden", output.getvalue())
            self.assertEqual(security_trust.read_trust(path), ["02:11:22:33:44:55"])

    def test_untrusted_browser_cannot_read_or_change_inventory(self):
        body = urlencode({"mac": "02:11:22:33:44:55", "action": "add"})
        env = {"REQUEST_METHOD": "POST", "HTTP_HOST": "pi:8080",
               "CONTENT_TYPE": "application/x-www-form-urlencoded", "CONTENT_LENGTH": str(len(body))}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trusted.json")
            output = io.StringIO()
            with mock.patch.object(security_trust, "PATH", path), \
                    mock.patch.object(security_trust, "authorized", return_value=False), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch("sys.stdin", io.StringIO(body)), contextlib.redirect_stdout(output):
                security_trust.main()
            self.assertIn("Trusted client certificate and device required", output.getvalue())
            self.assertFalse(os.path.exists(path))
