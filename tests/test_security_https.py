"""HTTPS CGI transport tests; Linux runs executable CGI scripts."""
import http.client
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cgi-bin"))
sys.path.insert(0, str(ROOT / "piscripts"))
import security_https


@unittest.skipIf(os.name == "nt", "CGI executable scripts require Linux")
class HttpsCgiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        directory = Path(self.temporary.name)
        cgi = directory / "cgi-bin"
        cgi.mkdir()
        script = cgi / "fixture.cgi"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "print('Status: 201 Created')\n"
            "print('Content-Type: application/json')\n"
            "print('Set-Cookie: fixture=ok; Secure')\n"
            "print()\n"
            "print(json.dumps({'body': sys.stdin.read(), 'tls': os.environ['WEBSITEPI_SEC_TLS'], "
            "'fingerprint': os.environ['WEBSITEPI_SEC_CLIENT_SHA256'], "
            "'origin': os.environ['HTTP_ORIGIN'], 'referer': os.environ['HTTP_REFERER'], "
            "'remote': os.environ['REMOTE_ADDR']}))\n",
            encoding="utf-8",
        )
        script.chmod(0o755)
        cert, key = directory / "cert.pem", directory / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec",
                        "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                        "-keyout", str(key), "-out", str(cert), "-days", "1",
                        "-subj", "/CN=localhost"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.client_key = directory / "client.key"
        self.client_cert = directory / "client.crt"
        request = directory / "client.csr"
        subprocess.run(["openssl", "req", "-new", "-newkey", "ec",
                        "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                        "-keyout", str(self.client_key), "-out", str(request), "-subj", "/CN=test-client"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["openssl", "x509", "-req", "-in", str(request), "-CA", str(cert),
                        "-CAkey", str(key), "-CAcreateserial", "-out", str(self.client_cert), "-days", "1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.untrusted_key = directory / "untrusted.key"
        self.untrusted_cert = directory / "untrusted.crt"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec",
                        "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                        "-keyout", str(self.untrusted_key), "-out", str(self.untrusted_cert), "-days", "1",
                        "-subj", "/CN=untrusted-client"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        der = ssl.PEM_cert_to_DER_cert(self.client_cert.read_text(encoding="ascii"))
        self.fingerprint = hashlib.sha256(der).hexdigest()
        self.root_patch = mock.patch.object(security_https, "ROOT", str(directory))
        self.root_patch.start()
        self.access_patch = mock.patch.object(security_https, "authorized", return_value=True)
        self.access_patch.start()
        self.audit_patch = mock.patch.object(security_https, "record")
        self.audit = self.audit_patch.start()
        self.server = security_https.ThreadingTlsServer(("127.0.0.1", 0), security_https.Handler)
        self.media_directory = directory / "media"
        self.media_directory.mkdir()
        self.server.media_directory = str(self.media_directory)
        context = security_https.tls_context(str(cert), str(key), str(cert))
        self.server.tls_context = context
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.access_patch.stop()
        self.audit_patch.stop()
        self.root_patch.stop()
        self.temporary.cleanup()

    def request(self, method, path, body=None, headers=None, client_certificate=True):
        context = ssl._create_unverified_context()
        if client_certificate == "untrusted":
            context.load_cert_chain(str(self.untrusted_cert), str(self.untrusted_key))
        elif client_certificate:
            context.load_cert_chain(str(self.client_cert), str(self.client_key))
        connection = http.client.HTTPSConnection("127.0.0.1", self.server.server_port,
                                                  context=context, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheaders(), response.read()
        finally:
            connection.close()

    def test_cgi_response_and_post_body_are_transported_over_tls(self):
        origin = "https://127.0.0.1:{}".format(self.server.server_port)
        status, headers, body = self.request("POST", "/cgi-bin/fixture.cgi", "value=hello",
                                             {"Origin": origin, "Content-Type": "application/x-www-form-urlencoded",
                                              "Referer": origin + "/air.html",
                                              "Websitepi-Sec-Client-Sha256": "0" * 64})
        self.assertEqual(status, 201)
        self.assertIn(("Set-Cookie", "fixture=ok; Secure"), headers)
        self.assertEqual(json.loads(body), {"body": "value=hello", "tls": "1", "fingerprint": self.fingerprint,
                                           "origin": origin, "referer": origin + "/air.html", "remote": "127.0.0.1"})

    def test_missing_and_unapproved_clients_are_rejected(self):
        with self.assertRaises((ssl.SSLError, ConnectionResetError, http.client.RemoteDisconnected)):
            self.request("GET", "/cgi-bin/fixture.cgi", client_certificate=False)
        with self.assertRaises((ssl.SSLError, ConnectionResetError, http.client.RemoteDisconnected)):
            self.request("GET", "/cgi-bin/fixture.cgi", client_certificate="untrusted")
        with mock.patch.object(security_https, "authorized", return_value=False):
            self.assertEqual(self.request("GET", "/cgi-bin/fixture.cgi")[0], 403)
        self.assertEqual(self.audit.call_args.args[0], "denied")
        self.assertEqual(self.audit.call_args.args[3], self.fingerprint)

    def test_audit_failure_blocks_request(self):
        self.audit.side_effect = OSError("audit unavailable")
        self.assertEqual(self.request("GET", "/cgi-bin/fixture.cgi")[0], 503)

    def test_incomplete_handshake_does_not_block_another_client(self):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2):
            time.sleep(0.1)
            self.assertEqual(self.request("GET", "/cgi-bin/fixture.cgi")[0], 201)

    def test_cgi_response_ends_with_tls_close_notify(self):
        context = ssl._create_unverified_context()
        context.load_cert_chain(str(self.client_cert), str(self.client_key))
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname="localhost", suppress_ragged_eofs=False) as connection:
                connection.sendall(b"GET /cgi-bin/fixture.cgi HTTP/1.0\r\nHost: localhost\r\n\r\n")
                response = bytearray()
                while True:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    response.extend(chunk)
                self.assertIn(b"201 Created", response)
                connection.unwrap().close()

    def test_cross_origin_and_path_traversal_are_rejected(self):
        self.assertEqual(self.request("GET", "/cgi-bin/fixture.cgi", headers={"Origin": "https://elsewhere"})[0], 403)
        self.assertEqual(self.request("GET", "/cgi-bin/%2e%2e%2ffixture.cgi")[0], 404)
        self.assertEqual(self.request("GET", "/%63gi-bin/fixture.cgi")[0], 404)
        self.assertEqual(self.request("HEAD", "/cgi-bin/fixture.cgi")[0], 404)
        self.assertEqual(self.request("GET", "/logs/auth.json")[0], 404)

    def test_media_requires_authorization_and_rejects_symlinks_and_traversal(self):
        (self.media_directory / "photo.jpg").write_bytes(b"photo")
        (self.media_directory / "latest.txt").write_text("photo.jpg\n", encoding="utf-8")
        (self.media_directory / "secret.jpg").symlink_to(self.client_key)
        self.assertEqual(self.request("GET", "/media/photo.jpg")[2], b"photo")
        self.assertEqual(self.request("GET", "/media/latest.txt")[2], b"photo.jpg\n")
        self.assertEqual(self.request("HEAD", "/media/photo.jpg")[0], 200)
        self.assertEqual(self.request("GET", "/media/secret.jpg")[0], 404)
        self.assertEqual(self.request("GET", "/media/%2e%2e/client.key")[0], 404)
        self.assertEqual(self.request("GET", "/media/client.key")[0], 404)
        with mock.patch.object(security_https, "authorized", return_value=False):
            self.assertEqual(self.request("GET", "/media/photo.jpg")[0], 403)


if __name__ == "__main__":
    unittest.main()
