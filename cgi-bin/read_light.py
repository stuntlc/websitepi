#!/usr/bin/env python3
import subprocess
import sys

# Set the path of the file to execute
file_path = '/home/q/light.py'

print('Content-type: text/plain\n')  # CGI header

try:
    # Execute the Python script and capture output
    result = subprocess.run([sys.executable, file_path], capture_output=True, text=True, timeout=10)
    
    if result.returncode == 0:
        # Script executed successfully
        print(result.stdout)
    else:
        # Script had an error
        print(f'Error executing script:\n{result.stderr}')
        
except subprocess.TimeoutExpired:
    print('Error: Script execution timed out')
except Exception as e:
    print(f'Error executing file: {e}');