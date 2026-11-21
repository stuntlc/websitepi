#!/usr/bin/env python3
"""Redirect bare HTTP navigation to the configured HTTPS site."""
import http.server
import os
import re

from systemd_listener import activated_server


def https_url(host):
    labels = host.split(".")
    if (len(host) > 253 or len(labels) < 2 or
            any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in labels)):
        raise ValueError("Invalid WEBSITEPI_HTTPS_HOST")
    return "https://" + host + "/"


class Handler(http.server.BaseHTTPRequestHandler):
    def redirect(self):
        self.send_response(302)
        self.send_header("Location", self.server.https_url)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = redirect
    do_HEAD = redirect


def main():
    url = https_url(os.environ.get("WEBSITEPI_HTTPS_HOST", ""))
    server = activated_server(Handler, 80)
    server.https_url = url
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
