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

import abc  # Added for Abstract Base Class
import logging
import random  # Moved import for use in SimulatedINA219Adapter
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


# Custom Exception for sensor reading errors
class SensorReadError(IOError):
    """Custom exception for errors encountered during sensor readings."""

    pass


@dataclass
class PowerReading:
    """Data class for power measurement results."""

    voltage: float  # Volts
    current: float  # Amperes
    power: float  # Watts
    timestamp: float  # Unix timestamp


# Abstract Base Class for Power Sensor Adapters
class PowerSensorAdapter(abc.ABC):
    """Abstract base class for power sensor adapters."""

    @abc.abstractmethod
    def read_voltage(self) -> float:
        """Read bus voltage in volts."""
        pass

    @abc.abstractmethod
    def read_current_ma(self) -> float:
        """Read current in milliamperes."""
        pass

    # Power reading from sensor might be direct, or calculated.
    # INA219 provides it directly.
    @abc.abstractmethod
    def read_power_mw(self) -> float:
        """Read power in milliwatts."""
        pass

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize the sensor hardware or simulation."""
        pass


# Concrete Adapter for the real INA219 hardware
class HardwareINA219Adapter(PowerSensorAdapter):
    """Adapter for the Adafruit INA219 hardware sensor."""

    def __init__(self, i2c_address: int):
        self.i2c_address = i2c_address
        self.sensor = None
        self.logger = logging.getLogger(__name__)
        self._initialize_sensor()

    def _initialize_sensor(self) -> None:
        try:
            import board
            import busio
            from adafruit_ina219 import INA219  # type: ignore

            i2c = busio.I2C(board.SCL, board.SDA)
            self.sensor = INA219(i2c, addr=self.i2c_address)
            self.logger.info(
                f"Hardware INA219 sensor initialized at address 0x{self.i2c_address:02X}"
            )
        except ImportError:
            self.logger.error(
                "Required libraries (board, busio, adafruit_ina219) not available for production mode."
            )
            self.logger.error(
                "Please install: pip install adafruit-circuitpython-ina219"
            )
            raise  # Re-raise to prevent operation without sensor
        except Exception as e:
            self.logger.error(f"Failed to initialize INA219 hardware: {e}")
            raise SensorReadError(f"Failed to initialize INA219 hardware: {e}") from e

    def initialize(self) -> None:
        # Initialization is done in __init__ for this adapter
        if not self.sensor:  # Try to re-initialize if it failed previously
            self._initialize_sensor()
        if not self.sensor:
            raise SensorReadError("Hardware INA219 sensor not initialized.")

    def read_voltage(self) -> float:
        if not self.sensor:
            raise SensorReadError("INA219 sensor not available.")
        try:
            return self.sensor.bus_voltage  # Already in Volts
        except Exception as e:
            self.logger.error(f"Error reading voltage from hardware: {e}")
            raise SensorReadError(f"Error reading voltage from hardware: {e}") from e

    def read_current_ma(self) -> float:
        if not self.sensor:
            raise SensorReadError("INA219 sensor not available.")
        try:
            return self.sensor.current  # In mA
        except Exception as e:
            self.logger.error(f"Error reading current from hardware: {e}")
            raise SensorReadError(f"Error reading current from hardware: {e}") from e

    def read_power_mw(self) -> float:
        if not self.sensor:
            raise SensorReadError("INA219 sensor not available.")
        try:
            # The adafruit_ina219 library's `power` property is already calculated
            # from bus_voltage and current, and it's returned in mW.
            return self.sensor.power  # In mW
        except Exception as e:
            self.logger.error(f"Error reading power from hardware: {e}")
            raise SensorReadError(f"Error reading power from hardware: {e}") from e


# Concrete Adapter for Simulated Sensor
class SimulatedINA219Adapter(PowerSensorAdapter):
    """Adapter for a simulated INA219 sensor."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.initialize()
        # Add state to occasionally simulate higher power draws
        self._normal_operation = True
        self._last_state_change = time.time()
        self._state_duration = random.uniform(
            30, 120
        )  # 30s to 2min between state changes

    def initialize(self) -> None:
        self.logger.debug("Simulated INA219 sensor initialized.")
        # No actual hardware to initialize

    def _update_operation_state(self) -> None:
        """Update whether we're in normal or high power operation mode."""
        current_time = time.time()
        if current_time - self._last_state_change > self._state_duration:
            # 90% chance of normal operation, 10% chance of high power
            self._normal_operation = random.random() < 0.9
            self._last_state_change = current_time
            self._state_duration = random.uniform(30, 120)

    def read_voltage(self) -> float:
        # Simulate typical solar/battery voltage (12V nominal with some variation)
        base_voltage = 12.0
        variation = random.uniform(-0.3, 0.3)  # Reduced variation
        return max(0.0, base_voltage + variation)

    def read_current_ma(self) -> float:
        self._update_operation_state()

        if self._normal_operation:
            # Normal operation: 200-800mA (0.2-0.8A)
            current = random.uniform(200.0, 800.0)
        else:
            # High power operation: 800-1200mA (0.8-1.2A)
            # This will occasionally trigger high power warnings but not too frequently
            current = random.uniform(800.0, 1200.0)

        return current

    def read_power_mw(self) -> float:
        # Calculate simulated power from voltage and current
        voltage_v = self.read_voltage()
        current_ma = self.read_current_ma()
        return voltage_v * current_ma  # V * mA = mW


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

        # Initialize sensor adapter
        self.sensor_adapter: PowerSensorAdapter
        self._last_reading: Optional[PowerReading] = None
        self._init_sensor_adapter()

        self.logger.debug(
            f"INA219 Power Monitor initialized - Address: 0x{self.i2c_address:02X}, "
            f"Mode: {'Production' if production else 'Development'}"
        )

    def _init_sensor_adapter(self) -> None:
        """Initialize the appropriate sensor adapter based on environment."""
        try:
            if self.production:
                self.sensor_adapter = HardwareINA219Adapter(self.i2c_address)
            else:
                self.sensor_adapter = SimulatedINA219Adapter()
            self.sensor_adapter.initialize()  # Ensure it's ready
        except SensorReadError as e:  # Catch errors from adapter initialization
            self.logger.error(f"Failed to initialize INA219 sensor adapter: {e}")
            # If production sensor fails, we might want to fall back or raise
            # For now, re-raising to make it clear initialization failed.
            raise
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during sensor adapter initialization: {e}"
            )
            raise

    def read_voltage(self) -> float:
        """
        Read bus voltage in volts.

        Returns:
            Voltage in volts
        Raises:
            SensorReadError if reading fails.
        """
        try:
            return self.sensor_adapter.read_voltage()
        except SensorReadError as e:
            self.logger.error(f"Error reading voltage: {e}")
            raise  # Re-raise the specific error

    def read_current(self) -> float:
        """
        Read current in amperes.

        Returns:
            Current in amperes
        Raises:
            SensorReadError if reading fails.
        """
        try:
            current_ma = self.sensor_adapter.read_current_ma()
            return current_ma / 1000.0  # Convert mA to A
        except SensorReadError as e:
            self.logger.error(f"Error reading current: {e}")
            raise

    def read_power(self) -> float:
        """
        Read power in watts.

        Returns:
            Power in watts
        Raises:
            SensorReadError if reading fails.
        """
        try:
            power_mw = self.sensor_adapter.read_power_mw()
            return power_mw / 1000.0  # Convert mW to W
        except SensorReadError as e:
            self.logger.error(f"Error reading power: {e}")
            raise

    def get_reading(self) -> PowerReading:
        """
        Get a complete power reading with voltage, current, and power.

        Returns:
            PowerReading object with all measurements
        Raises:
            SensorReadError if any underlying sensor read fails.
        """
        try:
            voltage = self.read_voltage()
            current = self.read_current()
            power = self.read_power()
            timestamp = time.time()

            reading = PowerReading(
                voltage=voltage, current=current, power=power, timestamp=timestamp
            )

            self._last_reading = reading

            if self.log_measurements:
                self.logger.debug(
                    f"Power Reading - V: {voltage:.2f}V, I: {current:.3f}A, P: {power:.2f}W"
                )

            # Check thresholds
            self._check_thresholds(reading)

            return reading
        except SensorReadError as e:
            self.logger.error(f"Failed to get complete power reading: {e}")
            raise  # Propagate the error

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
        health_status = False  # Default to unhealthy
        try:
            # Attempt to initialize the adapter if it's not ready (e.g., if initial attempt failed)
            # This is a bit complex as initialize() might raise errors.
            # A simpler health check is to just try getting a reading.
            if not (hasattr(self, "sensor_adapter") and self.sensor_adapter):
                self.logger.warning("Sensor adapter not available for health check.")
                return health_status

            # For hardware adapter, ensure it's truly initialized
            if (
                isinstance(self.sensor_adapter, HardwareINA219Adapter)
                and not self.sensor_adapter.sensor
            ):
                try:
                    self.logger.info(
                        "Attempting to re-initialize hardware sensor for health check."
                    )
                    self.sensor_adapter.initialize()
                except SensorReadError as init_e:
                    self.logger.warning(
                        f"Sensor re-initialization failed during health check: {init_e}"
                    )
                    return health_status

            reading = (
                self.get_reading()
            )  # This will raise SensorReadError if issues occur

            # Basic sanity checks - all conditions must be met for healthy status
            health_status = (
                -0.1
                < reading.voltage
                < 30  # Allow slightly below 0 for noise, but not much
                and -5.0 < reading.current < 5.0  # Reasonable current limit (A)
                and -1.0
                < reading.power
                < 150.0  # Reasonable power limit (W), allow slightly negative
            )

            if not health_status:
                if not (-0.1 < reading.voltage < 30):
                    self.logger.warning(f"Unhealthy voltage: {reading.voltage}V")
                if not (-5.0 < reading.current < 5.0):
                    self.logger.warning(f"Unhealthy current: {reading.current}A")
                if not (-1.0 < reading.power < 150.0):
                    self.logger.warning(f"Unhealthy power: {reading.power}W")

        except SensorReadError as e:
            self.logger.error(f"Health check failed due to sensor read error: {e}")
        except Exception as e:  # Catch any other unexpected errors
            self.logger.error(f"Health check failed due to unexpected error: {e}")

        return health_status

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
