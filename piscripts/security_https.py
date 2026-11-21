#!/usr/bin/env python3
"""HTTPS website listener with authenticated local camera and audio proxies."""
import http.server
import http.client
import hashlib
import errno
import os
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cgi-bin"))
from security_access import authorized, same_origin
from systemd_listener import activated_server


STREAMS = {
    "/secure-stream/live": ("http://127.0.0.1:8000/", "multipart/x-mixed-replace"),
    "/secure-stream/udp": ("http://127.0.0.1:9101/", "audio/mpeg"),
}


class ThreadingTlsServer(http.server.ThreadingHTTPServer):
    def process_request_thread(self, request, client_address):
        try:
            request.settimeout(10)
            connection = self.tls_context.wrap_socket(request, server_side=True)
            connection.settimeout(None)
        except (OSError, ssl.SSLError) as error:
            print("TLS handshake failed: " + str(error), file=sys.stderr)
            request.close()
            return
        super().process_request_thread(connection, client_address)

    def shutdown_request(self, request):
        try:
            request.settimeout(1)
            connection = request.unwrap()
        except (OSError, ssl.SSLError):
            request.close()
        else:
            connection.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    def access_environ(self):
        certificate = self.connection.getpeercert(binary_form=True)
        return {
            "WEBSITEPI_SEC_TLS": "1",
            "WEBSITEPI_SEC_CLIENT_SHA256": hashlib.sha256(certificate).hexdigest() if certificate else "",
            "REMOTE_ADDR": self.client_address[0],
            "HTTP_HOST": self.headers.get("Host", ""),
            "HTTP_ORIGIN": self.headers.get("Origin", ""),
            "HTTP_SEC_FETCH_SITE": self.headers.get("Sec-Fetch-Site", ""),
        }

    def require_access(self):
        try:
            if same_origin(self.access_environ()) and authorized(self.access_environ()):
                return True
        except (OSError, ValueError, RuntimeError) as error:
            self.send_error(503, "SEC access check failed: " + str(error))
            return False
        self.send_error(403, "Trusted client certificate and device required")
        return False

    def request_origin_allowed(self):
        return same_origin({
            "WEBSITEPI_SEC_TLS": "1",
            "HTTP_HOST": self.headers.get("Host", ""),
            "HTTP_ORIGIN": self.headers.get("Origin", ""),
            "HTTP_SEC_FETCH_SITE": self.headers.get("Sec-Fetch-Site", ""),
        })

    def do_GET(self):
        if not self.request_origin_allowed():
            self.send_error(403, "Cross-origin requests are not allowed")
            return
        if not self.require_access():
            return
        path = urllib.parse.urlsplit(self.path).path
        decoded_path = urllib.parse.unquote(path)
        if self.private_static_path(decoded_path):
            self.send_error(404)
            return
        if decoded_path.startswith(("/cgi-bin/", "/media/")) and decoded_path != path:
            self.send_error(404)
            return
        if path.startswith("/cgi-bin/"):
            return self.run_cgi()
        if path.startswith("/media/"):
            return self.serve_media(path)
        if path not in STREAMS:
            return super().do_GET()
        target, expected_type = STREAMS[path]
        try:
            upstream = urllib.request.urlopen(target, timeout=15)
            content_type = upstream.headers.get("Content-Type", "")
            if not content_type.lower().startswith(expected_type):
                upstream.close()
                raise ValueError("Unexpected local stream response")
        except (OSError, ValueError, urllib.error.URLError) as error:
            self.send_error(502, "Local stream unavailable: " + str(error))
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            with upstream:
                while True:
                    chunk = upstream.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_POST(self):
        if not self.request_origin_allowed():
            self.send_error(403, "Cross-origin requests are not allowed")
            return
        if not self.require_access():
            return
        if not urllib.parse.urlsplit(self.path).path.startswith("/cgi-bin/"):
            self.send_error(404)
            return
        return self.run_cgi()

    def do_HEAD(self):
        raw_path = urllib.parse.urlsplit(self.path).path
        path = urllib.parse.unquote(raw_path)
        if not self.request_origin_allowed() or self.private_static_path(path) or path.startswith("/cgi-bin"):
            self.send_error(404)
            return
        if not self.require_access():
            return
        if path.startswith("/media/"):
            if raw_path != path:
                self.send_error(404)
                return
            return self.serve_media(path, head=True)
        return super().do_HEAD()

    def serve_media(self, path, head=False):
        name = path[len("/media/"):]
        if not re.fullmatch(r"(?:[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.jpe?g|latest\.txt)", name,
                            flags=re.IGNORECASE):
            self.send_error(404)
            return
        try:
            fd = os.open(os.path.join(self.server.media_directory, name),
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ELOOP):
                self.send_error(404)
            else:
                self.send_error(503, "Media unavailable: " + str(error))
            return
        with os.fdopen(fd, "rb") as media:
            info = os.fstat(media.fileno())
            if not stat.S_ISREG(info.st_mode):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8" if name == "latest.txt" else "image/jpeg")
            self.send_header("Content-Length", str(info.st_size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                self.copyfile(media, self.wfile)

    @staticmethod
    def private_static_path(path):
        parts = path.replace("\\", "/").split("/")
        return any(part.startswith(".") for part in parts if part) or any(
            part in ("logs", "piscripts", "tests") for part in parts
        ) or path.rstrip("/") == "/cgi-bin"

    def run_cgi(self):
        parsed = urllib.parse.urlsplit(self.path)
        name = urllib.parse.unquote(parsed.path[len("/cgi-bin/"):])
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
            self.send_error(404)
            return
        directory = os.path.realpath(os.path.join(ROOT, "cgi-bin"))
        script = os.path.realpath(os.path.join(directory, name))
        if os.path.dirname(script) != directory or not os.path.isfile(script) or not os.access(script, os.X_OK):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1024 * 1024:
                raise ValueError
        except ValueError:
            self.send_error(400, "Invalid request length")
            return
        environ = {key: value for key, value in os.environ.items()
                   if not key.startswith("HTTP_") and not key.startswith("WEBSITEPI_SEC_")}
        environ.update(self.access_environ())
        environ.update({
            "REQUEST_METHOD": self.command,
            "QUERY_STRING": parsed.query,
            "SCRIPT_NAME": parsed.path,
            "SERVER_NAME": self.server.server_name,
            "SERVER_PORT": str(self.server.server_port),
            "SERVER_PROTOCOL": self.request_version,
            "GATEWAY_INTERFACE": "CGI/1.1",
            "REMOTE_ADDR": self.client_address[0],
            "CONTENT_LENGTH": str(length),
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "HTTP_COOKIE": self.headers.get("Cookie", ""),
            "HTTP_HOST": self.headers.get("Host", ""),
            "HTTP_ORIGIN": self.headers.get("Origin", ""),
            "HTTP_REFERER": self.headers.get("Referer", ""),
            "HTTP_SEC_FETCH_SITE": self.headers.get("Sec-Fetch-Site", ""),
        })
        with tempfile.TemporaryFile() as body:
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    self.send_error(400, "Incomplete request body")
                    return
                body.write(chunk)
                remaining -= len(chunk)
            body.seek(0)
            try:
                process = subprocess.Popen([script], stdin=body, stdout=subprocess.PIPE, env=environ)
            except OSError as error:
                self.send_error(500, "Could not start CGI: " + str(error))
                return
            try:
                headers = http.client.parse_headers(process.stdout)
                status = headers.get("Status", "200 OK").split(" ", 1)
                code = int(status[0])
                if not 100 <= code <= 599 or not headers.get("Content-Type"):
                    raise ValueError("Invalid CGI response")
                self.send_response(code, status[1] if len(status) > 1 else None)
                for key, value in headers.items():
                    if key.lower() not in ("status", "connection", "transfer-encoding"):
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                while True:
                    chunk = process.stdout.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (ValueError, http.client.HTTPException) as error:
                self.send_error(502, "Invalid CGI response: " + str(error))
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                process.wait()


def tls_context(server_cert, server_key, client_ca):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(server_cert, server_key)
    context.load_verify_locations(cafile=client_ca)
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def main():
    if os.environ.get("WEBSITEPI_SEC_TLS") != "1":
        raise RuntimeError("HTTPS service marker is missing")
    os.chdir(ROOT)
    context = tls_context("/etc/websitepi-sec/tls/server.crt", "/etc/websitepi-sec/tls/server.key",
                          "/etc/websitepi-sec/tls/client-ca.crt")
    media_directory = os.environ.get("WEBSITEPI_MEDIA_DIR", "")
    if not os.path.isabs(media_directory) or not os.path.isdir(media_directory):
        raise RuntimeError("WEBSITEPI_MEDIA_DIR must be an existing absolute directory")
    server = activated_server(Handler, 443, ThreadingTlsServer)
    server.media_directory = media_directory
    server.tls_context = context
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
