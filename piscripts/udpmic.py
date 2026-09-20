#!/usr/bin/env python3
"""Receive raw PCM mic audio over UDP from the phone app and rebroadcast it as an MP3 HTTP stream."""
import http.server
import socket
import socketserver
import subprocess
import threading

UDP_PORT = 9100
HTTP_PORT = 9101
SAMPLE_RATE = 16000

clients_lock = threading.Lock()
clients = []


def udp_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
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
        proc = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-fflags", "nobuffer", "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-",
                "-c:a", "libmp3lame", "-b:a", "64k", "-write_xing", "0", "-flush_packets", "1",
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


if __name__ == "__main__":
    threading.Thread(target=udp_receiver, daemon=True).start()
    with ThreadingHTTPServer(("", HTTP_PORT), StreamHandler) as httpd:
        httpd.serve_forever()
