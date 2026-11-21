"""Verify that the service accepts only its systemd-provided socket."""
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "piscripts"))
import systemd_listener


@unittest.skipIf(os.name == "nt", "Systemd socket activation requires POSIX descriptors")
class SystemdListenerTests(unittest.TestCase):
    def test_missing_activation_is_rejected(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                systemd_listener.activated_server(None, 443)

    def test_inherited_listener_serves_requests_and_rejects_wrong_port(self):
        code = (
            "import http.server,os,sys; "
            "sys.path.insert(0,sys.argv[1]); "
            "import systemd_listener; "
            "fd=int(sys.argv[2]); "
            "os.dup2(fd,3) if fd != 3 else None; "
            "os.environ['LISTEN_PID']=str(os.getpid()); "
            "os.environ['LISTEN_FDS']='1'; "
            "server=systemd_listener.activated_server(http.server.SimpleHTTPRequestHandler,int(sys.argv[3])); "
            "server.daemon_threads=False; "
            "server.handle_request(); server.server_close()"
        )
        for wrong_port in (False, True):
            with self.subTest(wrong_port=wrong_port), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen()
                port = listener.getsockname()[1]
                expected = port + 1 if wrong_port else port
                process = subprocess.Popen(
                    [sys.executable, "-c", code, str(ROOT / "piscripts"), str(listener.fileno()), str(expected)],
                    pass_fds=(listener.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                try:
                    if not wrong_port:
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                        connection.request("GET", "/")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        response.read()
                        connection.close()
                    _, stderr = process.communicate(timeout=10)
                    if wrong_port:
                        self.assertNotEqual(process.returncode, 0)
                        self.assertIn(b"Invalid systemd-activated listening socket", stderr)
                    else:
                        self.assertEqual(process.returncode, 0, stderr.decode("utf-8", "replace"))
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    process.stdout.close()
                    process.stderr.close()
