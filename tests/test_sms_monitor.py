"""Tests for the restricted SMS monitor start request."""
import contextlib
import io
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cgi-bin"))
import sms_monitor


class SmsMonitorTests(unittest.TestCase):
    def test_running_monitor_does_not_contact_broker(self):
        output = io.StringIO()
        with mock.patch.object(sms_monitor, "active", return_value=True), \
                mock.patch.object(sms_monitor.socket, "socket") as create_socket, \
                contextlib.redirect_stdout(output):
            self.assertEqual(sms_monitor.main(), 0)
        create_socket.assert_not_called()
        self.assertIn("SMS monitor is running", output.getvalue())

    def test_stopped_monitor_requests_start_and_verifies_result(self):
        connection = mock.MagicMock()
        connection.recv.return_value = b""
        create_socket = mock.MagicMock()
        create_socket.return_value.__enter__.return_value = connection
        output = io.StringIO()
        with mock.patch.object(sms_monitor, "active", side_effect=[False, True]), \
                mock.patch.object(sms_monitor.socket, "socket", create_socket), \
                contextlib.redirect_stdout(output):
            self.assertEqual(sms_monitor.main(), 0)
        create_socket.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.connect.assert_called_once_with(sms_monitor.SOCKET_PATH)
        connection.shutdown.assert_called_once_with(socket.SHUT_WR)
        self.assertIn("SMS monitor is running", output.getvalue())

    def test_broker_error_or_failed_start_is_reported(self):
        for error in (FileNotFoundError("broker unavailable"), subprocess.TimeoutExpired("systemctl", 10)):
            output = io.StringIO()
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(sms_monitor, "active", side_effect=error), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(sms_monitor.main(), 1)
            self.assertIn("ERROR: Could not start SMS monitor", output.getvalue())

        connection = mock.MagicMock()
        connection.recv.return_value = b""
        output = io.StringIO()
        with mock.patch.object(sms_monitor, "active", side_effect=[False, False]), \
                mock.patch.object(sms_monitor.socket, "socket") as create_socket, \
                contextlib.redirect_stdout(output):
            create_socket.return_value.__enter__.return_value = connection
            self.assertEqual(sms_monitor.main(), 1)
        self.assertIn("SMS monitor did not start", output.getvalue())
