"""Verify the website reboot control remains gated and reports failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "The SMS CGI requires Bash")
class SmsCgiTests(unittest.TestCase):
    def test_reboot_uses_the_narrow_systemd_action_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            systemctl = root / "systemctl"
            systemctl.write_text('#!/bin/sh\nprintf "%s" "$1" > "$REBOOT_LOG"\nexit "${REBOOT_STATUS:-0}"\n',
                                 encoding="utf-8")
            systemctl.chmod(0o755)
            env = dict(os.environ, QUERY_STRING="reboot", REBOOT_LOG=str(root / "action"),
                       PATH=directory + os.pathsep + os.environ.get("PATH", ""))
            env.pop("REQUEST_METHOD", None)
            for status in ("0", "1"):
                env["REBOOT_STATUS"] = status
                result = subprocess.run(["bash", str(ROOT / "cgi-bin" / "sms.cgi")],
                                        capture_output=True, text=True, env=env)
                self.assertEqual((root / "action").read_text(encoding="utf-8"), "reboot")
                if status == "0":
                    self.assertEqual(result.returncode, 0)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("ERROR: Pi reboot is not available", result.stdout)

    def test_http_request_cannot_trigger_reboot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            systemctl = root / "systemctl"
            systemctl.write_text('#!/bin/sh\ntouch "$REBOOT_LOG"\n', encoding="utf-8")
            systemctl.chmod(0o755)
            env = dict(os.environ, REQUEST_METHOD="GET", QUERY_STRING="reboot",
                       HTTP_WEBSITEPI_SEC_TLS="1", REBOOT_LOG=str(root / "action"),
                       PATH=directory + os.pathsep + os.environ.get("PATH", ""))
            env.pop("WEBSITEPI_SEC_TLS", None)
            result = subprocess.run(["bash", str(ROOT / "cgi-bin" / "sms.cgi")],
                                    capture_output=True, text=True, env=env, check=True)
            self.assertIn("403 Forbidden", result.stdout)
            self.assertFalse((root / "action").exists())
