"""Air map key access with an isolated website configuration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "cgi-bin" / "airkey.cgi"


class AirKeyTests(unittest.TestCase):
    def test_isolated_key_path_and_referer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_text("test-key\n", encoding="utf-8")
            env = dict(os.environ, WEBSITEPI_MAPS_KEY_FILE=str(path),
                       HTTP_REFERER="https://example.test/air.html")
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True,
                                    text=True, check=True)
            self.assertEqual(json.loads(result.stdout.split("\n\n", 1)[1]), {"ok": True, "key": "test-key"})
            env["HTTP_REFERER"] = "https://example.test/index.html"
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True,
                                    text=True, check=True)
            self.assertIn("403 Forbidden", result.stdout)
