"""Use the phone browser's local debugging interface to enter video full screen."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request


EXPRESSION = """(async () => {
  const video = document.querySelector("video");
  if (document.visibilityState !== "visible" || !video || video.readyState < 2)
    return {ready: false};
  if (!document.fullscreenElement) await video.requestFullscreen();
  await video.play();
  return {ready: true, fullscreen: !!document.fullscreenElement};
})()"""


def enter_fullscreen(run_adb, package, video_id):
    try:
        import websocket
    except ImportError as error:
        raise RuntimeError("Install the Pi requirements: python3 -m pip install --user -r requirements.txt") from error

    process = run_adb("shell", "pidof", package)
    pid = process.stdout.strip()
    if process.returncode != 0 or not pid.isdigit():
        return False
    forward = run_adb("forward", "tcp:0", "localabstract:webview_devtools_remote_" + pid)
    port = forward.stdout.strip()
    if forward.returncode != 0 or not port.isdigit():
        raise RuntimeError((forward.stderr or forward.stdout).strip() or "ADB forwarding failed.")
    try:
        try:
            with urllib.request.urlopen("http://127.0.0.1:" + port + "/json", timeout=3) as response:
                pages = json.load(response)
        except (urllib.error.URLError, TimeoutError):
            return False
        for page in pages:
            page_url = urllib.parse.urlsplit(page.get("url", ""))
            if (page_url.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com")
                    or urllib.parse.parse_qs(page_url.query).get("v") != [video_id]):
                continue
            debug_path = urllib.parse.urlsplit(page.get("webSocketDebuggerUrl", "")).path
            if not re.fullmatch(r"/devtools/page/[A-Za-z0-9_.-]+", debug_path):
                raise RuntimeError("Browser returned an invalid debugging target.")
            try:
                ws = websocket.create_connection(
                    "ws://127.0.0.1:" + port + debug_path, timeout=4, suppress_origin=True
                )
                try:
                    ws.send(json.dumps({
                        "id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": EXPRESSION, "returnByValue": True,
                                   "userGesture": True, "awaitPromise": True},
                    }))
                    while True:
                        reply = json.loads(ws.recv())
                        if reply.get("id") == 1:
                            break
                finally:
                    ws.close()
            except websocket.WebSocketTimeoutException:
                return False
            except (websocket.WebSocketException, OSError) as error:
                raise RuntimeError("Browser full-screen connection failed: " + str(error)) from error
            if "error" in reply or reply.get("result", {}).get("exceptionDetails"):
                raise RuntimeError("The browser could not start full-screen playback.")
            value = reply.get("result", {}).get("result", {}).get("value", {})
            if not isinstance(value, dict):
                raise RuntimeError("The browser returned an invalid player response.")
            if value.get("ready"):
                if not value.get("fullscreen"):
                    raise RuntimeError("The browser did not enter full screen.")
                return True
        return False
    finally:
        removed = run_adb("forward", "--remove", "tcp:" + port)
        if removed.returncode != 0:
            raise RuntimeError((removed.stderr or removed.stdout).strip() or "Could not remove ADB forwarding.")
