"""
PiPower Monitor Module for SOLAR Robot

This module provides an interface to the SunFounder PiPower V2 UPS
for monitoring battery status and power conditions via GPIO pins.

Features:
- Battery voltage monitoring (requires ADC for BT_LV pin)
- USB power input detection (IN_DT pin)
- Charging status detection (CHG pin)
- Low battery detection (LO_DT pin)
- Development mode simulation
"""

import abc
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Attempt to import RPi.GPIO, but allow failure for non-Pi environments
try:
    import RPi.GPIO as GPIO  # type: ignore
except (ImportError, RuntimeError):
    import FakeRPi.GPIO as GPIO


# Custom Exception for sensor reading errors
class SensorReadError(IOError):
    """Custom exception for errors encountered during sensor readings."""

    pass


@dataclass
class PiPowerReading:
    """Data class for PiPower status."""

    battery_voltage: Optional[float]  # Actual battery voltage in Volts
    is_usb_power_input: Optional[bool]
    is_charging: Optional[bool]
    is_low_battery: Optional[bool]
    timestamp: float


class PiPowerSensorAdapter(abc.ABC):
    """Abstract base class for PiPower sensor adapters."""

    @abc.abstractmethod
    def initialize(
        self, pins: Dict[str, int], adc_channel: Optional[int] = None
    ) -> None:
        """Initialize the sensor hardware or simulation."""
        pass

    @abc.abstractmethod
    def read_status(self) -> PiPowerReading:
        """Read the current status from PiPower."""
        pass

    @abc.abstractmethod
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        pass


