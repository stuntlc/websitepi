import smbus
import time

# ADS1115 I2C address
ADDR = 0x48

# Registers
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

# I2C bus
bus = smbus.SMBus(1)

# Gain = 1 (±4.096 V)
# Single-ended A0
# 128 SPS
config = (
    0x8000 |  # Start single conversion
    0x4000 |  # AIN0
    0x0200 |  # Gain = 1
    0x0100 |  # Single-shot mode
    0x0080    # 128 samples/sec
)

def read_adc():
    # Write config (high byte, low byte)
    bus.write_i2c_block_data(ADDR, REG_CONFIG, [(config >> 8) & 0xFF, config & 0xFF])

    # Wait for conversion
    time.sleep(0.01)

    # Read conversion register
    data = bus.read_i2c_block_data(ADDR, REG_CONVERSION, 2)
    raw = (data[0] << 8) | data[1]

    # Convert signed 16-bit
    if raw > 32767:
        raw -= 65536

    return raw

# ADS1115 LSB size for gain=1
LSB = 4.096 / 32768.0

# Divider factor
DIVIDER = (470000 + 39000) / 39000  # ≈ 13.05

while True:
    raw = read_adc()
    v_meas = raw * LSB
    v_in = v_meas * DIVIDER

    print(f"ADC pin: {v_meas:.3f} V   |   Input: {v_in:.2f} V")
    time.sleep(0.5)
