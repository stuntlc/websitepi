"""Morse and strobe flashlight signal behavior."""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piscripts"))
if os.name != "nt":
    import phone_light_signal as light


@unittest.skipIf(os.name == "nt", "The flashlight service uses a Unix socket")
class PhoneLightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = light.Controller(Path(self.temp.name) / "active")

    def test_morse_spacing_and_validation(self):
        self.assertEqual(list(light.pulses("E T")), [
            (True, light.UNIT), (False, 7 * light.UNIT), (True, 3 * light.UNIT),
        ])
        for value in ("", " ", "SOS!", "A" * 101, "é"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list(light.pulses(value))

    def test_strobe_is_exclusive_and_stop_turns_light_off(self):
        calls = []
        controller = self.controller
        with mock.patch.object(light, "set_light", side_effect=calls.append), \
                mock.patch.object(light, "UNIT", 0.01):
            self.assertEqual(controller.start("strobe")["mode"], "strobe")
            with self.assertRaises(RuntimeError):
                controller.start("morse", "SOS")
            time.sleep(0.03)
            self.assertIsNone(controller.stop()["mode"])
        self.assertTrue(calls[0])
        self.assertFalse(calls[-1])

    def test_morse_finishes_and_light_is_off(self):
        calls = []
        controller = self.controller
        with mock.patch.object(light, "set_light", side_effect=calls.append), \
                mock.patch.object(light, "UNIT", 0.001):
            controller.start("morse", "E")
            controller.thread.join(timeout=1)
            self.assertIsNone(controller.status()["mode"])
        self.assertEqual(calls, [True, False])

    def test_flash_error_is_reported_and_stop_retries_off(self):
        controller = self.controller
        with mock.patch.object(light, "set_light", side_effect=[RuntimeError("offline"), None, None]) as lamp:
            with self.assertRaisesRegex(RuntimeError, "offline"):
                controller.start("strobe")
            controller.thread.join(timeout=1)
            self.assertIn("offline", controller.status()["error"])
            self.assertIsNone(controller.stop()["error"])
            self.assertEqual(lamp.call_args.args, (False,))

    def test_cleanup_only_turns_off_an_interrupted_signal(self):
        marker = self.controller.marker
        with mock.patch.object(light, "set_light") as lamp:
            light.cleanup_marker(marker)
            lamp.assert_not_called()
            marker.touch()
            light.cleanup_marker(marker)
            lamp.assert_called_once_with(False)
            self.assertFalse(marker.exists())

    def test_cleanup_keeps_marker_when_turning_off_fails(self):
        marker = self.controller.marker
        marker.touch()
        with mock.patch.object(light, "set_light", side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                light.cleanup_marker(marker)
        self.assertTrue(marker.exists())

    def test_start_waits_for_stop_to_finish(self):
        controller = self.controller
        off_started = threading.Event()
        allow_off = threading.Event()

        def lamp(on):
            if not on and controller.stop_event.is_set():
                off_started.set()
                self.assertTrue(allow_off.wait(2))

        with mock.patch.object(light, "set_light", side_effect=lamp):
            controller.start("strobe")
            stopping = threading.Thread(target=controller.stop)
            stopping.start()
            self.assertTrue(off_started.wait(2))
            starting = threading.Thread(target=controller.start, args=("morse", "E"))
            starting.start()
            time.sleep(0.05)
            self.assertTrue(starting.is_alive())
            allow_off.set()
            stopping.join(2)
            starting.join(2)
            controller.stop()
            self.assertFalse(stopping.is_alive())
            self.assertFalse(starting.is_alive())


if __name__ == "__main__":
    unittest.main()
