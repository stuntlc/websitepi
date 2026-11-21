"""Test the fixed HTTPS redirect without exposing HTTP content."""
import http.client
from pathlib import Path
import sys
import threading
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piscripts"))
import security_redirect


class RedirectTests(unittest.TestCase):
    def test_only_valid_hostnames_are_accepted(self):
        self.assertEqual(security_redirect.https_url("pi.example.org"), "https://pi.example.org/")
        for host in ("", "evil.example/path", "user@evil.example", "evil.example:443", "-bad.example"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                security_redirect.https_url(host)

    def test_redirect_ignores_host_and_path_and_does_not_redirect_post(self):
        server = security_redirect.http.server.ThreadingHTTPServer(("127.0.0.1", 0), security_redirect.Handler)
        server.https_url = security_redirect.https_url("pi.example.org")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for method, status in (("GET", 302), ("HEAD", 302), ("POST", 501)):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request(method, "/secret?value=example", headers={"Host": "attacker.example"})
                response = connection.getresponse()
                self.assertEqual(response.status, status)
                if status == 302:
                    self.assertEqual(response.getheader("Location"), "https://pi.example.org/")
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                    self.assertEqual(response.read(), b"")
                else:
                    self.assertIsNone(response.getheader("Location"))
                    response.read()
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
