#!/usr/bin/env python3
"""
Unit tests for INA219 Power Monitor

Tests both development (simulated) and production modes of the power monitor.
"""

import unittest
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sensors import INA219PowerMonitor


class TestINA219PowerMonitor(unittest.TestCase):
    """Test cases for INA219 Power Monitor."""

    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            "ina219": {
                "i2c_address": 0x40,
                "measurement_interval": 0.1,  # Fast for testing
                "log_measurements": False,  # Quiet for testing
                "low_power_threshold": 0.5,
                "high_power_threshold": 10.0,
            }
        }

    def test_development_mode_initialization(self):
        """Test initialization in development mode."""
        monitor = INA219PowerMonitor(self.test_config, production=False)
        self.assertIsNotNone(monitor)
        self.assertFalse(monitor.production)
        self.assertEqual(monitor.i2c_address, 0x40)

    def test_development_mode_readings(self):
        """Test taking readings in development mode."""
        monitor = INA219PowerMonitor(self.test_config, production=False)

        # Test individual readings
        voltage = monitor.read_voltage()
        current = monitor.read_current()
        power = monitor.read_power()

        self.assertGreater(voltage, 0)
        self.assertGreater(current, 0)
        self.assertGreater(power, 0)

        # Test complete reading
        reading = monitor.get_reading()
        self.assertIsNotNone(reading)
        self.assertGreater(reading.voltage, 0)
        self.assertGreater(reading.current, 0)
        self.assertGreater(reading.power, 0)
        self.assertIsNotNone(reading.timestamp)

    def test_health_check(self):
        """Test sensor health checking."""
        monitor = INA219PowerMonitor(self.test_config, production=False)

        # Should be healthy in development mode
        self.assertTrue(monitor.is_healthy())

    def test_status_reporting(self):
        """Test status reporting functionality."""
        monitor = INA219PowerMonitor(self.test_config, production=False)

        # Take a reading first
        monitor.get_reading()

        # Get status
        status = monitor.get_status()

        self.assertEqual(status["sensor_type"], "INA219")
        self.assertEqual(status["i2c_address"], "0x40")
        self.assertEqual(status["mode"], "development")
        self.assertTrue(status["healthy"])
        self.assertIsNotNone(status["last_reading"])
        self.assertIn("thresholds", status)

    def test_last_reading_retrieval(self):
        """Test retrieving the last reading."""
        monitor = INA219PowerMonitor(self.test_config, production=False)

        # Should be None initially
        self.assertIsNone(monitor.get_last_reading())

        # Take a reading
        reading1 = monitor.get_reading()

        # Should return the same reading
        reading2 = monitor.get_last_reading()
        self.assertEqual(reading1.timestamp, reading2.timestamp)
        self.assertEqual(reading1.voltage, reading2.voltage)

    def test_configuration_parsing(self):
        """Test configuration parameter parsing."""
        custom_config = {
            "ina219": {
                "i2c_address": 0x41,
                "measurement_interval": 2.0,
                "log_measurements": True,
                "low_power_threshold": 1.0,
                "high_power_threshold": 20.0,
            }
        }

        monitor = INA219PowerMonitor(custom_config, production=False)

        self.assertEqual(monitor.i2c_address, 0x41)
        self.assertEqual(monitor.measurement_interval, 2.0)
        self.assertTrue(monitor.log_measurements)
        self.assertEqual(monitor.low_power_threshold, 1.0)
        self.assertEqual(monitor.high_power_threshold, 20.0)

    def test_missing_config_defaults(self):
        """Test default values when configuration is missing."""
        empty_config = {}

        monitor = INA219PowerMonitor(empty_config, production=False)

        # Should use default values
        self.assertEqual(monitor.i2c_address, 0x40)
        self.assertEqual(monitor.measurement_interval, 1.0)
        self.assertTrue(monitor.log_measurements)
        self.assertEqual(monitor.low_power_threshold, 0.5)
        self.assertEqual(monitor.high_power_threshold, 10.0)


class TestINA219PowerReadingDataClass(unittest.TestCase):
    """Test cases for PowerReading data class."""

    def test_power_reading_creation(self):
        """Test PowerReading data class creation."""
        from sensors.ina219_power_monitor import PowerReading
        import time

        timestamp = time.time()
        reading = PowerReading(
            voltage=12.5, current=1.25, power=15.625, timestamp=timestamp
        )

        self.assertEqual(reading.voltage, 12.5)
        self.assertEqual(reading.current, 1.25)
        self.assertEqual(reading.power, 15.625)
        self.assertEqual(reading.timestamp, timestamp)


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
