#!/usr/bin/env python3
import http.server, socketserver, subprocess

class MJPEGHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        cmd = [
                "rpicam-vid",
                "-t", "0",
                "--codec", "mjpeg",
                "--width", "640",
                "--height", "480",
                "--framerate", "15",
                "--nopreview",
                "-o", "-"
]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

        data = b""
        while True:
            chunk = proc.stdout.read(1024)
            if not chunk:
                break
            data += chunk

            # JPEG start and end markers
            start = data.find(b"\xff\xd8")
            end = data.find(b"\xff\xd9")

            if start != -1 and end != -1 and end > start:
                frame = data[start:end+2]
                data = data[end+2:]

                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")

PORT = 8000
with socketserver.TCPServer(("", PORT), MJPEGHandler) as httpd:
    httpd.serve_forever()
