#!/bin/bash
echo "Content-Type: text/plain"
echo ""

VAL=$(python3 /home/q/websd/piscripts/volt.py)
echo "sensor:$VAL"
