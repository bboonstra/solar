#!/usr/bin/env python3
"""
Unit tests for PiPower Monitor

Tests both development (simulated) and production modes of the power monitor.
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sensors.pipower_monitor import (
    HardwarePiPowerAdapter,
    PiPowerMonitor,
    PiPowerReading,
    SensorReadError,
    SimulatedPiPowerAdapter,
)


class TestPiPowerMonitorDevelopment(unittest.TestCase):
    """Test cases for PiPower Monitor in Development Mode (Simulated)."""

    def setUp(self):
        """Set up test configuration for development mode."""
        self.test_config = {
            "pipower": {
                "log_readings": False,  # Quiet for testing
                "bt_lv_pin": 17,
                "adc_channel": 0,
                "in_dt_pin": 18,
                "chg_pin": 27,
                "lo_dt_pin": 22,
            }
        }
        # In development mode, it uses SimulatedPiPowerAdapter
        self.monitor = PiPowerMonitor(self.test_config, production=False)

    def test_development_mode_initialization(self):
        """Test initialization in development mode."""
        self.assertIsNotNone(self.monitor)
        self.assertFalse(self.monitor.production)
        self.assertIsInstance(self.monitor.sensor_adapter, SimulatedPiPowerAdapter)
        self.assertEqual(self.monitor.pins["BT_LV"], 17)
        self.assertEqual(self.monitor.pins["IN_DT"], 18)
        self.assertEqual(self.monitor.pins["CHG"], 27)
        self.assertEqual(self.monitor.pins["LO_DT"], 22)
        self.assertEqual(self.monitor.adc_channel, 0)

    def test_development_mode_readings(self):
        """Test taking readings in development mode."""
        reading = self.monitor.get_reading()
        self.assertIsNotNone(reading)
        self.assertIsInstance(reading, PiPowerReading)

        # Check all fields are present and of correct type
        self.assertIsInstance(reading.battery_voltage, float)
        self.assertIsInstance(reading.is_usb_power_input, bool)
        self.assertIsInstance(reading.is_charging, bool)
        self.assertIsInstance(reading.is_low_battery, bool)
        self.assertIsInstance(reading.timestamp, float)

        # Check voltage is in reasonable range for simulated data
        self.assertGreaterEqual(reading.battery_voltage, 6.0)
        self.assertLessEqual(reading.battery_voltage, 8.4)

    def test_health_check_development(self):
        """Test sensor health checking in development mode."""
        # Should be healthy in development mode with simulated adapter
        self.assertTrue(self.monitor.is_healthy())

    def test_status_reporting_development(self):
        """Test status reporting functionality in development mode."""
        self.monitor.get_reading()  # Take a reading first
        status = self.monitor.get_status()

        self.assertEqual(status["sensor_type"], "PiPowerV2")
        self.assertEqual(status["mode"], "development/simulated")
        self.assertTrue(status["healthy"])
        self.assertIsNotNone(status["last_reading"])
        self.assertIn("battery_voltage", status["last_reading"])
        self.assertIn("is_usb_power_input", status["last_reading"])
        self.assertIn("is_charging", status["last_reading"])
        self.assertIn("is_low_battery", status["last_reading"])

    def test_last_reading_retrieval_development(self):
        """Test retrieving the last reading in development mode."""
        self.assertIsNone(self.monitor.get_last_reading())  # Initially None
        reading1 = self.monitor.get_reading()
        reading2 = self.monitor.get_last_reading()
        self.assertIsNotNone(reading2)
        self.assertEqual(reading1.timestamp, reading2.timestamp)
        self.assertEqual(reading1.battery_voltage, reading2.battery_voltage)

    def test_configuration_parsing(self):
        """Test configuration parameter parsing."""
        custom_config = {
            "pipower": {
                "log_readings": True,
                "bt_lv_pin": 25,
                "adc_channel": 1,
                "in_dt_pin": 24,
                "chg_pin": 23,
                "lo_dt_pin": 22,
            }
        }
        monitor = PiPowerMonitor(custom_config, production=False)
        self.assertEqual(monitor.pins["BT_LV"], 25)
        self.assertEqual(monitor.adc_channel, 1)
        self.assertEqual(monitor.pins["IN_DT"], 24)
        self.assertEqual(monitor.pins["CHG"], 23)
        self.assertEqual(monitor.pins["LO_DT"], 22)
        self.assertTrue(monitor.log_readings)

    def test_missing_config_handling(self):
        """Test handling of missing configuration values."""
        monitor = PiPowerMonitor({}, production=False)  # Empty config
        self.assertIsNone(monitor.pins["BT_LV"])
        self.assertIsNone(monitor.adc_channel)
        self.assertIsNone(monitor.pins["IN_DT"])
        self.assertIsNone(monitor.pins["CHG"])
        self.assertIsNone(monitor.pins["LO_DT"])
        self.assertTrue(monitor.log_readings)  # Default should be True


class TestPiPowerMonitorProduction(unittest.TestCase):
    """Test cases for PiPower Monitor in Production Mode (Hardware)."""

    def setUp(self):
        self.test_config = {
            "pipower": {
                "log_readings": False,
                "bt_lv_pin": 17,
                "adc_channel": 0,
                "in_dt_pin": 18,
                "chg_pin": 27,
                "lo_dt_pin": 22,
            }
        }

    @patch("sensors.pipower_monitor.GPIO")
    def test_production_mode_initialization_successful(self, mock_gpio):
        """Test successful initialization in production mode with mocked GPIO."""
        monitor = PiPowerMonitor(self.test_config, production=True)
        self.assertIsNotNone(monitor)
        self.assertTrue(monitor.production)
        self.assertIsInstance(monitor.sensor_adapter, HardwarePiPowerAdapter)

        # Verify GPIO setup
        mock_gpio.setmode.assert_called_once_with(mock_gpio.BCM)
        mock_gpio.setwarnings.assert_called_once_with(False)

        # Verify pin setup calls
        setup_calls = mock_gpio.setup.call_args_list
        self.assertEqual(len(setup_calls), 3)  # IN_DT, CHG, LO_DT (BT_LV is for ADC)

    @patch("sensors.pipower_monitor.GPIO")
    def test_production_mode_readings(self, mock_gpio):
        """Test taking readings in production mode with mocked GPIO."""
        # Configure mock GPIO readings
        mock_gpio.HIGH = 1
        mock_gpio.LOW = 0
        mock_gpio.input.side_effect = [1, 1, 0]  # USB power on, Charging, Battery OK

        monitor = PiPowerMonitor(self.test_config, production=True)
        reading = monitor.get_reading()

        self.assertIsNotNone(reading)
        self.assertTrue(reading.is_usb_power_input)  # First mock input was HIGH
        self.assertTrue(reading.is_charging)  # Second mock input was HIGH
        self.assertFalse(reading.is_low_battery)  # Third mock input was LOW
        self.assertIsNone(reading.battery_voltage)  # No ADC implementation

    @patch("sensors.pipower_monitor.GPIO")
    def test_production_mode_gpio_error(self, mock_gpio):
        """Test handling of GPIO errors in production mode."""
        mock_gpio.setup.side_effect = RuntimeError("GPIO setup failed")

        with self.assertRaises(SensorReadError):
            PiPowerMonitor(self.test_config, production=True)

    @patch("sensors.pipower_monitor.GPIO")
    def test_cleanup(self, mock_gpio):
        """Test cleanup in production mode."""
        monitor = PiPowerMonitor(self.test_config, production=True)
        monitor.cleanup()
        # We don't call GPIO.cleanup() to avoid affecting other GPIO users
        self.assertEqual(mock_gpio.cleanup.call_count, 0)


class TestPiPowerReadingDataClass(unittest.TestCase):
    """Test cases for PiPowerReading data class."""

    def test_power_reading_creation(self):
        """Test PiPowerReading data class creation and attributes."""
        import time

        timestamp = time.time()
        reading = PiPowerReading(
            battery_voltage=7.4,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=False,
            timestamp=timestamp,
        )

        self.assertEqual(reading.battery_voltage, 7.4)
        self.assertTrue(reading.is_usb_power_input)
        self.assertTrue(reading.is_charging)
        self.assertFalse(reading.is_low_battery)
        self.assertEqual(reading.timestamp, timestamp)

    def test_power_reading_optional_voltage(self):
        """Test PiPowerReading with optional battery voltage."""
        reading = PiPowerReading(
            battery_voltage=None,  # Battery voltage can be None if no ADC
            is_usb_power_input=True,
            is_charging=False,
            is_low_battery=False,
            timestamp=time.time(),
        )
        self.assertIsNone(reading.battery_voltage)


if __name__ == "__main__":
    unittest.main(verbosity=2)
