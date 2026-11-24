"""Camera photo storage for the isolated website account."""
from contextlib import contextmanager, redirect_stdout
import io
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class PhoneCameraTests(unittest.TestCase):
    def run_capture(self, fail_front=False):
        calls = []
        locked = False
        image_id = 0

        @contextmanager
        def lock():
            nonlocal locked
            locked = True
            try:
                yield
            finally:
                locked = False

        def fake_run(command, **kwargs):
            nonlocal image_id
            self.assertTrue(locked)
            calls.append(command)
            if "resolve-activity" in command:
                stdout = "org.lineageos.aperture/.CaptureActivity\n"
            elif "query" in command:
                stdout = "_id=%d, _data=/storage/photo.jpg, date_added=1\n" % image_id
            elif "KEYCODE_CAMERA" in command:
                if not (fail_front and image_id == 1):
                    image_id += 1
                stdout = ""
            else:
                stdout = ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        output = io.StringIO()
        with mock.patch.dict("sys.modules", {"phone_lock": types.SimpleNamespace(phone_lock=lock)}), \
                mock.patch("subprocess.run", side_effect=fake_run), \
                mock.patch("time.sleep"), redirect_stdout(output):
            runpy.run_path(str(ROOT / "cgi-bin" / "phone-cameras.cgi"))
        return calls, output.getvalue()

    def test_explicit_camera_selection_under_phone_lock(self):
        calls, output = self.run_capture()
        starts = [call for call in calls if "start" in call and "am" in call]
        self.assertEqual(len(starts), 2)
        for call, facing in zip(starts, ("false", "true")):
            index = call.index("android.intent.extra.USE_FRONT_CAMERA")
            self.assertEqual(call[index + 1], facing)
        self.assertEqual(sum("force-stop" in call for call in calls), 4)
        self.assertIn("rear=", output)
        self.assertIn("front=", output)

    def test_failed_second_capture_does_not_report_success(self):
        calls, output = self.run_capture(fail_front=True)
        self.assertIn("Camera capture failed", output)
        self.assertNotIn("front=", output)
        self.assertEqual(sum("force-stop" in call for call in calls), 4)


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
        self.command("rpicam-jpeg", '[ "$1" = "-o" ] || exit 1; printf photo > "$2"')
        result = self.run_script("capture.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        name = (self.media / "latest.txt").read_text(encoding="utf-8").strip()
        self.assertTrue(name.endswith("-raw.jpg"))
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
