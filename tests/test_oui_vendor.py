"""Tests for local OUI database loading and vendor classification."""
import os
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piscripts"))
from oui_vendor import device_type, load_vendors


class OuiVendorTests(unittest.TestCase):
    def test_prefers_current_csv_and_falls_back_to_legacy_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = os.path.join(directory, "oui.csv")
            legacy_path = os.path.join(directory, "oui.txt")
            Path(csv_path).write_text('Registry,Assignment,Organization Name\nMA-L,AABBCC,"Samsung Electronics Co.,Ltd"\n', encoding="utf-8")
            Path(legacy_path).write_text("AABBCC\tOld Vendor\nDDEEFF\tOther Vendor\n", encoding="utf-8")
            vendors, files = load_vendors([csv_path, legacy_path, os.path.join(directory, "missing")])
            self.assertEqual(vendors["AABBCC"], "Samsung Electronics Co.,Ltd")
            self.assertEqual(vendors["DDEEFF"], "Other Vendor")
            self.assertEqual(files, [csv_path, legacy_path])
            self.assertEqual(device_type(vendors["AABBCC"]), "Android phone/tablet")
            self.assertEqual(device_type("Unknown vendor"), "Unknown device")

    def test_invalid_csv_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "oui.csv")
            Path(path).write_text("wrong,headers\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid IEEE OUI CSV"):
                load_vendors([path])
