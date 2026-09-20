#!/usr/bin/env python3
"""Receive raw PCM mic audio over UDP from the phone app and rebroadcast it as an MP3 HTTP stream."""
import http.server
import socket
import socketserver
import subprocess
import sys
import threading

UDP_PORT = 9100
HTTP_PORT = 9101
SAMPLE_RATE = 16000

clients_lock = threading.Lock()
clients = []


def udp_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", UDP_PORT))
    except OSError as error:
        print(f"udp bind failed on {UDP_PORT}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
    while True:
        data, _ = sock.recvfrom(4096)
        with clients_lock:
            dead = []
            for proc in clients:
                try:
                    proc.stdin.write(data)
                    proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    dead.append(proc)
            for proc in dead:
                clients.remove(proc)


class StreamHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        # Each listener gets its own ffmpeg encoder fed the same raw PCM fan-out.
        # Output is resampled to 44.1kHz so the MP3 is standard MPEG-1 Layer III;
        # encoding directly at 16kHz needs MPEG-2 LSF, which some Android decoders
        # accept but play back silently.
        proc = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-fflags", "nobuffer", "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-",
                "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "64k", "-write_xing", "0", "-flush_packets", "1",
                "-f", "mp3", "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        with clients_lock:
            clients.append(proc)
        try:
            while True:
                chunk = proc.stdout.read(1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with clients_lock:
                if proc in clients:
                    clients.remove(proc)
            proc.stdin.close()
            proc.kill()

    def log_message(self, format, *args):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    threading.Thread(target=udp_receiver, daemon=True).start()
    try:
        with ThreadingHTTPServer(("", HTTP_PORT), StreamHandler) as httpd:
            httpd.serve_forever()
    except OSError as error:
        print(f"http bind failed on {HTTP_PORT}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
