"""Tests for trusted client certificates and trusted MAC addresses."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cgi-bin"))
import security_access


class SecurityAccessTests(unittest.TestCase):
    def test_trust_inventory_uses_the_configured_state_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "security-trust.json").write_text('["02:11:22:33:44:55"]', encoding="utf-8")
            protected = path / "protected.json"
            protected.write_text("[]", encoding="utf-8")
            env = dict(os.environ, WEBSITEPI_LOG_DIR=directory)
            code = ("import sys; sys.path.insert(0, sys.argv[1]); import security_access as access; "
                    "access.PROTECTED_PATH = sys.argv[2]; print(','.join(access.trusted_devices()))")
            result = subprocess.run([sys.executable, "-c", code,
                                     str(Path(__file__).resolve().parents[1] / "cgi-bin"), str(protected)],
                                    capture_output=True, text=True, env=env, check=True)
            self.assertEqual(result.stdout.strip(), "02:11:22:33:44:55")
            env["WEBSITEPI_LOG_DIR"] = "relative"
            result = subprocess.run([sys.executable, "-c", code,
                                     str(Path(__file__).resolve().parents[1] / "cgi-bin"), str(protected)],
                                    capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("WEBSITEPI_LOG_DIR must be an absolute path", result.stderr)

    def test_https_origin_requires_matching_scheme_and_host(self):
        environ = {"WEBSITEPI_SEC_TLS": "1", "HTTP_HOST": "pi.local:8443"}
        self.assertTrue(security_access.same_origin(dict(environ, HTTP_ORIGIN="https://pi.local:8443")))
        self.assertFalse(security_access.same_origin(dict(environ, HTTP_ORIGIN="http://pi.local:8443")))
        self.assertFalse(security_access.same_origin(dict(environ, HTTP_ORIGIN="https://other.local:8443")))
        self.assertFalse(security_access.same_origin(dict(environ, HTTP_SEC_FETCH_SITE="cross-site")))

    def test_certificate_must_match_the_trusted_device_and_https(self):
        fingerprint = "a" * 64
        mac = "02:11:22:33:44:55"
        environ = {"WEBSITEPI_SEC_TLS": "1", "WEBSITEPI_SEC_CLIENT_SHA256": fingerprint}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "clients.json")
            Path(path).write_text(json.dumps({fingerprint: mac}), encoding="utf-8")
            with mock.patch.object(security_access, "CLIENTS_PATH", path), \
                    mock.patch.object(security_access, "current_mac", return_value=mac) as current:
                self.assertTrue(security_access.authorized(environ))
                self.assertFalse(security_access.authorized(dict(environ, WEBSITEPI_SEC_TLS="0")))
                self.assertFalse(security_access.authorized(dict(environ, WEBSITEPI_SEC_CLIENT_SHA256="b" * 64)))
                current.return_value = "02:11:22:33:44:66"
                self.assertFalse(security_access.authorized(environ))
                current.return_value = None
                self.assertFalse(security_access.authorized(environ))

    def test_invalid_or_missing_certificate_policy_fails_closed(self):
        environ = {"WEBSITEPI_SEC_TLS": "1", "WEBSITEPI_SEC_CLIENT_SHA256": "a" * 64}
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(security_access, "current_mac", return_value="02:11:22:33:44:55"):
            path = os.path.join(directory, "clients.json")
            with mock.patch.object(security_access, "CLIENTS_PATH", path):
                with self.assertRaises(FileNotFoundError):
                    security_access.authorized(environ)
                Path(path).write_text('{"invalid": "invalid"}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    security_access.authorized(environ)
