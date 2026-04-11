#!/bin/bash
echo "Content-Type: text/plain"
echo ""

VAL=$(python3 /home/q/volt.py)
echo "sensor:$VAL"
