"""Verify dashboard readings reflect observed hardware states."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cgi-bin"))
import device_status


class DeviceStatusTests(unittest.TestCase):
    def test_relay_reads_pin_level_and_rejects_other_modes(self):
        with mock.patch.object(device_status.shutil, "which", side_effect=lambda name: "/usr/bin/raspi-gpio" if name == "raspi-gpio" else None), \
                mock.patch.object(device_status, "command") as command:
            for level in (0, 1):
                command.return_value = f"GPIO 12: level={level} fsel=1 func=OUTPUT"
                self.assertEqual(device_status.relay_state(), bool(level))
            command.return_value = "GPIO 12: level=0 fsel=0 func=INPUT"
            self.assertFalse(device_status.relay_state())
            command.return_value = "GPIO 12: level=1 fsel=4 func=ALT0"
            with self.assertRaises(ValueError):
                device_status.relay_state()
        with mock.patch.object(device_status.shutil, "which", return_value="/usr/bin/pinctrl"), \
                mock.patch.object(device_status, "command", return_value="12: op -- pu | hi // GPIO12 = output"):
            self.assertTrue(device_status.relay_state())

    def test_fm_tracks_active_tuner_client_not_just_process(self):
        active = (
            " Inputs (1):\n  1. Port ID: 176; flags\n"
            "     Devices: AUDIO_DEVICE_IN_FM_TUNER, @:\n"
            "     AudioRecord Clients (1):\n"
            "      1. Port ID: 177; uid 1000; State: Active\n"
            "         Attributes: Source: AUDIO_SOURCE_FM_TUNER\n"
            "\n Total Effects CPU: 0\n"
        )
        with mock.patch.object(device_status, "adb", return_value=active) as adb:
            self.assertTrue(device_status.fm_state())
            adb.return_value = active.replace("State: Active", "State: Idle")
            self.assertFalse(device_status.fm_state())
            adb.return_value = " Inputs (0):\n\n Total Effects CPU: 0\n"
            self.assertFalse(device_status.fm_state())
            adb.return_value = "unexpected output"
            with self.assertRaises(ValueError):
                device_status.fm_state()

    def test_flashlight_and_partial_failures(self):
        with mock.patch.object(device_status, "adb", return_value="0"):
            self.assertFalse(device_status.flashlight_state())
        with mock.patch.object(device_status, "adb", return_value="1"):
            self.assertTrue(device_status.flashlight_state())
        with mock.patch.object(device_status, "fm_state", side_effect=subprocess.TimeoutExpired("adb", 10)), \
                mock.patch.object(device_status, "relay_state", return_value=False), \
                mock.patch.object(device_status, "flashlight_state", return_value=True):
            states = device_status.read_states()
        self.assertIsNone(states["fm"]["on"])
        self.assertTrue(states["fm"]["error"])
        self.assertFalse(states["led"]["on"])
        self.assertTrue(states["flash"]["on"])


if __name__ == "__main__":
    unittest.main()
