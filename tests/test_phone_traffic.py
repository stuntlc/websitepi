"""Tests for ADB interface counter reads."""
import subprocess
import unittest
from unittest import mock

from piscripts.phone_traffic import phone_traffic


class PhoneTrafficTests(unittest.TestCase):
    @mock.patch("piscripts.phone_traffic.subprocess.run")
    def test_reads_both_counters(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "123\n456\n", "")
        self.assertEqual(phone_traffic("ccmni0"), {"rx_bytes": 123, "tx_bytes": 456})
        self.assertEqual(run.call_args.args[0], [
            "adb", "shell", "cat", "/sys/class/net/ccmni0/statistics/rx_bytes",
            "/sys/class/net/ccmni0/statistics/tx_bytes",
        ])

    @mock.patch("piscripts.phone_traffic.subprocess.run")
    def test_reports_failed_and_invalid_reads(self, run):
        for result in (
            subprocess.CompletedProcess([], 1, "", "device offline"),
            subprocess.CompletedProcess([], 0, "123\nnot-a-number\n", ""),
            subprocess.TimeoutExpired("adb", 8),
        ):
            with self.subTest(result=result):
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.side_effect = None
                    run.return_value = result
                self.assertIn("error", phone_traffic("ccmni0"))


if __name__ == "__main__":
    unittest.main()
