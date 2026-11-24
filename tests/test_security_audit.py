"""Tests for HTTPS access history and the deployment inventory."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cgi-bin"))
import security_audit


class SecurityAuditTests(unittest.TestCase):
    def test_records_and_prunes_history(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(security_audit, "AUDIT_PATH", str(Path(directory) / "audit.db")), \
                mock.patch.object(security_audit.time, "time", return_value=100):
            security_audit.record("allowed", "10.0.0.50", "02:11:22:33:44:55", "a" * 64, "browser")
            self.assertEqual(security_audit.history()[0]["mac"], "02:11:22:33:44:55")
            with mock.patch.object(security_audit.time, "time", return_value=100 + security_audit.RETENTION + 1):
                security_audit.record("denied", "10.0.0.51")
                self.assertEqual([event["outcome"] for event in security_audit.history()], ["denied"])

    def test_inventory_includes_unrecorded_deployments_and_rejects_bad_entries(self):
        fingerprint = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            clients = Path(directory) / "clients.json"
            deployments = Path(directory) / "deployments.json"
            clients.write_text(json.dumps({fingerprint: "02:11:22:33:44:55"}), encoding="utf-8")
            deployments.write_text("{}", encoding="utf-8")
            with mock.patch.object(security_audit, "CLIENTS_PATH", str(clients)), \
                    mock.patch.object(security_audit, "DEPLOYMENTS_PATH", str(deployments)):
                self.assertEqual(security_audit.inventory()[0]["browsers"], [])
                deployments.write_text(json.dumps({fingerprint: ["Chromium", "Firefox"]}), encoding="utf-8")
                self.assertEqual(security_audit.inventory()[0]["browsers"], ["Chromium", "Firefox"])
                deployments.write_text(json.dumps({"b" * 64: ["Firefox"]}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    security_audit.inventory()


if __name__ == "__main__":
    unittest.main()
