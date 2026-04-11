import smbus
import time

ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

bus = smbus.SMBus(1)

config = (
    0x8000 |  # Start single conversion
    0x4000 |  # AIN0
    0x0200 |  # Gain = 1
    0x0100 |  # Single-shot mode
    0x0080    # 128 SPS
)

def read_adc():
    bus.write_i2c_block_data(ADDR, REG_CONFIG, [(config >> 8) & 0xFF, config & 0xFF])
    time.sleep(0.01)
    data = bus.read_i2c_block_data(ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]
    if raw > 32767:
        raw -= 65536
    return raw

LSB = 4.096 / 32768.0
DIVIDER = (470000 + 39000) / 39000  # ≈ 13.05

raw = read_adc()
v_meas = raw * LSB
v_in = v_meas * DIVIDER

print(f"{v_in:.2f}")

