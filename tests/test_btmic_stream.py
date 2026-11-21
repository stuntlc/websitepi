"""Verify BT audio is fetched from Pi 5's loopback interface over SSH."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "cgi-bin" / "btmic-stream.cgi"


@unittest.skipIf(os.name == "nt", "The fake SSH command needs an executable script")
class BluetoothStreamTests(unittest.TestCase):
    def run_stream(self, fake_body, restricted=False):
        with tempfile.TemporaryDirectory() as directory:
            ssh = Path(directory) / "ssh"
            args = Path(directory) / "args"
            ssh.write_text(
                "#!/usr/bin/env python3\nimport os, sys\n"
                "open(os.environ['FAKE_ARGS'], 'w').write('\\n'.join(sys.argv[1:]))\n" + fake_body,
                encoding="utf-8",
            )
            ssh.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"], FAKE_ARGS=str(args))
            env.pop("REQUEST_METHOD", None)
            if restricted:
                env.update(BTMIC_RESTRICTED="1", BTMIC_SSH_KEY="/var/lib/websitepi/.ssh/btmic_ed25519")
            else:
                env.pop("BTMIC_RESTRICTED", None)
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, timeout=10)
            return result, args.read_text(encoding="utf-8")

    def test_audio_is_fetched_from_remote_loopback(self):
        result, args = self.run_stream("sys.stdout.buffer.write(b'ID3fixture')\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Content-Type: audio/mpeg", result.stdout)
        self.assertTrue(result.stdout.endswith(b"ID3fixture"))
        self.assertIn("q@10.0.0.50", args)
        self.assertIn("http://127.0.0.1:8000/live.mp3", args)

    def test_missing_audio_reports_an_error(self):
        result, _ = self.run_stream("sys.stderr.write('connection refused')\nsys.exit(1)\n")
        self.assertIn(b"502 Bad Gateway", result.stdout)
        self.assertIn(b"connection refused", result.stdout)

    def test_restricted_stream_uses_only_the_forced_command(self):
        result, args = self.run_stream("sys.stdout.buffer.write(b'ID3fixture')\n", restricted=True)
        self.assertIn(b"Content-Type: audio/mpeg", result.stdout)
        self.assertIn("websitepi-btmic stream", args)
        self.assertIn("/var/lib/websitepi/.ssh/btmic_ed25519", args)
        self.assertNotIn("curl", args)
