# SOLAR Robot Sensors Module

This module contains sensor implementations for the SOLAR robot, including environmental monitoring and system diagnostics sensors.

## INA219 Power Monitor

The INA219PowerMonitor class provides an interface to the [Adafruit INA219 High Side DC Current Sensor Breakout](https://www.adafruit.com/product/904) for monitoring power consumption and battery status.

### Features

- **Voltage Measurement**: Up to 26V high-side voltage monitoring
- **Current Measurement**: ±3.2A current measurement with ±0.8mA resolution  
- **Power Calculation**: Automatic power calculation (V × I)
- **Development Mode**: Simulated readings for testing without hardware
- **Health Monitoring**: Built-in sensor health checks
- **Configurable Thresholds**: Low and high power alerts
- **I2C Communication**: Uses standard I2C protocol (addresses 0x40-0x45)

### Hardware Setup

1. **Connect the INA219 to your Raspberry Pi:**

   ```
   INA219    Raspberry Pi
   --------  ------------
   VCC    -> 3.3V or 5V
   GND    -> GND
   SCL    -> SCL (GPIO 3)
   SDA    -> SDA (GPIO 2)
   ```

2. **Connect your power circuit:**

   ```
   Power Supply (+) -> VIN+ (INA219) -> VIN- (INA219) -> Load (+)
   Power Supply (-) -> Load (-)
   ```

3. **Enable I2C on Raspberry Pi:**

   ```bash
   sudo raspi-config
   # Navigate to Interface Options > I2C > Enable
   ```

### Software Setup

1. **Install dependencies:**

   ```bash
   pip install adafruit-circuitpython-ina219
   ```

2. **Configure in config.yaml:**

   ```yaml
   ina219:
     i2c_address: 0x40  # Default address
     measurement_interval: 1.0  # Seconds between readings
     log_measurements: true
     low_power_threshold: 0.5   # Watts
     high_power_threshold: 10.0 # Watts
   ```

### Usage Examples

#### Basic Usage

```python
from sensors import INA219PowerMonitor

# Load your configuration
config = load_config()  # Your config loading function

# Initialize the power monitor
power_monitor = INA219PowerMonitor(config, production=False)

# Take a single reading
reading = power_monitor.get_reading()
print(f"Voltage: {reading.voltage:.2f}V")
print(f"Current: {reading.current:.3f}A") 
print(f"Power: {reading.power:.2f}W")
```

#### Continuous Monitoring Loop

```python
import time

power_monitor = INA219PowerMonitor(config, production=False)

while True:
    try:
        reading = power_monitor.get_reading()
        
        # Check if sensor is healthy
        if not power_monitor.is_healthy():
            print("Warning: INA219 sensor is not healthy!")
        
        # Your application logic here
        # ... process the power data ...
        
        time.sleep(power_monitor.measurement_interval)
        
    except KeyboardInterrupt:
        break
```

#### Individual Measurements

```python
power_monitor = INA219PowerMonitor(config, production=False)

# Read individual values
voltage = power_monitor.read_voltage()  # Volts
current = power_monitor.read_current()  # Amperes  
power = power_monitor.read_power()      # Watts

# Get last reading without new measurement
last_reading = power_monitor.get_last_reading()
```

#### Status and Health Monitoring

```python
power_monitor = INA219PowerMonitor(config, production=False)

# Get comprehensive status
status = power_monitor.get_status()
print(f"Sensor Type: {status['sensor_type']}")
print(f"I2C Address: {status['i2c_address']}")
print(f"Mode: {status['mode']}")
print(f"Healthy: {status['healthy']}")

# Check if sensor is responding properly
if power_monitor.is_healthy():
    print("Sensor is working correctly")
else:
    print("Sensor may have issues")
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `i2c_address` | `0x40` | I2C address of the INA219 sensor |
| `measurement_interval` | `1.0` | Seconds between measurements in continuous mode |
| `log_measurements` | `true` | Whether to log each measurement |
| `low_power_threshold` | `0.5` | Low power warning threshold (watts) |
| `high_power_threshold` | `10.0` | High power warning threshold (watts) |

### Development vs Production Mode

- **Development Mode (`production=False`)**: Uses simulated sensor readings for testing without hardware
- **Production Mode (`production=True`)**: Communicates with real INA219 hardware via I2C

### PowerReading Data Class

The `PowerReading` data class contains:

```python
@dataclass
class PowerReading:
    voltage: float    # Volts
    current: float    # Amperes
    power: float      # Watts
    timestamp: float  # Unix timestamp
```

### Error Handling

The INA219PowerMonitor includes robust error handling:

- **Hardware communication errors** are caught and logged
- **Missing configuration** uses sensible defaults
- **Health checks** validate sensor readings
- **Development mode** provides fallback when hardware unavailable

### Example Applications

1. **Battery Monitoring**: Track battery voltage and current draw
2. **Solar Panel Monitoring**: Monitor solar panel output
3. **Power Consumption Analysis**: Measure device power usage
4. **System Health**: Monitor overall power system status
5. **Energy Efficiency**: Optimize power consumption

### Troubleshooting

1. **"Failed to initialize INA219 hardware"**:
   - Check I2C connections
   - Verify I2C is enabled: `sudo i2cdetect -y 1`
   - Ensure correct I2C address in config

2. **"Required libraries not available"**:
   - Install CircuitPython libraries: `pip install adafruit-circuitpython-ina219`

3. **Unrealistic readings**:
   - Check power circuit connections
   - Verify voltage is within 0-26V range
   - Ensure current is within ±3.2A range

4. **No readings in production mode**:
   - Switch to development mode for testing
   - Check hardware connections
   - Verify sensor power supply

### Testing

Run the included tests to verify functionality:

```bash
# Run all sensor tests
python -m pytest tests/test_ina219_power_monitor.py -v

# Run the demonstration script
python src/examples/power_monitor_demo.py
```
