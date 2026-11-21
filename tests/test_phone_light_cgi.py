"""Authorization and request handling for phone flashlight signals."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import types
import unittest
from unittest import mock
from urllib.parse import urlencode


SCRIPT = Path(__file__).resolve().parents[1] / "cgi-bin" / "phone-light.cgi"


class PhoneLightCgiTests(unittest.TestCase):
    def request(self, data, allowed=True):
        body = urlencode(data)
        env = dict(os.environ, REQUEST_METHOD="POST", CONTENT_TYPE="application/x-www-form-urlencoded",
                   CONTENT_LENGTH=str(len(body)))
        access = types.SimpleNamespace(authorized=lambda: allowed, same_origin=lambda: True)
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.return_value = b'{"ok": true, "mode": "morse", "error": null}\n'
        output = io.StringIO()
        with mock.patch.dict("sys.modules", {"security_access": access}), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("socket.socket", return_value=connection) as sock, \
                mock.patch("socket.AF_UNIX", 1, create=True), \
                mock.patch("sys.stdin", io.StringIO(body)), contextlib.redirect_stdout(output):
            runpy.run_path(str(SCRIPT), run_name="__main__")
        return json.loads(output.getvalue().split("\n\n", 1)[1]), sock, connection

    def test_authorized_start_reaches_service(self):
        result, sock, connection = self.request({"action": "start", "mode": "morse", "message": "SOS"})
        self.assertTrue(result["ok"])
        sock.assert_called_once()
        self.assertEqual(json.loads(connection.sendall.call_args.args[0]), {
            "action": "start", "mode": "morse", "message": "SOS",
        })

    def test_denied_or_invalid_request_does_not_reach_service(self):
        for data, allowed in (({"action": "stop"}, False), ({"action": "delete"}, True)):
            with self.subTest(data=data, allowed=allowed):
                result, sock, _ = self.request(data, allowed=allowed)
                self.assertFalse(result["ok"])
                sock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
