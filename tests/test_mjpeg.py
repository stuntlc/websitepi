"""Verify camera streams release their subprocess when a viewer disconnects."""
import http.client
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piscripts"))
import mjpeg


@unittest.skipIf(os.name == "nt", "The fake camera needs an executable script")
class CameraStreamTests(unittest.TestCase):
    def test_disconnect_allows_a_second_viewer_to_start(self):
        with tempfile.TemporaryDirectory() as directory:
            camera = Path(directory) / "camera"
            camera.write_text(
                "#!/usr/bin/env python3\n"
                "import sys, time\n"
                "while True:\n"
                " sys.stdout.buffer.write((b'\\xff\\xd8' + b'x' * 252 + b'\\xff\\xd9') * 4)\n"
                " sys.stdout.buffer.flush()\n"
                " time.sleep(0.02)\n",
                encoding="utf-8",
            )
            camera.chmod(0o755)
            server = mjpeg.MJPEGServer(("127.0.0.1", 0), mjpeg.MJPEGHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            with mock.patch.object(mjpeg, "camera_command", return_value=str(camera)):
                thread.start()
                try:
                    for _ in range(2):
                        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                        connection.request("GET", "/")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertIn(b"\xff\xd8", response.read(512))
                        response.close()
                        connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()