class HardwarePiPowerAdapter(PiPowerSensorAdapter):
    """Adapter for the PiPower hardware using RPi.GPIO."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pins: Dict[str, Optional[int]] = {
            "BT_LV": None,  # Analog, requires ADC
            "IN_DT": None,  # Digital
            "CHG": None,  # Digital
            "LO_DT": None,  # Digital
        }
        self.adc_channel: Optional[int] = None  # For BT_LV if using an ADC like MCP3008

        if GPIO is None:
            self.logger.error(
                "RPi.GPIO library not available. HardwarePiPowerAdapter cannot function."
            )
            raise ImportError(
                "RPi.GPIO library not found. Please install it to use PiPower hardware."
            )
        self.logger.info("HardwarePiPowerAdapter created.")

    def initialize(
        self, pins: Dict[str, int], adc_channel: Optional[int] = None
    ) -> None:
        """
        Initialize GPIO pins.

        Args:
            pins: Dictionary mapping pin functions ('BT_LV', 'IN_DT', 'CHG', 'LO_DT') to GPIO BCM numbers.
            adc_channel: The ADC channel connected to BT_LV (e.g., for an MCP3008).
        """
        self.logger.info(
            f"Initializing HardwarePiPowerAdapter with pins: {pins}, ADC channel: {adc_channel}"
        )
        self.pins = {
            key: pins.get(key) for key in self.pins.keys()
        }  # Ensure all keys exist
        self.adc_channel = adc_channel

        if not all(
            isinstance(pin, int)
            for pin_name, pin in pins.items()
            if pin_name != "BT_LV" and pin is not None
        ):  # BT_LV is special
            missing_pins = [
                name
                for name, num in self.pins.items()
                if num is None and name != "BT_LV"
            ]
            if self.pins.get("BT_LV") is None and self.adc_channel is None:
                missing_pins.append("BT_LV (or ADC channel)")

            if missing_pins:
                self.logger.error(
                    f"Missing pin configurations for: {', '.join(missing_pins)}"
                )
                raise ValueError(
                    f"Required pin numbers not provided for: {', '.join(missing_pins)}"
                )

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            if self.pins["IN_DT"] is not None:
                GPIO.setup(self.pins["IN_DT"], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self.logger.info(f"IN_DT pin {self.pins['IN_DT']} setup as input.")
            if self.pins["CHG"] is not None:
                GPIO.setup(self.pins["CHG"], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self.logger.info(f"CHG pin {self.pins['CHG']} setup as input.")
            if self.pins["LO_DT"] is not None:
                GPIO.setup(self.pins["LO_DT"], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self.logger.info(f"LO_DT pin {self.pins['LO_DT']} setup as input.")

            # BT_LV pin setup depends on whether an ADC is used
            if self.pins["BT_LV"] is not None and self.adc_channel is not None:
                # Here you would initialize your ADC (e.g., MCP3008)
                # For example, if using a library for MCP3008:
                # self.adc = MCP3008(spi_bus, spi_device)
                self.logger.info(
                    f"BT_LV will be read from ADC channel {self.adc_channel} "
                    f"(GPIO pin {self.pins['BT_LV']} might be CE/CS for SPI)."
                )
            elif self.pins["BT_LV"] is not None:
                self.logger.warning(
                    "BT_LV pin specified but no ADC channel provided. "
                    "BT_LV provides an analog voltage (1/3 of battery voltage) and requires an ADC. "
                    "Battery voltage reading will not be available."
                )
            else:
                self.logger.info(
                    "BT_LV pin/ADC channel not configured. Battery voltage reading will not be available."
                )

            self.logger.info("HardwarePiPowerAdapter GPIO pins initialized.")

        except Exception as e:
            self.logger.error(f"Failed to initialize PiPower GPIO pins: {e}")
            raise SensorReadError(f"Failed to initialize PiPower GPIO pins: {e}") from e

    def _read_adc_voltage(self, channel: int) -> Optional[float]:
        """
        Placeholder for reading voltage from an ADC.
        The BT_LV pin outputs 1/3 of the battery voltage.
        This function should return the voltage read AT THE BT_LV PIN.
        """
        # IMPORTANT: Implement your ADC reading logic here.
        # This is an example assuming an MCP3008 and a library that returns raw ADC values.
        # from MCP3008 import MCP3008 # Example import
        # adc = MCP3008() # Example initialization
        # raw_value = adc.read(channel)
        # adc_max_value = 1023 # For a 10-bit ADC
        # reference_voltage = 3.3 # Raspberry Pi's 3.3V rail often used as ADC VREF
        # pin_voltage = (raw_value / adc_max_value) * reference_voltage
        # return pin_voltage
        self.logger.warning(
            "ADC reading for BT_LV not implemented. Returning None for battery voltage."
        )
        return None

    def read_status(self) -> PiPowerReading:
        if GPIO is None:
            raise SensorReadError("RPi.GPIO not available.")

        battery_voltage_actual: Optional[float] = None
        is_usb_power_input: Optional[bool] = None
        is_charging: Optional[bool] = None
        is_low_battery: Optional[bool] = None

        try:
            # Read BT_LV (Battery Voltage) via ADC if configured
            if self.adc_channel is not None:
                bt_lv_pin_voltage = self._read_adc_voltage(self.adc_channel)
                if bt_lv_pin_voltage is not None:
                    battery_voltage_actual = (
                        bt_lv_pin_voltage * 3.0
                    )  # BT_LV is 1/3 of actual battery voltage
                    self.logger.debug(
                        f"BT_LV (pin {self.pins['BT_LV']}, ADC ch {self.adc_channel}): {bt_lv_pin_voltage:.2f}V -> Battery: {battery_voltage_actual:.2f}V"
                    )
                else:
                    self.logger.debug(
                        f"BT_LV (pin {self.pins['BT_LV']}, ADC ch {self.adc_channel}): No ADC reading"
                    )

            # Read IN_DT (Input Detect)
            if self.pins["IN_DT"] is not None:
                is_usb_power_input = GPIO.input(self.pins["IN_DT"]) == GPIO.HIGH
                self.logger.debug(
                    f"IN_DT (pin {self.pins['IN_DT']}): {'High (USB Power)' if is_usb_power_input else 'Low (No USB Power)'}"
                )

            # Read CHG (Charging Status)
            if self.pins["CHG"] is not None:
                is_charging = GPIO.input(self.pins["CHG"]) == GPIO.HIGH
                self.logger.debug(
                    f"CHG (pin {self.pins['CHG']}): {'High (Charging)' if is_charging else 'Low (Not Charging)'}"
                )

            # Read LO_DT (Low Battery Detect)
            if self.pins["LO_DT"] is not None:
                is_low_battery = GPIO.input(self.pins["LO_DT"]) == GPIO.HIGH
                self.logger.debug(
                    f"LO_DT (pin {self.pins['LO_DT']}): {'High (Low Battery)' if is_low_battery else 'Low (Normal)'}"
                )

            return PiPowerReading(
                battery_voltage=battery_voltage_actual,
                is_usb_power_input=is_usb_power_input,
                is_charging=is_charging,
                is_low_battery=is_low_battery,
                timestamp=time.time(),
            )
        except Exception as e:
            self.logger.error(f"Error reading PiPower hardware status: {e}")
            raise SensorReadError(f"Error reading PiPower hardware status: {e}") from e

    def cleanup(self) -> None:
        if GPIO is not None:
            self.logger.info("Cleaning up PiPower GPIO pins.")
            # GPIO.cleanup() # Be careful with global cleanup if other parts of app use GPIO
        else:
            self.logger.info(
                "RPi.GPIO not available, no hardware cleanup needed for PiPower."
            )


class SimulatedPiPowerAdapter(PiPowerSensorAdapter):
    """Adapter for a simulated PiPower sensor."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.battery_voltage = 8.0  # Start with a healthy voltage
        self.usb_connected = True
        self.is_charging_sim = True
        self.low_battery_sim = False

    def initialize(
        self, pins: Dict[str, int], adc_channel: Optional[int] = None
    ) -> None:
        self.logger.info(
            f"SimulatedPiPowerAdapter initialized with pins: {pins}, ADC channel: {adc_channel}"
        )
        # No actual hardware to initialize

    def read_status(self) -> PiPowerReading:
        # Simulate battery voltage changes
        if self.usb_connected and self.is_charging_sim:
            self.battery_voltage += random.uniform(0.01, 0.05)  # Charging
        else:
            self.battery_voltage -= random.uniform(0.01, 0.05)  # Discharging

        self.battery_voltage = max(6.0, min(8.4, self.battery_voltage))  # Clamp voltage

        # Simulate low battery
        self.low_battery_sim = self.battery_voltage < 6.8

        # Simulate charging status based on USB and voltage
        if self.usb_connected and self.battery_voltage < 8.35:
            self.is_charging_sim = True
        elif self.battery_voltage >= 8.4:
            self.is_charging_sim = False  # Fully charged
        elif not self.usb_connected:
            self.is_charging_sim = False

        # Occasionally toggle USB power for simulation variety
        if random.random() < 0.05:
            self.usb_connected = not self.usb_connected
            self.logger.debug(
                f"Simulated USB power toggled to: {'Connected' if self.usb_connected else 'Disconnected'}"
            )

        reading = PiPowerReading(
            battery_voltage=self.battery_voltage,
            is_usb_power_input=self.usb_connected,
            is_charging=self.is_charging_sim,
            is_low_battery=self.low_battery_sim,
            timestamp=time.time(),
        )
        self.logger.debug(f"SimulatedPiPowerAdapter reading: {reading}")
        return reading

    def cleanup(self) -> None:
        self.logger.debug("SimulatedPiPowerAdapter cleaned up.")


