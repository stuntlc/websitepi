"""Tests for the Orange USSD request and phone dialog cleanup."""
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


path = Path(__file__).resolve().parents[1] / "cgi-bin" / "phone-ussd.cgi"
sys.path.insert(0, str(path.parent))
loader = importlib.machinery.SourceFileLoader("phone_ussd", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
phone_ussd = importlib.util.module_from_spec(spec)
loader.exec_module(phone_ussd)


def screen(message=None, button_id="button2", button_text="CANCEL"):
    root = ET.Element("hierarchy")
    if message is not None:
        ET.SubElement(root, "node", {
            "package": "com.android.phone", "resource-id": "android:id/message",
            "text": message,
        })
        ET.SubElement(root, "node", {
            "package": "com.android.phone", "resource-id": "android:id/" + button_id,
            "text": button_text, "clickable": "true", "bounds": "[100,200][200,300]",
        })
    return root


class PhoneUssdTests(unittest.TestCase):
    def test_reads_data_and_closes_dialog(self):
        menu = screen("General credit, 1 euro\nOption : Data, 10 GB, valid 30 day(s)")
        pending = screen("USSD code running...")
        with mock.patch.object(phone_ussd, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_ussd, "phone_ui", side_effect=[screen(), pending, menu, menu, screen(), screen()]), \
                mock.patch.object(phone_ussd, "adb", return_value="") as adb, \
                mock.patch.object(phone_ussd.time, "sleep"):
            self.assertEqual(phone_ussd.read_balance(), "Data, 10 GB, valid 30 day(s)")
        self.assertEqual(adb.call_args_list[0].args[-1], phone_ussd.USSD_URI)
        self.assertEqual(adb.call_args_list[1].args, ("shell", "input", "tap", "150", "250"))

    def test_waits_for_pending_request_before_cleanup(self):
        pending = screen("USSD code running...")
        menu = screen("Option : Data, 10 GB")
        with mock.patch.object(phone_ussd, "phone_ui", side_effect=[pending, menu, screen(), screen()]), \
                mock.patch.object(phone_ussd, "adb", return_value="") as adb, \
                mock.patch.object(phone_ussd.time, "sleep"):
            phone_ussd.close_dialog()
        adb.assert_called_once_with("shell", "input", "tap", "150", "250")

    def test_pending_timeout_reports_dialog_may_remain(self):
        pending = screen("USSD code running...")
        with mock.patch.object(phone_ussd, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_ussd, "phone_ui", side_effect=[screen(), pending, pending]), \
                mock.patch.object(phone_ussd, "adb", return_value=""), \
                mock.patch.object(phone_ussd.time, "monotonic", side_effect=[0, 1, 36, 0, 1, 26]), \
                mock.patch.object(phone_ussd.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "delayed phone dialog may still appear.*Could not verify"):
                phone_ussd.read_balance()

    def test_cleanup_dismisses_error_then_underlying_menu(self):
        error = screen("Connection problem or invalid MMI code.", "button1", "OK")
        menu = screen("Option : Data, 10 GB")
        with mock.patch.object(phone_ussd, "phone_ui", side_effect=[error, menu, screen(), screen()]), \
                mock.patch.object(phone_ussd, "adb", return_value="") as adb, \
                mock.patch.object(phone_ussd.time, "sleep"):
            phone_ussd.close_dialog()
        self.assertEqual(adb.call_count, 2)

    def test_unexpected_response_is_closed_and_reported(self):
        dialog = screen("Connection problem or invalid MMI code.", "button1", "OK")
        with mock.patch.object(phone_ussd, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_ussd, "phone_ui", side_effect=[screen(), dialog, dialog, screen(), screen()]), \
                mock.patch.object(phone_ussd, "adb", return_value="") as adb, \
                mock.patch.object(phone_ussd.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "unexpected response"):
                phone_ussd.read_balance()
        self.assertEqual(adb.call_args_list[1].args, ("shell", "input", "tap", "150", "250"))

    def test_cleanup_failure_is_not_reported_as_success(self):
        menu = screen("Option : Data, 10 GB", "button1", "SEND")
        with mock.patch.object(phone_ussd, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_ussd, "phone_ui", side_effect=[screen(), menu, menu]), \
                mock.patch.object(phone_ussd, "adb", return_value=""), \
                self.assertRaisesRegex(RuntimeError, "Could not verify"):
            phone_ussd.read_balance()

    def test_existing_dialog_is_not_modified(self):
        with mock.patch.object(phone_ussd, "phone_lock", side_effect=contextlib.nullcontext), \
                mock.patch.object(phone_ussd, "phone_ui", return_value=screen("Already open")), \
                mock.patch.object(phone_ussd, "adb") as adb, \
                self.assertRaisesRegex(RuntimeError, "already open"):
            phone_ussd.read_balance()
        adb.assert_not_called()

    def test_rejects_cross_origin_and_get_without_touching_phone(self):
        for env in (
            {"REQUEST_METHOD": "GET"},
            {"REQUEST_METHOD": "POST", "HTTP_HOST": "pi:8080", "HTTP_ORIGIN": "https://other.example"},
            {"REQUEST_METHOD": "POST", "HTTP_SEC_FETCH_SITE": "cross-site"},
        ):
            output = io.StringIO()
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(phone_ussd, "read_balance") as read, contextlib.redirect_stdout(output):
                phone_ussd.main()
            self.assertIn('"ok": false', output.getvalue())
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
