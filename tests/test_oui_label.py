"""Tests for saving device names without losing existing labels."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode


@unittest.skipIf(os.name == "nt", "The CGI uses Linux file locks")
class OuiLabelTests(unittest.TestCase):
    def test_save_preserves_other_names_and_rejects_corrupt_data(self):
        source = Path(__file__).resolve().parents[1] / "cgi-bin" / "oui-label.cgi"
        for configured in (False, True):
            with self.subTest(configured=configured), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "cgi-bin").mkdir()
                (root / "logs").mkdir()
                state = root / "state" if configured else root / "logs"
                state.mkdir(exist_ok=True)
                script = root / "cgi-bin" / "oui-label.cgi"
                shutil.copyfile(source, script)
                shutil.copyfile(source.parent / "websitepi_paths.py", root / "cgi-bin" / "websitepi_paths.py")
                (root / "cgi-bin" / "security_gate.py").write_text(
                    "def require_access(response_type='text'):\n    return True\n", encoding="utf-8"
                )
                labels = state / "oui-labels.json"
                labels.write_text('{"02:00:00:00:00:01": "Existing"}', encoding="utf-8")
                body = urlencode({"mac": "02:00:00:00:00:02", "label": "My phone"})
                env = dict(os.environ, REQUEST_METHOD="POST", CONTENT_TYPE="application/x-www-form-urlencoded",
                           CONTENT_LENGTH=str(len(body)))
                env.pop("WEBSITEPI_LOG_DIR", None)
                if configured:
                    env["WEBSITEPI_LOG_DIR"] = str(state)
                def submit():
                    return subprocess.run([sys.executable, str(script)], input=body, text=True,
                                          capture_output=True, env=env, check=True).stdout
                self.assertIn("Saved", submit())
                self.assertEqual(json.loads(labels.read_text(encoding="utf-8")), {
                    "02:00:00:00:00:01": "Existing", "02:00:00:00:00:02": "My phone"})
                labels.write_text("{invalid", encoding="utf-8")
                self.assertIn("500 Internal Server Error", submit())
                self.assertEqual(labels.read_text(encoding="utf-8"), "{invalid")
