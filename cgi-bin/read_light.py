#!/usr/bin/env python3
import subprocess

print("Content-Type: text/plain")
print("")

try:
    VAL = subprocess.run(['python3', '/home/q/light.py'], capture_output=True, text=True, timeout=10)
    output = VAL.stdout.strip()
    print(f"light:{output}")
except Exception as e:
    print(f"light:Error - {e}")