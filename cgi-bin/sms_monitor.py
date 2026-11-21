#!/usr/bin/env python3
"""Start the SMS monitor through its restricted systemd socket."""
import socket
import subprocess
import sys


SOCKET_PATH = "/run/websitepi/sms-monitor.sock"


def active():
    result = subprocess.run(
        ["/bin/systemctl", "is-active", "--quiet", "smschecker.service"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def main():
    try:
        if not active():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(25)
                connection.connect(SOCKET_PATH)
                connection.shutdown(socket.SHUT_WR)
                while connection.recv(1024):
                    pass
            if not active():
                raise RuntimeError("SMS monitor did not start; check its service log.")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("ERROR: Could not start SMS monitor: " + str(error))
        return 1
    print("SMS monitor is running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
