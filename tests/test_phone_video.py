"""Tests for the phone video CGI."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


path = Path(__file__).resolve().parents[1] / "cgi-bin" / "phone-video.cgi"
sys.path.insert(0, str(path.parent))
loader = importlib.machinery.SourceFileLoader("phone_video", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
phone_video = importlib.util.module_from_spec(spec)
loader.exec_module(phone_video)


class PhoneVideoTests(unittest.TestCase):
    def test_video_links_are_canonicalized(self):
        for url in (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/shorts/dQw4w9WgXcQ",
            "https://youtube.com/live/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    phone_video.video_url(url),
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&autoplay=1",
                )

    def test_rejects_non_video_and_unsafe_links(self):
        for url in (
            "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
            "https://youtube.com@evil.test/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ&v=aaaaaaaaaaa",
            "https://youtu.be/dQw4w9WgXcQ;reboot",
            "https://youtube.com/playlist?list=foo",
            "https://youtube.com:bad/watch?v=dQw4w9WgXcQ",
        ):
            with self.subTest(url=url):
                self.assertIsNone(phone_video.video_url(url))

    def request(self, url, results, method="POST", action="play"):
        form = mock.Mock()
        form.getfirst.side_effect = lambda name, default="": {"url": url, "action": action}.get(name, default)
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"REQUEST_METHOD": method, "CONTENT_LENGTH": "100"}), \
                mock.patch.object(phone_video.cgi, "FieldStorage", return_value=form), \
                mock.patch.object(phone_video, "run_adb", side_effect=results) as adb, \
                mock.patch.object(phone_video, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_video, "save_and_set_landscape"), \
                mock.patch.object(phone_video, "restore_rotation"), \
                contextlib.redirect_stdout(output):
            phone_video.main()
        return output.getvalue(), adb

    def test_opens_canonical_url_in_resolved_browser(self):
        result = lambda stdout: subprocess.CompletedProcess([], 0, stdout, "")
        output, adb = self.request(
            "https://youtube.com/watch?v=dQw4w9WgXcQ&t=5",
            [result("com.browser/.MainActivity\n"), result("Starting: Intent\n")],
        )
        self.assertIn('"ok": true', output)
        self.assertEqual(adb.call_args_list[0].args, (
            "shell", "cmd", "package", "resolve-activity", "--brief",
            "-a", "android.intent.action.VIEW", "-c", "android.intent.category.BROWSABLE",
            "-d", "https://example.com",
        ))
        self.assertEqual(adb.call_args_list[1].args, (
            "shell", "am", "start", "-n", "com.browser/.MainActivity",
            "-a", "android.intent.action.VIEW", "-d",
            "'https://www.youtube.com/watch?v=dQw4w9WgXcQ&autoplay=1'",
        ))

    def test_real_cgi_parses_invalid_post(self):
        body = "url=https%3A%2F%2Fevil.test%2F"
        env = dict(os.environ, REQUEST_METHOD="POST",
                   CONTENT_TYPE="application/x-www-form-urlencoded",
                   CONTENT_LENGTH=str(len(body)))
        result = subprocess.run(
            [sys.executable, str(path)], input=body, capture_output=True,
            text=True, env=env, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("400 Bad Request", result.stdout)
        self.assertIn("valid YouTube video link", result.stdout)

    def test_invalid_input_never_calls_adb(self):
        output, adb = self.request("https://evil.test/", [])
        self.assertIn("400 Bad Request", output)
        adb.assert_not_called()
        output, adb = self.request("https://youtu.be/dQw4w9WgXcQ", [], method="GET")
        self.assertIn("405 Method Not Allowed", output)
        adb.assert_not_called()

    def test_stop_closes_the_resolved_browser(self):
        result = lambda stdout: subprocess.CompletedProcess([], 0, stdout, "")
        output, adb = self.request("", [result("org.lineageos.jelly/.MainActivity\n"), result("")], action="stop")
        self.assertIn('"ok": true', output)
        self.assertEqual(adb.call_args_list[1].args, ("shell", "am", "force-stop", "org.lineageos.jelly"))

    def test_fullscreen_reports_when_player_is_ready(self):
        result = subprocess.CompletedProcess([], 0, "org.lineageos.jelly/.MainActivity\n", "")
        with mock.patch.object(phone_video, "enter_fullscreen", return_value=True) as fullscreen:
            output, _ = self.request("https://youtu.be/dQw4w9WgXcQ", [result], action="fullscreen")
        self.assertIn('"ready": true', output)
        self.assertEqual(fullscreen.call_args.args[1:], ("org.lineageos.jelly", "dQw4w9WgXcQ"))

    def test_landscape_saves_and_restores_original_rotation(self):
        result = lambda stdout="": subprocess.CompletedProcess([], 0, stdout, "")
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(phone_video, "ROTATION_PATH", str(Path(temp) / "rotation.json")), \
                mock.patch.object(phone_video, "run_adb", side_effect=[
                    result("1\n"), result("0\n"), result(), result(),
                    result(), result(), result(), result(),
                ]) as adb:
            phone_video.save_and_set_landscape()
            phone_video.save_and_set_landscape()
            phone_video.restore_rotation()
            self.assertFalse(Path(phone_video.ROTATION_PATH).exists())
            self.assertEqual(adb.call_args_list[-2].args[-2:], ("user_rotation", "0"))
            self.assertEqual(adb.call_args_list[-1].args[-2:], ("accelerometer_rotation", "1"))

    def test_browser_and_adb_failures_are_reported(self):
        result = subprocess.CompletedProcess([], 0, "No activity found\n", "")
        output, adb = self.request("https://youtu.be/dQw4w9WgXcQ", [result])
        self.assertIn("502 Bad Gateway", output)
        self.assertIn("No default browser", output)
        self.assertEqual(adb.call_count, 1)
        output, _ = self.request(
            "https://youtu.be/dQw4w9WgXcQ", [OSError("adb unavailable")]
        )
        self.assertIn("adb unavailable", output)
        output, _ = self.request(
            "https://youtu.be/dQw4w9WgXcQ",
            [subprocess.CompletedProcess([], 0, "com.browser/.Main\n", ""),
             subprocess.CompletedProcess([], 0, "Error: Activity not started\n", "")],
        )
        self.assertIn("502 Bad Gateway", output)


if __name__ == "__main__":
    unittest.main()
