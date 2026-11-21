"""Coordinate operations that use the phone's user interface."""
from contextlib import contextmanager
import time


LOCK_PATH = "/run/websitepi/phone-ui.lock"


@contextmanager
def phone_lock():
    import fcntl
    with open(LOCK_PATH, "w") as lock:
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Phone controls are busy. Try again.")
                time.sleep(0.1)
        yield
