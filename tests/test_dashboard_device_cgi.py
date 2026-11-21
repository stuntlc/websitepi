"""Verify dashboard device commands report failures through CGI."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Device CGI scripts require Bash")
class DashboardDeviceCgiTests(unittest.TestCase):
    def test_device_commands_report_adb_and_fm_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cgi-bin").mkdir()
            (root / "piscripts").mkdir()
            adb = root / "adb"
            adb.write_text('#!/bin/sh\necho "device output"\nexit "$TEST_EXIT"\n')
            adb.chmod(0o755)
            fm = root / "piscripts" / "fmradiophone"
            fm.write_text('echo "device output"\nexit "$TEST_EXIT"\n')
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"])
            for name in ("fmradiophone", "fmphoneoff", "phonelight1", "phonelight0"):
                script = root / "cgi-bin" / name
                script.write_bytes((ROOT / "cgi-bin" / name).read_bytes())
                for code in (0, 1):
                    with self.subTest(script=name, code=code):
                        env["TEST_EXIT"] = str(code)
                        result = subprocess.run(
                            ["bash", str(script)], env=env, capture_output=True, text=True
                        )
                        self.assertEqual(result.returncode, code)
                        self.assertIn("Content-Type: text/plain\n\n", result.stdout)
                        if code:
                            self.assertTrue(result.stdout.startswith("Status: 500 "))
                            self.assertIn("ERROR:", result.stdout)
                        else:
                            self.assertTrue(result.stdout.startswith("Content-Type:"))
                            self.assertNotIn("device output", result.stdout)


if __name__ == "__main__":
    unittest.main()
