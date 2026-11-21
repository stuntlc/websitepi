"""Read per-station Wi-Fi counters from the Realtek serial console."""
import os
import re
import subprocess
import time


PORT = "/dev/ttyUSB0"
RADIOS = ("wlan0", "wlan1")


def parse_stations(text):
    stations = []
    for radio in RADIOS:
        match = re.search(
            r"(?ms)^__%s__\r?\n(.*?)(?=^__(?:wlan[01]|END)__\r?$)" % radio,
            text,
        )
        if not match:
            raise ValueError("Missing station output for " + radio)
        section = match.group(1)
        header = re.search(r"-- STA info table -- \(active: (\d+)\)", section)
        if not header:
            raise ValueError("Invalid station output for " + radio)
        blocks = re.split(r"(?m)^\s*\d+: stat_info\.\.\.\s*$", section)[1:]
        if len(blocks) != int(header.group(1)):
            raise ValueError("Incomplete station output for " + radio)
        for block in blocks:
            mac = re.search(r"(?m)^\s*hwaddr:\s*([0-9a-fA-F]{12})\s*$", block)
            tx = re.search(r"(?m)^\s*tx_bytes:\s*(\d+)\s*$", block)
            rx = re.search(r"(?m)^\s*rx_bytes:\s*(\d+)\s*$", block)
            if not (mac and tx and rx):
                raise ValueError("Incomplete station counters for " + radio)
            value = mac.group(1).upper()
            stations.append({
                "radio": radio,
                "mac": ":".join(value[i:i + 2] for i in range(0, 12, 2)),
                "tx_bytes": int(tx.group(1)),
                "rx_bytes": int(rx.group(1)),
            })
    return stations


def read_wifi_counters():
    import fcntl
    import select
    import termios
    import tty

    def holders():
        result = subprocess.run(["fuser", PORT], capture_output=True, text=True, timeout=3)
        if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr.strip()):
            raise RuntimeError("Cannot check serial port: " + (result.stderr.strip() or "fuser failed"))
        return {int(pid) for pid in result.stdout.split()}

    def receive(fd, pattern, timeout):
        data = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if select.select([fd], [], [], min(0.25, deadline - time.monotonic()))[0]:
                try:
                    data.extend(os.read(fd, 8192))
                except BlockingIOError:
                    continue
                if len(data) > 131072:
                    raise RuntimeError("Serial response too large")
                if re.search(pattern, data):
                    return data.decode("utf-8", "replace")
        raise RuntimeError("Realtek serial console did not respond")

    fd = None
    original = None
    exclusive = False
    try:
        if holders():
            raise RuntimeError("Realtek serial console is in use")
        fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.ioctl(fd, termios.TIOCEXCL)
        exclusive = True
        if holders() - {os.getpid()}:
            raise RuntimeError("Realtek serial console is in use")
        original = termios.tcgetattr(fd)
        tty.setraw(fd)
        settings = termios.tcgetattr(fd)
        settings[4] = settings[5] = termios.B38400
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        termios.tcflush(fd, termios.TCIFLUSH)
        os.write(fd, b"\x15\r")
        receive(fd, rb"(?:^|[\r\n])# ?$", 3)
        termios.tcflush(fd, termios.TCIFLUSH)
        os.write(fd, b"echo __wlan0__; cat /proc/wlan0/sta_info; echo __wlan1__; cat /proc/wlan1/sta_info; echo __END__\r")
        output = receive(fd, rb"(?:^|[\r\n])__END__\r?\n", 8)
        return {"ok": True, "stations": parse_stations(output)}
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": str(error)}
    finally:
        if fd is not None:
            try:
                if original is not None:
                    termios.tcsetattr(fd, termios.TCSANOW, original)
                if exclusive:
                    fcntl.ioctl(fd, termios.TIOCNXCL)
            finally:
                os.close(fd)
