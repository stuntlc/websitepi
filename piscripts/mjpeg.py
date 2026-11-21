#!/usr/bin/env python3
import http.server
import shutil
import socketserver
import subprocess


def camera_command():
    for command in ("rpicam-vid", "libcamera-vid"):
        path = shutil.which(command)
        if path:
            return path
    raise RuntimeError("Camera command unavailable: install rpicam-apps or libcamera-apps")

class MJPEGHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            cmd = [
                camera_command(),
                "-t", "0",
                "--codec", "mjpeg",
                "--width", "640",
                "--height", "480",
                "--framerate", "15",
                "--nopreview",
                "-o", "-"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        except (OSError, RuntimeError) as error:
            self.send_error(503, str(error))
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            data = b""
            while True:
                chunk = proc.stdout.read(1024)
                if not chunk:
                    break
                data += chunk
                start = data.find(b"\xff\xd8")
                end = data.find(b"\xff\xd9", max(start, 0))
                if start != -1 and end != -1 and end > start:
                    frame = data[start:end + 2]
                    data = data[end + 2:]
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class MJPEGServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with MJPEGServer(("127.0.0.1", 8000), MJPEGHandler) as httpd:
        httpd.serve_forever()
