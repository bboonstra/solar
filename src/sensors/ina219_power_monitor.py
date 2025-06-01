"""
INA219 Power Monitor Module for SOLAR Robot

This module provides an interface to the Adafruit INA219 High Side DC Current
Sensor Breakout for monitoring power consumption and battery status.

Features:
- Voltage measurement (up to 26V)
- Current measurement (±3.2A with ±0.8mA resolution)
- Power calculation
- Development mode simulation
- Configurable thresholds and alerts
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PowerReading:
    """Data class for power measurement results."""

    voltage: float  # Volts
    current: float  # Amperes
    power: float  # Watts
    timestamp: float  # Unix timestamp


class INA219PowerMonitor:
    """
    INA219 Power Monitor for measuring voltage, current, and power.

    Supports both production (real hardware) and development (simulated) modes.
    """

    def __init__(self, config: Dict[str, Any], production: bool = False):
        """
        Initialize the INA219 power monitor.

        Args:
            config: Configuration dictionary with INA219 settings
            production: Whether running on real hardware (True) or development (False)
        """
        self.config = config.get("ina219", {})
        self.production = production
        self.logger = logging.getLogger(__name__)

        # Configuration parameters
        self.i2c_address = self.config.get("i2c_address", 0x40)
        self.measurement_interval = self.config.get("measurement_interval", 1.0)
        self.log_measurements = self.config.get("log_measurements", True)
        self.low_power_threshold = self.config.get("low_power_threshold", 0.5)
        self.high_power_threshold = self.config.get("high_power_threshold", 10.0)

        # Initialize sensor
        self.sensor = None
        self._last_reading: Optional[PowerReading] = None
        self._init_sensor()

        self.logger.info(
            f"INA219 Power Monitor initialized - Address: 0x{self.i2c_address:02X}, "
            f"Mode: {'Production' if production else 'Development'}"
        )

    def _init_sensor(self) -> None:
        """Initialize the INA219 sensor based on environment."""
        try:
            if self.production:
                self._init_production_sensor()
            else:
                self._init_development_sensor()
        except Exception as e:
            self.logger.error(f"Failed to initialize INA219 sensor: {e}")
            raise

    def _init_production_sensor(self) -> None:
        """Initialize real INA219 sensor for production environment."""
        try:
            import board
            import busio
            import adafruit_ina219

            # Initialize I2C bus
            i2c = busio.I2C(board.SCL, board.SDA)

            # Initialize INA219 sensor
            self.sensor = adafruit_ina219.INA219(i2c, addr=self.i2c_address)

            self.logger.info("INA219 hardware sensor initialized successfully")

        except ImportError as e:
            self.logger.error("Required libraries not available for production mode")
            self.logger.error(
                "Please install: pip install adafruit-circuitpython-ina219"
            )
            raise e
        except Exception as e:
            self.logger.error(f"Failed to initialize INA219 hardware: {e}")
            raise e

    def _init_development_sensor(self) -> None:
        """Initialize simulated sensor for development environment."""
        self.logger.info("Using simulated INA219 sensor for development")
        # Development mode uses simulated values
        self.sensor = "simulated"

    def read_voltage(self) -> float:
        """
        Read bus voltage in volts.

        Returns:
            Voltage in volts
        """
        if self.production and self.sensor:
            try:
                return self.sensor.bus_voltage
            except Exception as e:
                self.logger.error(f"Error reading voltage: {e}")
                return 0.0
        else:
            # Simulate typical solar/battery voltage (12V nominal with some variation)
            import random

            base_voltage = 12.0
            variation = random.uniform(-0.5, 0.5)
            return max(0.0, base_voltage + variation)

    def read_current(self) -> float:
        """
        Read current in amperes.

        Returns:
            Current in amperes
        """
        if self.production and self.sensor:
            try:
                return self.sensor.current / 1000.0  # Convert mA to A
            except Exception as e:
                self.logger.error(f"Error reading current: {e}")
                return 0.0
        else:
            # Simulate current draw (typical robot consumption 0.5-2.0A)
            import random

            return random.uniform(0.5, 2.0)

    def read_power(self) -> float:
        """
        Read power in watts.

        Returns:
            Power in watts
        """
        if self.production and self.sensor:
            try:
                return self.sensor.power / 1000.0  # Convert mW to W
            except Exception as e:
                self.logger.error(f"Error reading power: {e}")
                return 0.0
        else:
            # Calculate simulated power from voltage and current
            voltage = self.read_voltage()
            current = self.read_current()
            return voltage * current

    def get_reading(self) -> PowerReading:
        """
        Get a complete power reading with voltage, current, and power.

        Returns:
            PowerReading object with all measurements
        """
        voltage = self.read_voltage()
        current = self.read_current()
        power = self.read_power()
        timestamp = time.time()

        reading = PowerReading(
            voltage=voltage, current=current, power=power, timestamp=timestamp
        )

        self._last_reading = reading

        if self.log_measurements:
            self.logger.info(
                f"Power Reading - V: {voltage:.2f}V, I: {current:.3f}A, P: {power:.2f}W"
            )

        # Check thresholds
        self._check_thresholds(reading)

        return reading

    def _check_thresholds(self, reading: PowerReading) -> None:
        """Check power reading against configured thresholds."""
        if reading.power < self.low_power_threshold:
            self.logger.warning(
                f"Low power detected: {reading.power:.2f}W "
                f"(threshold: {self.low_power_threshold}W)"
            )
        elif reading.power > self.high_power_threshold:
            self.logger.warning(
                f"High power detected: {reading.power:.2f}W "
                f"(threshold: {self.high_power_threshold}W)"
            )

    def get_last_reading(self) -> Optional[PowerReading]:
        """
        Get the last power reading without taking a new measurement.

        Returns:
            Last PowerReading or None if no reading has been taken
        """
        return self._last_reading

    def is_healthy(self) -> bool:
        """
        Check if the sensor is responding and providing reasonable readings.

        Returns:
            True if sensor appears healthy, False otherwise
        """
        try:
            reading = self.get_reading()
            # Basic sanity checks
            if reading.voltage < 0 or reading.voltage > 30:
                return False
            if abs(reading.current) > 5:  # Reasonable current limit
                return False
            if reading.power < 0 or reading.power > 50:  # Reasonable power limit
                return False
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about the power monitor.

        Returns:
            Dictionary with status information
        """
        reading = self.get_last_reading()

        status = {
            "sensor_type": "INA219",
            "i2c_address": f"0x{self.i2c_address:02X}",
            "mode": "production" if self.production else "development",
            "healthy": self.is_healthy(),
            "last_reading": None,
            "thresholds": {
                "low_power": self.low_power_threshold,
                "high_power": self.high_power_threshold,
            },
        }

        if reading:
            status["last_reading"] = {
                "voltage": reading.voltage,
                "current": reading.current,
                "power": reading.power,
                "timestamp": reading.timestamp,
            }

        return status
