"""Verify relay actions return valid CGI responses."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Relay CGI scripts require Bash")
class RelayCgiTests(unittest.TestCase):
    def test_relay_success_and_failure_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for action in ("on", "off"):
                source = (ROOT / "cgi-bin" / ("relay" + action + ".sh")).read_text()
                command = root / ("relay" + action)
                script = root / ("relay" + action + ".sh")
                script.write_text(source.replace("/home/q/websd/piscripts/relay" + action, str(command)))
                env = dict(os.environ)
                env.pop("REQUEST_METHOD", None)
                for code in (0, 1):
                    with self.subTest(action=action, code=code):
                        command.write_text("#!/bin/sh\nexit %s\n" % code)
                        command.chmod(0o755)
                        result = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)
                        self.assertEqual(result.returncode, code)
                        self.assertIn("Content-Type: text/plain\n\n", result.stdout)
                        if code:
                            self.assertIn("Status: 500", result.stdout)
                            self.assertIn("ERROR:", result.stdout)
                        else:
                            self.assertIn("Relay turned " + action.upper(), result.stdout)


if __name__ == "__main__":
    unittest.main()