class PiPowerMonitor:
    """
    PiPower Monitor for reading status from PiPower V2 UPS.
    Supports both production (real hardware) and development (simulated) modes.
    """

    def __init__(self, config: Dict[str, Any], production: bool = False):
        self.config = config.get(
            "pipower", {}
        )  # Runner specific config under 'pipower'
        self.production = production
        self.logger = logging.getLogger(__name__)

        # Configuration for pins
        self.pins = {
            "BT_LV": self.config.get("bt_lv_pin"),
            "IN_DT": self.config.get("in_dt_pin"),
            "CHG": self.config.get("chg_pin"),
            "LO_DT": self.config.get("lo_dt_pin"),
        }
        self.adc_channel = self.config.get("adc_channel")  # For BT_LV

        self.log_readings = self.config.get("log_readings", True)

        self.sensor_adapter: PiPowerSensorAdapter
        self._last_reading: Optional[PiPowerReading] = None
        self._init_sensor_adapter()

        self.logger.info(
            f"PiPower Monitor initialized. Mode: {'Production' if production else 'Development'}"
        )
        self.logger.info(
            f"Pin configuration: {self.pins}, ADC Channel: {self.adc_channel}"
        )

    def _init_sensor_adapter(self) -> None:
        """Initialize the appropriate sensor adapter based on environment."""
        try:
            if self.production:
                if GPIO is None:
                    self.logger.error(
                        "RPi.GPIO is not available. Cannot use HardwarePiPowerAdapter."
                    )
                    self.logger.warning(
                        "Falling back to SimulatedPiPowerAdapter for safety."
                    )
                    self.sensor_adapter = SimulatedPiPowerAdapter()
                else:
                    self.sensor_adapter = HardwarePiPowerAdapter()
            else:
                self.sensor_adapter = SimulatedPiPowerAdapter()

            # Pass only valid (integer) pin numbers to initialize
            valid_pins = {
                name: num for name, num in self.pins.items() if isinstance(num, int)
            }
            self.sensor_adapter.initialize(valid_pins, self.adc_channel)
        except ImportError as e:
            self.logger.error(
                f"Import error during PiPower sensor adapter initialization: {e}"
            )
            self.logger.warning(
                "Falling back to SimulatedPiPowerAdapter due to import error."
            )
            self.sensor_adapter = SimulatedPiPowerAdapter()
            # Initialize the simulated adapter with placeholder/dummy values if needed
            self.sensor_adapter.initialize({}, None)  # No specific pins for simulator
        except SensorReadError as e:
            self.logger.error(f"Failed to initialize PiPower sensor adapter: {e}")
            raise
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during sensor adapter initialization: {e}"
            )
            raise

    def get_reading(self) -> PiPowerReading:
        """
        Get a complete status reading from PiPower.

        Returns:
            PiPowerReading object with current status.
        Raises:
            SensorReadError if reading fails.
        """
        try:
            reading = self.sensor_adapter.read_status()
            self._last_reading = reading

            if self.log_readings:
                voltage_str = (
                    f"{reading.battery_voltage:.2f}V"
                    if reading.battery_voltage is not None
                    else "N/A"
                )
                usb_str = "USB In" if reading.is_usb_power_input else "No USB"
                charge_str = "Charging" if reading.is_charging else "Not Charging"
                low_batt_str = "LOW BATT" if reading.is_low_battery else "Batt OK"

                # Handle cases where boolean flags might be None
                if reading.is_usb_power_input is None:
                    usb_str = "USB N/A"
                if reading.is_charging is None:
                    charge_str = "Charge N/A"
                if reading.is_low_battery is None:
                    low_batt_str = "LowBatt N/A"

                self.logger.info(
                    f"PiPower Status - Voltage: {voltage_str}, {usb_str}, {charge_str}, {low_batt_str}"
                )
            return reading
        except SensorReadError as e:
            self.logger.error(f"Failed to get PiPower reading: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during PiPower reading: {e}")
            raise SensorReadError(f"Unexpected error during PiPower reading: {e}")

    def get_last_reading(self) -> Optional[PiPowerReading]:
        """
        Get the last PiPower reading without taking a new measurement.
        """
        return self._last_reading

    def is_healthy(self) -> bool:
        """
        Check if the sensor is responding.
        For PiPower, this mainly means we can attempt a read without critical errors.
        More specific health (e.g. voltage range) can be checked by the runner.
        """
        try:
            # Attempt a quick read; if it fails with SensorReadError, it's unhealthy.
            # We don't store this reading, just check if the call succeeds.
            test_reading = self.sensor_adapter.read_status()
            # Basic check: at least timestamp should be present.
            return test_reading.timestamp > 0
        except SensorReadError:
            self.logger.warning("PiPower health check failed: SensorReadError.")
            return False
        except Exception as e:
            self.logger.error(
                f"PiPower health check failed due to unexpected error: {e}"
            )
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about the PiPower monitor.
        """
        reading = self.get_last_reading()
        status = {
            "sensor_type": "PiPowerV2",
            "mode": (
                "production"
                if self.production and GPIO is not None
                else "development/simulated"
            ),
            "healthy": self.is_healthy(),
            "last_reading": None,
            "pins_configured": self.pins,
            "adc_channel_configured": self.adc_channel,
        }

        if reading:
            status["last_reading"] = {
                "battery_voltage": reading.battery_voltage,
                "is_usb_power_input": reading.is_usb_power_input,
                "is_charging": reading.is_charging,
                "is_low_battery": reading.is_low_battery,
                "timestamp": reading.timestamp,
            }
        return status

    def cleanup(self) -> None:
        """Cleanup resources used by the sensor adapter."""
        if hasattr(self, "sensor_adapter") and self.sensor_adapter:
            self.sensor_adapter.cleanup()
        self.logger.debug("PiPowerMonitor cleaned up.")


# Example usage (for testing purposes)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # --- Test Simulated Mode ---
    logger.info("-" * 20 + "TESTING SIMULATED MODE" + "-" * 20)
    sim_config = {
        "pipower": {
            "log_readings": True,
            # Pins not strictly needed for simulated, but good to show structure
            "bt_lv_pin": 17,  # GPIO BCM number (example)
            "adc_channel": 0,  # MCP3008 channel 0 (example)
            "in_dt_pin": 18,  # GPIO BCM number (example)
            "chg_pin": 27,  # GPIO BCM number (example)
            "lo_dt_pin": 22,  # GPIO BCM number (example)
        }
    }
    try:
        sim_monitor = PiPowerMonitor(config=sim_config, production=False)
        for i in range(5):
            reading = sim_monitor.get_reading()
            logger.info(f"Simulated Reading {i+1}: {reading}")
            status = sim_monitor.get_status()
            logger.info(
                f"Simulated Status: Healthy={sim_monitor.is_healthy()}, FullStatus: {status}"
            )
            time.sleep(1)
        sim_monitor.cleanup()
    except Exception as e:
        logger.error(f"Error in simulated test: {e}", exc_info=True)

    # --- Test Hardware Mode (will fail if not on RPi or RPi.GPIO not installed) ---
    # You would need to define actual BCM pin numbers for your setup.
    logger.info("-" * 20 + "TESTING HARDWARE MODE (EXPECTS RPi.GPIO)" + "-" * 20)
    # IMPORTANT: Replace with your actual BCM pin numbers and ADC channel if using an ADC
    hw_config = {
        "pipower": {
            "log_readings": True,
            "bt_lv_pin": None,  # Example: GPIO for ADC CS, or None if ADC handles it.
            # If you don't have an ADC for BT_LV, voltage will be None.
            "adc_channel": None,  # Example: 0 for MCP3008 channel 0. Set to None if no ADC.
            "in_dt_pin": 18,  # Example: GPIO BCM 18
            "chg_pin": 27,  # Example: GPIO BCM 27
            "lo_dt_pin": 22,  # Example: GPIO BCM 22
        }
    }
    if GPIO is not None:  # Only run if RPi.GPIO seems available
        try:
            logger.info("Attempting to initialize PiPowerMonitor in production mode.")
            # Ensure your user has permissions for GPIO access (e.g., part of 'gpio' group)
            # And that SPI is enabled if using an SPI-based ADC (sudo raspi-config)
            hw_monitor = PiPowerMonitor(config=hw_config, production=True)
            logger.info("PiPowerMonitor (HW mode) initialized. Taking a reading...")
            reading = hw_monitor.get_reading()
            logger.info(f"Hardware Reading: {reading}")
            status = hw_monitor.get_status()
            logger.info(
                f"Hardware Status: Healthy={hw_monitor.is_healthy()}, FullStatus: {status}"
            )
            hw_monitor.cleanup()
        except ImportError:
            logger.warning("RPi.GPIO not found, skipping hardware test.")
        except SensorReadError as sre:
            logger.error(f"SensorReadError during hardware test: {sre}")
        except Exception as e:
            logger.error(f"Error in hardware test: {e}", exc_info=True)
    else:
        logger.warning(
            "RPi.GPIO not available, hardware test for PiPowerMonitor skipped."
        )
