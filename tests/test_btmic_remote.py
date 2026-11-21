"""Restricted Pi 5 Bluetooth microphone command tests."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piscripts"))
import websitepi_btmic_remote as remote


@unittest.skipIf(os.name == "nt", "Restricted microphone broker requires Linux")
class BluetoothRemoteTests(unittest.TestCase):
    def test_only_fixed_operations_are_permitted(self):
        for command in ("", "id", "websitepi-btmic stop; id", "websitepi-btmic file ../secret.wav"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                remote.main(command)
        real_open = os.open
        with tempfile.TemporaryDirectory() as runtime, \
             mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}), \
             mock.patch.object(remote.os, "getuid", return_value=1234), \
             mock.patch.object(remote.os, "open", wraps=os.open) as open_file, \
             mock.patch.object(remote, "systemctl") as systemctl:
            expected = "/run/user/1234/websitepi-btmic.lock"
            open_file.side_effect = lambda path, flags, mode: real_open(
                os.path.join(runtime, "lock") if path == expected else path, flags, mode)
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1234"}):
                remote.main("websitepi-btmic stop")
        systemctl.assert_called_once_with("stop", *remote.UNITS)

    def test_recordings_exclude_symlinks_and_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "voice.mp3").write_bytes(b"audio")
            (root / "private.txt").write_text("private", encoding="utf-8")
            (root / "link.wav").symlink_to(root / "private.txt")
            with mock.patch.object(remote, "RECORDINGS", directory):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    remote.main("websitepi-btmic list")
                self.assertEqual(output.getvalue(), "voice.mp3\n")
                with self.assertRaises(OSError):
                    remote.send_recording("link.wav")

    def test_stream_start_reports_service_failure(self):
        with mock.patch.object(remote, "listener_in_unit", return_value=False), \
             mock.patch.object(remote, "systemctl", side_effect=[
                 subprocess.CompletedProcess([], 0, stdout="inactive\n"), None,
                 subprocess.CalledProcessError(3, "systemctl"), None,
             ]), \
             self.assertRaisesRegex(RuntimeError, "stream failed"):
            remote.start(remote.UNITS[0])


if __name__ == "__main__":
    unittest.main()
