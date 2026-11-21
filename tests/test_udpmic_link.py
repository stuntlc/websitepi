"""Tests for the USB microphone link check."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "cgi-bin" / "udpmic-adb.cgi"


def check_link(pi, phone):
    output = io.StringIO()
    form = mock.Mock()
    form.getfirst.side_effect = lambda name, default="": "link" if name == "action" else default
    with mock.patch("cgi.FieldStorage", return_value=form), \
            mock.patch("subprocess.run", side_effect=[pi, phone]) as run, \
            contextlib.redirect_stdout(output):
        with unittest.TestCase().assertRaises(SystemExit):
            runpy.run_path(str(SCRIPT))
    return json.loads(output.getvalue().split("\n\n", 1)[1]), run


def result(output, code=0, error=""):
    return subprocess.CompletedProcess([], code, output, error)


class LinkTests(unittest.TestCase):
    def test_selects_matching_usb_addresses(self):
        data, run = check_link(
            result("4: usb0 inet 192.0.2.2/24 scope global usb0"),
            result("31: rndis0 inet 192.0.2.1/24 scope global rndis0"),
        )
        self.assertEqual(data, {"ok": True, "host": "192.0.2.2", "phone": "192.0.2.1"})
        self.assertEqual(run.call_count, 2)

    def test_rejects_missing_or_mismatched_link(self):
        for phone in (result(""), result("inet 192.168.2.1/24"), result("", 1, "device offline")):
            with self.subTest(phone=phone):
                data, _ = check_link(result("inet 192.0.2.2/24"), phone)
                self.assertFalse(data["ok"])
                self.assertIn("USB link check failed", data["error"])

    def test_stop_is_idempotent_without_starting_background_service(self):
        for reply, expected in (
            (result("Stopping service", 255, "Service stopped"), True),
            (result("Stopping service", 255, "Service not stopped: was not running."), True),
            (result("Error: device offline", 255), False),
        ):
            with self.subTest(reply=reply):
                output = io.StringIO()
                form = mock.Mock()
                form.getfirst.side_effect = lambda name, default="": "stop" if name == "action" else default
                with mock.patch("cgi.FieldStorage", return_value=form), \
                        mock.patch("subprocess.run", return_value=reply) as run, \
                        contextlib.redirect_stdout(output):
                    with contextlib.suppress(SystemExit):
                        runpy.run_path(str(SCRIPT))
                data = json.loads(output.getvalue().split("\n\n", 1)[1])
                self.assertEqual(data["ok"], expected)
                self.assertEqual(run.call_args.args[0][:4], ["adb", "shell", "am", "stopservice"])


if __name__ == "__main__":
    unittest.main()
