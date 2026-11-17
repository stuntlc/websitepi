"""Exercise SMS and FM rotation handling using a fake ADB command."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("flock"),
                     "Requires Linux bash and flock")
class PhoneRotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.state = self.directory / "state.json"
        self.log = self.directory / "adb.log"
        self.state.write_text(json.dumps({"accelerometer_rotation": "1", "user_rotation": "1"}))
        self.adb = self.directory / "adb"
        self.adb.write_text("""#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["ADB_LOG"], "a") as log:
    log.write(" ".join(args) + "\\n")
with open(os.environ["ADB_STATE"]) as f:
    state = json.load(f)
if args[:4] == ["shell", "settings", "get", "system"]:
    print(state[args[4]])
elif args[:4] == ["shell", "settings", "put", "system"]:
    if args[4:] == ["user_rotation", "0"] and os.environ.get("FAIL_PORTRAIT"):
        sys.exit(1)
    state[args[4]] = args[5]
    with open(os.environ["ADB_STATE"], "w") as f:
        json.dump(state, f)
elif args[:3] == ["shell", "uiautomator", "dump"]:
    sys.exit(1)
elif args[:3] == ["shell", "am", "start"] and os.environ.get("FAIL_START"):
    sys.exit(1)
elif args[:3] == ["shell", "am", "start"] and os.environ.get("HANG_START"):
    time.sleep(60)
""")
        self.adb.chmod(0o755)
        self.env = dict(os.environ, ADB=str(self.adb), ADB_LOG=str(self.log),
                        ADB_STATE=str(self.state), SMS_WAIT_AFTER_LAUNCH="0",
                        SMS_WAIT_AFTER_INPUT="0")

    def tearDown(self):
        self.temp.cleanup()

    def test_sms_uses_portrait_and_restores_auto_rotation(self):
        result = subprocess.run(
            ["bash", str(ROOT / "piscripts" / "smsend"), "+12025550123", "test"],
            env=self.env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertLess(commands.index("shell settings put system user_rotation 0"),
                        commands.index("shell input tap 340 1419"))
        self.assertEqual(json.loads(self.state.read_text()),
                         {"accelerometer_rotation": "1", "user_rotation": "1"})

    def test_fm_failure_still_restores_rotation(self):
        self.env["FAIL_START"] = "1"
        result = subprocess.run(
            ["bash", str(ROOT / "piscripts" / "fmradiophone")],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.state.read_text()),
                         {"accelerometer_rotation": "1", "user_rotation": "1"})

    def test_portrait_failure_restores_auto_rotation(self):
        self.env["FAIL_PORTRAIT"] = "1"
        result = subprocess.run(
            ["bash", str(ROOT / "piscripts" / "fmradiophone")],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.state.read_text()),
                         {"accelerometer_rotation": "1", "user_rotation": "1"})

    def test_terminated_sms_restores_rotation(self):
        self.env["HANG_START"] = "1"
        process = subprocess.Popen(
            ["bash", str(ROOT / "piscripts" / "smsend"), "+12025550123", "test"],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.log.exists() and "shell am start" in self.log.read_text():
                    break
                time.sleep(0.1)
            else:
                self.fail("SMS did not reach the simulated launch")
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(json.loads(self.state.read_text()),
                             {"accelerometer_rotation": "1", "user_rotation": "1"})
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    unittest.main()
