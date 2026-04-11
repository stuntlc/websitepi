<<<<<<< HEAD
#!/bin/bash
echo "Content-Type: text/plain"
echo ""

VAL=$(python3 /home/q/light.py)
echo "sensor:$VAL"
=======
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
>>>>>>> 3064cdf19b848525d2968892db63138bf79c6a27
