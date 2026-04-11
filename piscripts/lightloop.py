import smbus
import time

ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

bus = smbus.SMBus(1)

config = (
    0x8000 |  # Start single conversion
    0x5000 |  # AIN1
    0x0200 |  # Gain = 1 (±4.096V)
    0x0100 |  # Single-shot mode
    0x0080    # 128 SPS
)

def read_adc():
    bus.write_i2c_block_data(ADDR, REG_CONFIG,
                             [(config >> 8) & 0xFF, config & 0xFF])
    time.sleep(0.01)
    data = bus.read_i2c_block_data(ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]
    if raw > 32767:
        raw -= 65536
    return raw

LSB = 4.096 / 32768.0  # ADS1115 gain=1

# Smoothing buffer
SMOOTH_COUNT = 10
buffer = []

# Auto-calibration
min_v = 99
max_v = 0

def classify(voltage):
    if voltage < 0.30:
        return "Dark"
    elif voltage < 0.80:
        return "Medium dark"
    elif voltage < 1.50:
        return "Normal light"
    elif voltage < 2.50:
        return "Bright"
    else:
        return "Sunlight / very bright"

while True:
    raw = read_adc()
    voltage = raw * LSB

    # Update smoothing buffer
    buffer.append(voltage)
    if len(buffer) > SMOOTH_COUNT:
        buffer.pop(0)
    smooth = sum(buffer) / len(buffer)

    # Auto-calibration
    min_v = min(min_v, smooth)
    max_v = max(max_v, smooth)
    span = max(max_v - min_v, 0.001)
    percent = (smooth - min_v) / span * 100

    level = classify(smooth)

    print(f"{smooth:.3f} V  |  {level:18} | {percent:5.1f}% calibrated")

    time.sleep(0.2)
