"""Tests for the phone screenshot CGI."""
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest import mock


path = Path(__file__).resolve().parents[1] / "cgi-bin" / "phone-screen.cgi"
loader = importlib.machinery.SourceFileLoader("phone_screen", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
phone_screen = importlib.util.module_from_spec(spec)
loader.exec_module(phone_screen)


class PhoneScreenTests(unittest.TestCase):
    def test_returns_png_from_adb(self):
        image = b"\x89PNG\r\n\x1a\nimage"
        result = subprocess.CompletedProcess([], 0, image, b"")
        output = mock.Mock()
        output.buffer = io.BytesIO()
        with mock.patch.object(phone_screen.subprocess, "run", return_value=result) as run, \
                mock.patch.object(phone_screen.sys, "stdout", output):
            phone_screen.main()
        self.assertIn(b"Content-Type: image/png\r\n", output.buffer.getvalue())
        self.assertTrue(output.buffer.getvalue().endswith(image))
        self.assertEqual(run.call_args.args[0][-3:], ["exec-out", "screencap", "-p"])

    def test_reports_adb_failure_and_invalid_image(self):
        for result in (
            subprocess.CompletedProcess([], 1, b"", b"device offline"),
            subprocess.CompletedProcess([], 0, b"not a PNG", b""),
        ):
            with self.subTest(result=result), \
                    mock.patch.object(phone_screen.subprocess, "run", return_value=result), \
                    mock.patch.object(phone_screen, "fail") as fail:
                phone_screen.main()
                fail.assert_called_once()


if __name__ == "__main__":
    unittest.main()
