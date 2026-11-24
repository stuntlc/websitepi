"""HTTPS client access history and manually maintained deployment inventory."""
import json
import os
import sqlite3
import sys
import time
from contextlib import closing

from security_access import CLIENTS_PATH, FINGERPRINT, MAC
from websitepi_paths import log_directory


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_PATH = os.path.join(log_directory(ROOT), "security-access.sqlite3")
DEPLOYMENTS_PATH = "/etc/websitepi-sec/client-deployments.json"
RETENTION = 30 * 24 * 60 * 60


def connect():
    connection = sqlite3.connect(AUDIT_PATH, timeout=10)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS events (time INTEGER NOT NULL, outcome TEXT NOT NULL, "
        "ip TEXT NOT NULL, mac TEXT NOT NULL, fingerprint TEXT NOT NULL, browser TEXT NOT NULL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS events_time ON events(time)")
    return connection


def record(outcome, ip, mac="", fingerprint="", browser=""):
    now = int(time.time())
    with closing(connect()) as connection:
        with connection:
            connection.execute("DELETE FROM events WHERE time < ?", (now - RETENTION,))
            connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                               (now, outcome, ip[:64], mac or "", fingerprint, browser[:256]))


def inventory():
    with open(CLIENTS_PATH, encoding="utf-8") as handle:
        clients = json.load(handle)
    if not isinstance(clients, dict) or any(
        not isinstance(key, str) or not FINGERPRINT.fullmatch(key) or
        not isinstance(mac, str) or not MAC.fullmatch(mac) for key, mac in clients.items()
    ):
        raise ValueError("Invalid client-certificate inventory.")
    with open(DEPLOYMENTS_PATH, encoding="utf-8") as handle:
        deployments = json.load(handle)
    if not isinstance(deployments, dict) or any(
        key not in clients or not isinstance(value, list) or
        any(not isinstance(item, str) or not item or len(item) > 100 for item in value) or
        len(value) != len(set(value)) for key, value in deployments.items()
    ):
        raise ValueError("Invalid client deployment inventory.")
    return [{"fingerprint": key, "mac": mac, "browsers": deployments.get(key, [])}
            for key, mac in sorted(clients.items())]


def history():
    with closing(connect()) as connection:
        with connection:
            connection.execute("DELETE FROM events WHERE time < ?", (int(time.time()) - RETENTION,))
            rows = connection.execute(
                "SELECT time, outcome, ip, mac, fingerprint, browser FROM events ORDER BY time DESC, rowid DESC LIMIT 100"
            ).fetchall()
    return [dict(zip(("time", "outcome", "ip", "mac", "fingerprint", "browser"), row)) for row in rows]


if __name__ == "__main__":
    if sys.argv[1:] != ["prune"]:
        raise SystemExit("Use: security_audit.py prune")
    history()
