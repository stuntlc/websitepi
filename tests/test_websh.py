"""Tests for the isolated Pi WebShell."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from unittest import mock
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cgi-bin"))
import security_access


@unittest.skipIf(os.name == "nt", "Pi WebShell requires a POSIX shell")
class WebShellTests(unittest.TestCase):
    def run_pi_command(self, command, authorized=True):
        output = io.StringIO()
        env = dict(os.environ, REQUEST_METHOD="GET",
                   QUERY_STRING=urlencode({"target": "pi", "command": command}))
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(security_access, "authorized", return_value=authorized), \
                mock.patch.object(security_access, "same_origin", return_value=True), \
                contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(ROOT / "cgi-bin" / "websh.cgi"), run_name="__main__")
            except SystemExit as error:
                self.assertIn(error.code, (None, 0))
        return output.getvalue()

    def test_pi_commands_run_locally_without_ssh(self):
        original_run = subprocess.run
        with mock.patch("subprocess.run", wraps=original_run) as run:
            output = self.run_pi_command("printf websitepi-test")
        self.assertIn("websitepi-test", output)
        self.assertEqual(run.call_args.args[0][:2], ["/bin/sh", "-c"])

    def test_pi_command_failure_is_reported(self):
        self.assertIn("[exit status: 7]", self.run_pi_command("exit 7"))

    def test_pi_command_keeps_the_website_process_identity(self):
        output = self.run_pi_command("id -u")
        self.assertIn("\n%s\n" % os.geteuid(), output)

    def test_unauthorized_requests_cannot_run_commands(self):
        with mock.patch("subprocess.run") as run:
            output = self.run_pi_command("printf websitepi-test", authorized=False)
        self.assertIn("403 Forbidden", output)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
