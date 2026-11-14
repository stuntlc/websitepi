"""Linux integration tests for UDP mic receiver startup and recovery."""
import fcntl
from collections import namedtuple
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
Result = namedtuple("Result", "returncode stdout stderr")


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ReceiverStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="udpmic-test-")
        self.directory = Path(self.temp.name)
        self.udp_port = free_port(socket.SOCK_DGRAM)
        self.tcp_port = free_port(socket.SOCK_STREAM)
        self.receiver = self.directory / "udpmic.py"
        self.lock = self.directory / "udpmic.lock"
        with open(str(ROOT / "piscripts" / "udpmic.py")) as source:
            receiver_source = source.read()
        with open(str(self.receiver), "w") as receiver:
            receiver.write(
                receiver_source.replace("UDP_PORT = 9100", "UDP_PORT = {}".format(self.udp_port))
                .replace("HTTP_PORT = 9101", "HTTP_PORT = {}".format(self.tcp_port))
            )
        with open(str(ROOT / "cgi-bin" / "udpmic.cgi")) as source:
            script = source.read()
        script = script.replace("/home/q/websd/logs/udpmic.log", str(self.directory / "udpmic.log"))
        script = script.replace("/tmp/udpmic.lock", str(self.lock))
        script = script.replace("/home/q/websd/piscripts/udpmic[.]py", str(self.receiver).replace(".py", "[.]py"))
        script = script.replace("/home/q/websd/piscripts/udpmic.py", str(self.receiver))
        script = script.replace("9100", str(self.udp_port)).replace("9101", str(self.tcp_port))
        self.script = self.directory / "udpmic.cgi"
        with open(str(self.script), "w") as output:
            output.write(script)

    def tearDown(self):
        self.cgi("stop")
        self.temp.cleanup()

    def cgi(self, action):
        env = dict(os.environ, QUERY_STRING="action=" + action)
        process = subprocess.Popen(
            ["bash", str(self.script)], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True,
        )
        stdout, stderr = process.communicate(timeout=30)
        return Result(process.returncode, stdout, stderr)

    def test_repeated_start_and_stop_do_not_leave_lock_held(self):
        for action in ("start", "start", "stop", "start"):
            started = time.monotonic()
            result = self.cgi(action)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertLess(time.monotonic() - started, 3)

    def test_recovers_lock_inherited_by_old_receiver(self):
        with open(str(self.lock), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            old = subprocess.Popen(
                ["python3", str(self.receiver)],
                pass_fds=(lock.fileno(),),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        try:
            result = self.cgi("start")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            old.wait(timeout=5)
        finally:
            if old.poll() is None:
                old.kill()
                old.wait()

    def test_port_conflict_is_reported_without_killing_owner(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", self.udp_port))
            result = self.cgi("start")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already in use", result.stdout)
            self.assertEqual(sock.getsockname()[1], self.udp_port)

    def test_receiver_exits_if_udp_bind_fails(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", self.udp_port))
            process = subprocess.Popen(
                ["python3", str(self.receiver)], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True,
            )
            stdout, stderr = process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0, stdout + stderr)
            self.assertIn("receiver startup failed", stderr)


if __name__ == "__main__":
    unittest.main()
