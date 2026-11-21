"""Verify phone flashlight commands do not require sudo."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "The flashlight helper uses Bash")
class FlashTests(unittest.TestCase):
    def test_on_and_off_use_the_existing_adb_server(self):
        with tempfile.TemporaryDirectory() as directory:
            adb = Path(directory) / "adb"
            adb.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
            adb.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ.get("PATH", ""))
            for action, value in (("on", "1"), ("off", "0")):
                with self.subTest(action=action):
                    result = subprocess.run(
                        ["bash", str(ROOT / "cgi-bin" / "flash.sh"), action],
                        capture_output=True, text=True, env=env, check=True,
                    )
                    self.assertEqual(result.stdout.splitlines(),
                                     ["shell", "echo %s > /sys/class/leds/flashlight/brightness" % value])
