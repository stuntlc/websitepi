"""Bluetooth PipeWire node discovery."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "piscripts" / "btmic.sh"


@unittest.skipIf(os.name == "nt", "Bluetooth mic script requires Linux")
class BluetoothNodeTests(unittest.TestCase):
    def run_script(self, nodes, mode, listeners=""):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory)
            for name, body in {
                "pw-cli": "cat <<'NODES'\n" + nodes + "\nNODES",
                "mkdir": "exit 0",
                "ss": "printf '%s' '" + listeners + "'",
                "pkill": "echo unexpected-pkill",
                "fuser": "echo unexpected-fuser",
            }.items():
                command = bin_dir / name
                command.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
                command.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"])
            return subprocess.run(["bash", str(SCRIPT)], input=mode + "\n", env=env,
                                  text=True, capture_output=True, timeout=10)

    def test_selects_node_before_name_not_following_internal_capture(self):
        nodes = '''
        id 78, type PipeWire:Interface:Node/3
            node.name = "bluez_output.example.1"
        id 79, type PipeWire:Interface:Node/3
            node.name = "bluez_input.example"
        id 80, type PipeWire:Interface:Node/3
            node.name = "bluez_capture_internal.example"
'''
        result = self.run_script(nodes, "unknown")
        self.assertIn("Input node: 79", result.stdout)
        self.assertIn("Output node: headset (78)", result.stdout)
        self.assertNotIn("Input node: 80", result.stdout)

    def test_missing_microphone_fails_without_restarting_bluetooth(self):
        nodes = '''id 78, type PipeWire:Interface:Node/3
            node.name = "bluez_output.example.1"'''
        result = self.run_script(nodes, "stream")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Bluetooth microphone input not detected", result.stdout)
        self.assertNotIn("restarting", result.stdout)

    def test_busy_audio_port_is_reported_without_killing_other_processes(self):
        nodes = '''id 79, type PipeWire:Interface:Node/3
            node.name = "bluez_input.example"'''
        result = self.run_script(nodes, "stream", "LISTEN 0 5 127.0.0.1:8000 0.0.0.0:*")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Audio port 8000 is already in use", result.stdout)
        self.assertNotIn("unexpected-pkill", result.stdout)
        self.assertNotIn("unexpected-fuser", result.stdout)


if __name__ == "__main__":
    unittest.main()
