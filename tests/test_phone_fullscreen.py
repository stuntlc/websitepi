"""Tests for the phone browser full-screen controller."""
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cgi-bin"))
import phone_fullscreen


class PhoneFullscreenTests(unittest.TestCase):
    def test_enters_fullscreen_and_removes_forward(self):
        page = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "webSocketDebuggerUrl": "ws://localhost:9000/devtools/page/123",
        }
        response = io.BytesIO(json.dumps([page]).encode())
        ws = mock.Mock()
        ws.recv.return_value = json.dumps({
            "id": 1, "result": {"result": {"value": {"ready": True, "fullscreen": True}}}
        })
        websocket = types.SimpleNamespace(
            create_connection=mock.Mock(return_value=ws), WebSocketException=Exception,
            WebSocketTimeoutException=TimeoutError,
        )
        result = lambda stdout="": subprocess.CompletedProcess([], 0, stdout, "")
        adb = mock.Mock(side_effect=[result("123\n"), result("19000\n"), result()])
        with mock.patch.dict(sys.modules, {"websocket": websocket}), \
                mock.patch.object(phone_fullscreen.urllib.request, "urlopen", return_value=response):
            self.assertTrue(phone_fullscreen.enter_fullscreen(adb, "org.lineageos.jelly", "dQw4w9WgXcQ"))
        self.assertEqual(adb.call_args_list[-1].args, ("forward", "--remove", "tcp:19000"))
        request = json.loads(ws.send.call_args.args[0])
        self.assertTrue(request["params"]["userGesture"])
        ws.close.assert_called_once()

    def test_waits_when_video_is_not_ready(self):
        websocket = types.SimpleNamespace(WebSocketException=Exception, WebSocketTimeoutException=TimeoutError)
        result = lambda stdout="": subprocess.CompletedProcess([], 0, stdout, "")
        adb = mock.Mock(side_effect=[result("123\n"), result("19000\n"), result()])
        with mock.patch.dict(sys.modules, {"websocket": websocket}), \
                mock.patch.object(phone_fullscreen.urllib.request, "urlopen", return_value=io.BytesIO(b"[]")):
            self.assertFalse(phone_fullscreen.enter_fullscreen(adb, "org.lineageos.jelly", "dQw4w9WgXcQ"))
        self.assertEqual(adb.call_args_list[-1].args, ("forward", "--remove", "tcp:19000"))


if __name__ == "__main__":
    unittest.main()
