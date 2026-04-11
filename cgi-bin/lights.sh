#!/bin/bash
echo "Content-Type: text/plain"
echo ""

VAL=$(python3 /home/q/light.py)
echo "sensor:$VAL"
