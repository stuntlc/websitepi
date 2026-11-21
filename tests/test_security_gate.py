"""Verify that insecure CGI requests cannot bypass the access gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "cgi-bin" / "security_gate.py"


class SecurityGateTests(unittest.TestCase):
    def test_http_and_spoofed_tls_header_are_denied(self):
        env = dict(os.environ, REQUEST_METHOD="GET", HTTP_WEBSITEPI_SEC_TLS="1")
        env.pop("WEBSITEPI_SEC_TLS", None)
        result = subprocess.run([sys.executable, str(SCRIPT), "json"], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("403 Forbidden", result.stdout)
        self.assertFalse(json.loads(result.stdout.split("\n\n", 1)[1])["ok"])
