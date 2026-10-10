#!/usr/bin/env python3
"""Current GPS fix and satellite info from gpsd (JSON protocol on localhost:2947)."""
import json
import socket
import time

HOST, PORT = "127.0.0.1", 2947


def respond(payload, status=None):
    if status:
        print("Status: " + status)
    print("Content-Type: application/json; charset=utf-8")
    print("Cache-Control: no-store")
    print()
    print(json.dumps(payload))


def read_gpsd(timeout=4.0):
    tpv = sky = None
    deadline = time.time() + timeout
    with socket.create_connection((HOST, PORT), timeout=2) as conn:
        conn.sendall(b'?WATCH={"enable":true,"json":true}\n')
        conn.settimeout(1)
        buffer = b""
        while time.time() < deadline and not (tpv and sky):
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("class") == "TPV":
                    tpv = msg
                elif msg.get("class") == "SKY" and "satellites" in msg:
                    sky = msg
    return tpv, sky


try:
    tpv, sky = read_gpsd()
except OSError as error:
    respond({"ok": False, "error": "gpsd unreachable: " + str(error)}, "502 Bad Gateway")
    raise SystemExit

tpv = tpv or {}
sky = sky or {}
sats = sky.get("satellites", [])
speed = tpv.get("speed")
respond({
    "ok": True,
    "mode": tpv.get("mode", 0),
    "lat": tpv.get("lat"),
    "lon": tpv.get("lon"),
    "alt": tpv.get("altHAE", tpv.get("alt")),
    "speed_kmh": round(speed * 3.6, 1) if speed is not None else None,
    "track": tpv.get("track"),
    "climb": tpv.get("climb"),
    "time": tpv.get("time"),
    "eph": tpv.get("eph", tpv.get("epx")),
    "epv": tpv.get("epv"),
    "hdop": sky.get("hdop"),
    "vdop": sky.get("vdop"),
    "pdop": sky.get("pdop"),
    "sats_seen": len(sats),
    "sats_used": sum(1 for s in sats if s.get("used")),
    "satellites": [
        {k: s.get(k) for k in ("PRN", "gnssid", "el", "az", "ss", "used")}
        for s in sats
    ],
})
