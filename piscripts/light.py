import smbus
import time

ADDR = 0x48
REG_CONVERSION = 0x00
REG_CONFIG     = 0x01

bus = smbus.SMBus(1)

config = (
    0x8000 |
    0x5000 |  # AIN1
    0x0200 |
    0x0100 |
    0x0080
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

LSB = 4.096 / 32768.0

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

raw = read_adc()
voltage = raw * LSB
level = classify(voltage)

print(f"{voltage:.3f} V  →  {level}")
