#!/usr/bin/env python3
"""Account for IPv4 traffic forwarded from the LAN to the phone USB link."""
import ipaddress
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time
import uuid


CHAIN = "WPI_SEC_U_52B7"
STATE = "/var/lib/websitepi-sec/usage.json"
INTERVAL = 10
TAG = "wpi-sec"


def command(*args, check=True):
    result = subprocess.run(
        ["/usr/sbin/iptables", "-w", "5"] + list(args),
        capture_output=True, text=True, timeout=10,
    )
    if check and result.returncode:
        raise RuntimeError("iptables failed: " + (result.stderr.strip() or str(result.returncode)))
    return result


def parse_neighbors(text):
    neighbors = {}
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 6 or fields[5] != "eth0":
            continue
        try:
            if not int(fields[2], 16) & 2:
                continue
            address = ipaddress.IPv4Address(fields[0])
        except ValueError:
            continue
        mac = fields[3].upper()
        if (address.is_multicast or address.is_unspecified or
                not re.fullmatch(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", mac) or
                int(mac[:2], 16) & 1 or mac == "00:00:00:00:00:00"):
            continue
        neighbors[str(address)] = mac
    return neighbors


def parse_rules(text):
    rules = {}
    seen = set()
    for line in text.splitlines():
        if not re.match(r"^\[\d+:\d+\] -A " + re.escape(CHAIN) + r" ", line):
            continue
        parts = shlex.split(line)
        try:
            counter = int(parts[0][1:-1].split(":")[1])
            tag = parts[parts.index("--comment") + 1]
            prefix, direction, mac, address, token = tag.split("|")
            if prefix != TAG or direction not in ("up", "down"):
                raise ValueError("invalid tag")
            if not re.fullmatch(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", mac):
                raise ValueError("invalid MAC")
            ipaddress.IPv4Address(address)
            if not re.fullmatch(r"[0-9a-f]{12}", token):
                raise ValueError("invalid token")
            args = parts[3:]
            expected = {
                "-i": "eth0" if direction == "up" else "usb0",
                "-o": "usb0" if direction == "up" else "eth0",
                "-s" if direction == "up" else "-d": address + "/32",
                "--comment": tag,
            }
            if direction == "up":
                expected["--mac-source"] = mac.lower()
            options = {}
            modules = []
            if len(args) % 2:
                raise ValueError("invalid arguments")
            for index in range(0, len(args), 2):
                key, value = args[index:index + 2]
                if key == "-m":
                    modules.append(value)
                elif key in options:
                    raise ValueError("duplicate argument")
                else:
                    options[key] = value.lower() if key == "--mac-source" else value
            if options != expected or sorted(modules) != (["comment", "mac"] if direction == "up" else ["comment"]):
                raise ValueError("unsafe rule")
            identity = (address, direction) if direction == "down" else (address, direction, mac)
            if identity in seen:
                raise ValueError("duplicate identity")
            seen.add(identity)
        except (ValueError, IndexError) as error:
            raise RuntimeError("Unexpected rule in security accounting chain") from error
        if tag in rules:
            raise RuntimeError("Duplicate security accounting rule")
        rules[tag] = {
            "direction": direction, "mac": mac, "ip": address,
            "bytes": counter, "args": args,
        }
    return rules


def update_totals(state, rules):
    previous = state["last_counters"]
    for tag, rule in rules.items():
        last = previous.get(tag, 0)
        current = rule["bytes"]
        delta = current - last if current >= last else current
        device = state["devices"].setdefault(rule["mac"], {"up_bytes": 0, "down_bytes": 0, "ip": rule["ip"]})
        device[rule["direction"] + "_bytes"] += delta
        device["ip"] = rule["ip"]
    state["last_counters"] = {tag: rule["bytes"] for tag, rule in rules.items()}


def load_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        return {"started_at": int(time.time()), "updated_at": 0, "devices": {}, "last_counters": {}}
    if not isinstance(state, dict) or not isinstance(state.get("devices"), dict) or not isinstance(state.get("last_counters"), dict):
        raise ValueError("Invalid security usage state")
    return state


def save_state(path, state):
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix=".usage-", dir=directory)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot():
    result = subprocess.run(
        ["/usr/sbin/iptables-save", "-c", "-t", "filter"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode:
        raise RuntimeError("iptables-save failed: " + result.stderr.strip())
    return result.stdout


def initialize():
    saved = snapshot()
    rules = parse_rules(saved)
    if not re.search(r"(?m)^:" + re.escape(CHAIN) + r" ", saved):
        command("-N", CHAIN)
    elif not rules and re.search(r"(?m)^\[\d+:\d+\] -A " + re.escape(CHAIN) + r" ", saved):
        raise RuntimeError("Security accounting chain contains unknown rules")
    result = command("-C", "FORWARD", "-j", CHAIN, check=False)
    if result.returncode:
        if result.stderr and "Bad rule" not in result.stderr:
            raise RuntimeError("Unable to check accounting jump: " + result.stderr.strip())
        command("-I", "FORWARD", "1", "-j", CHAIN)


def reconcile(neighbors, rules):
    for rule in rules.values():
        if rule["ip"] in neighbors and neighbors[rule["ip"]] != rule["mac"]:
            command("-D", CHAIN, *rule["args"])
    existing = {(rule["ip"], rule["mac"], rule["direction"]) for rule in rules.values()}
    for address, mac in neighbors.items():
        for direction in ("up", "down"):
            if (address, mac, direction) in existing:
                continue
            tag = "|".join((TAG, direction, mac, address, uuid.uuid4().hex[:12]))
            if direction == "up":
                args = ["-i", "eth0", "-o", "usb0", "-s", address,
                        "-m", "mac", "--mac-source", mac]
            else:
                args = ["-i", "usb0", "-o", "eth0", "-d", address]
            command("-A", CHAIN, *args, "-m", "comment", "--comment", tag)


def tick(state):
    rules = parse_rules(snapshot())
    update_totals(state, rules)
    with open("/proc/net/arp", encoding="ascii") as handle:
        neighbors = parse_neighbors(handle.read())
    if any(rule["ip"] in neighbors and neighbors[rule["ip"]] != rule["mac"] for rule in rules.values()):
        save_state(STATE, state)
    reconcile(neighbors, rules)
    state["updated_at"] = int(time.time())
    save_state(STATE, state)


def main():
    import fcntl

    lock = open("/run/websitepi-security-usage.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = load_state(STATE)
    initialize()
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        tick(state)
        for _ in range(INTERVAL):
            if stopping:
                break
            time.sleep(1)
    rules = parse_rules(snapshot())
    update_totals(state, rules)
    state["updated_at"] = int(time.time())
    save_state(STATE, state)


if __name__ == "__main__":
    main()
