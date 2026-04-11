#!/usr/bin/env python3
import os

# Set the path of the file to read
file_path = '/home/q/light.py'

try:
    # Read the contents of the file
    with open(file_path, 'r') as file:
        content = file.read()
    print('Content-type: text/plain\n')  # CGI header
    print(content)
except Exception as e:
    print('Content-type: text/plain\n')  # CGI header
    print(f'Error reading file: {e}')