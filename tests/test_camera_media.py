"""Camera photo storage for the isolated website account."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "Camera CGI scripts require Linux")
class CameraMediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.media = self.directory / "media"
        self.media.mkdir()
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.command("pkill", "exit 0")
        self.environment = dict(os.environ, WEBSITEPI_MEDIA_DIR=str(self.media),
                                PATH=str(self.bin) + os.pathsep + os.environ["PATH"])

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, name, body):
        executable = self.bin / name
        executable.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        executable.chmod(0o755)

    def run_script(self, name):
        return subprocess.run(["bash", str(ROOT / "cgi-bin" / name)], env=self.environment,
                              capture_output=True, text=True, check=False)

    def test_capture_saves_and_reports_photo_in_media_directory(self):
        self.command("rpicam-jpeg", 'printf photo > "$4"')
        result = self.run_script("capture.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        name = (self.media / "latest.txt").read_text(encoding="utf-8").strip()
        self.assertEqual((self.media / name).read_bytes(), b"photo")
        self.assertIn("saved:/media/" + name, result.stdout)

    def test_failed_capture_does_not_replace_latest_marker(self):
        (self.media / "latest.txt").write_text("previous.jpg\n", encoding="utf-8")
        self.command("rpicam-jpeg", "exit 1")
        result = self.run_script("capture.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Camera capture failed", result.stdout)
        self.assertEqual((self.media / "latest.txt").read_text(encoding="utf-8"), "previous.jpg\n")

    def test_cleanup_removes_old_photos_from_media_directory(self):
        old = self.media / "old.jpg"
        newest = self.media / "new.jpg"
        old.write_bytes(b"old")
        newest.write_bytes(b"new")
        os.utime(old, (1, 1))
        result = self.run_script("cleanup.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(old.exists())
        self.assertTrue(newest.exists())


if __name__ == "__main__":
    unittest.main()
