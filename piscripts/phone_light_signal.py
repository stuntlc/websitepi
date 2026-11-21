#!/usr/bin/env python3
"""Control the phone flashlight for Morse and strobe signals."""
import json
import logging
import os
from pathlib import Path
import re
import signal
import socketserver
import subprocess
import sys
import threading


SOCKET = "/run/websitepi-light/control.sock"
MARKER = Path("/run/websitepi-light/active")
TORCH = "/sys/class/leds/flashlight/brightness"
MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}
UNIT = 0.25


def pulses(message):
    words = message.upper().split()
    if not words or len(message) > 100 or not re.fullmatch(r"[A-Za-z0-9 ]+", message):
        raise ValueError("Use 1-100 English letters, digits and spaces.")
    for wi, word in enumerate(words):
        if wi:
            yield False, 7 * UNIT
        for ci, letter in enumerate(word):
            if ci:
                yield False, 3 * UNIT
            for si, symbol in enumerate(MORSE[letter]):
                if si:
                    yield False, UNIT
                yield True, UNIT if symbol == "." else 3 * UNIT


def set_light(on):
    command = [os.environ.get("ADB", "adb")]
    serial = os.environ.get("PHONE_ADB_SERIAL", "SOEUDQIBF6ZLXK75")
    if serial:
        command.extend(["-s", serial])
    command.extend(["shell", "echo %d > %s" % (1 if on else 0, TORCH)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=8)
    if result.returncode or result.stderr.strip():
        raise RuntimeError((result.stderr or result.stdout).strip() or "ADB flashlight command failed.")


def cleanup_marker(marker=MARKER):
    if marker.exists():
        set_light(False)
        marker.unlink()


class Controller:
    def __init__(self, marker=MARKER):
        self.lock = threading.Lock()
        self.operation_lock = threading.RLock()
        self.marker = marker
        self.stop_event = threading.Event()
        self.thread = None
        self.mode = None
        self.error = None
        self.ready = threading.Event()

    def status(self):
        with self.lock:
            return {"ok": True, "mode": self.mode, "error": self.error}

    def start(self, mode, message=""):
        with self.operation_lock:
            return self._start(mode, message)

    def _start(self, mode, message):
        if mode not in ("strobe", "morse"):
            raise ValueError("Unknown flashlight mode.")
        if mode == "morse":
            sequence = list(pulses(message))
        else:
            sequence = None
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError("A flashlight signal is already running. Stop it first.")
            self.stop_event.clear()
            self.ready.clear()
            self.error = None
            self.mode = mode
            self.thread = threading.Thread(target=self.worker, args=(sequence,), daemon=True)
            self.thread.start()
        if not self.ready.wait(10):
            self.stop()
            raise RuntimeError("Flashlight did not start in time.")
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
        return self.status()

    def worker(self, sequence):
        failure = None
        try:
            with self.marker.open("x", encoding="ascii") as marker:
                marker.write("active\n")
            if sequence is None:
                while not self.stop_event.is_set():
                    set_light(True)
                    self.ready.set()
                    if self.stop_event.wait(UNIT):
                        break
                    set_light(False)
                    if self.stop_event.wait(UNIT):
                        break
            else:
                for on, delay in sequence:
                    if self.stop_event.is_set():
                        break
                    set_light(on)
                    self.ready.set()
                    if self.stop_event.wait(delay):
                        break
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            failure = "Flashlight signal failed: " + str(error)
            logging.error("%s", failure)
        finally:
            try:
                set_light(False)
                self.marker.unlink(missing_ok=True)
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                detail = "Could not turn the flashlight off: " + str(error)
                failure = (failure + " " if failure else "") + detail
                logging.error("%s", detail)
            with self.lock:
                self.mode = None
                self.error = failure
                self.ready.set()

    def stop(self):
        with self.operation_lock:
            return self._stop()

    def _stop(self):
        with self.lock:
            thread = self.thread
            if not thread or not thread.is_alive():
                set_light(False)
                self.marker.unlink(missing_ok=True)
                self.error = None
                return {"ok": True, "mode": None, "error": None}
            self.stop_event.set()
        thread.join(timeout=20)
        if thread.is_alive():
            raise RuntimeError("Flashlight did not stop in time.")
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
        return self.status()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            raw = self.rfile.readline(2049)
            if len(raw) > 2048 or not raw.endswith(b"\n"):
                raise ValueError("Invalid request.")
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("Invalid request.")
            action = request.get("action")
            if action == "status" and set(request) == {"action"}:
                response = self.server.controller.status()
            elif action == "stop" and set(request) == {"action"}:
                response = self.server.controller.stop()
            elif action == "start" and set(request) == {"action", "mode", "message"}:
                if not isinstance(request["message"], str):
                    raise ValueError("Invalid message.")
                response = self.server.controller.start(request["mode"], request["message"])
            else:
                raise ValueError("Invalid action.")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            response = {"ok": False, "error": str(error)}
        self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main():
    path = Path(SOCKET)
    if path.exists() or path.is_symlink():
        raise RuntimeError("Flashlight control socket already exists.")
    controller = Controller()
    shutdown = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, frame: shutdown.set())
    with Server(SOCKET, Handler) as server:
        os.chmod(SOCKET, 0o600)
        server.controller = controller
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            shutdown.wait()
        finally:
            try:
                if controller.status()["mode"]:
                    controller.stop()
            finally:
                server.shutdown()
                thread.join()
                path.unlink()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if sys.argv[1:] == ["--cleanup"]:
        cleanup_marker()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Unknown argument.")
