#!/usr/bin/env python3
"""
Unit tests for INA219 Power Monitor

Tests both development (simulated) and production modes of the power monitor.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch  # For mocking hardware

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Now import from sensors, including the new error type
from sensors import INA219PowerMonitor
from sensors.ina219_power_monitor import (
    PowerReading,
    SensorReadError,
    SimulatedINA219Adapter,
)


class TestINA219PowerMonitorDevelopment(unittest.TestCase):
    """Test cases for INA219 Power Monitor in Development Mode (Simulated)."""

    def setUp(self):
        """Set up test configuration for development mode."""
        self.test_config = {
            "ina219": {
                "i2c_address": 0x40,
                "measurement_interval": 0.1,  # Fast for testing
                "log_measurements": False,  # Quiet for testing
                "low_power_threshold": 0.5,
                "high_power_threshold": 10.0,
            }
        }
        # In development mode, it uses SimulatedINA219Adapter
        self.monitor = INA219PowerMonitor(self.test_config, production=False)

    def test_development_mode_initialization(self):
        """Test initialization in development mode."""
        self.assertIsNotNone(self.monitor)
        self.assertFalse(self.monitor.production)
        self.assertEqual(self.monitor.i2c_address, 0x40)
        self.assertIsInstance(self.monitor.sensor_adapter, SimulatedINA219Adapter)

    def test_development_mode_readings(self):
        """Test taking readings in development mode."""
        # Test individual readings
        voltage = self.monitor.read_voltage()
        current = self.monitor.read_current()
        power = self.monitor.read_power()

        self.assertGreater(voltage, 0)
        self.assertGreater(current, 0)
        self.assertGreater(power, 0)

        # Test complete reading
        reading = self.monitor.get_reading()
        self.assertIsNotNone(reading)
        self.assertIsInstance(reading, PowerReading)
        self.assertGreater(reading.voltage, 0)
        self.assertGreater(reading.current, 0)
        self.assertGreater(reading.power, 0)
        self.assertIsNotNone(reading.timestamp)

    def test_health_check_development(self):
        """Test sensor health checking in development mode."""
        # Should be healthy in development mode with simulated adapter
        self.assertTrue(self.monitor.is_healthy())

    def test_status_reporting_development(self):
        """Test status reporting functionality in development mode."""
        self.monitor.get_reading()  # Take a reading first
        status = self.monitor.get_status()

        self.assertEqual(status["sensor_type"], "INA219")
        self.assertEqual(status["i2c_address"], "0x40")
        self.assertEqual(status["mode"], "development")
        self.assertTrue(status["healthy"])  # is_healthy() should pass for sim
        self.assertIsNotNone(status["last_reading"])
        self.assertIn("voltage", status["last_reading"])
        self.assertIn("thresholds", status)

    def test_last_reading_retrieval_development(self):
        """Test retrieving the last reading in development mode."""
        self.assertIsNone(self.monitor.get_last_reading())  # Initially None
        reading1 = self.monitor.get_reading()
        reading2 = self.monitor.get_last_reading()
        self.assertIsNotNone(reading2)
        self.assertEqual(reading1.timestamp, reading2.timestamp)
        self.assertEqual(reading1.voltage, reading2.voltage)

    def test_configuration_parsing(self):
        """Test configuration parameter parsing (applies to both modes)."""
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
        """Test default values when configuration is missing (applies to both modes)."""
        monitor = INA219PowerMonitor({}, production=False)  # Empty config
        self.assertEqual(monitor.i2c_address, 0x40)
        self.assertEqual(monitor.measurement_interval, 1.0)
        self.assertTrue(monitor.log_measurements)
        self.assertEqual(monitor.low_power_threshold, 0.5)
        self.assertEqual(monitor.high_power_threshold, 10.0)


class TestINA219PowerMonitorProduction(unittest.TestCase):
    """Test cases for INA219 Power Monitor in Production Mode (Hardware)."""

    def setUp(self):
        self.test_config = {
            "ina219": {
                "i2c_address": 0x40,  # A common default
                "log_measurements": False,
            }
        }

    @patch("sensors.ina219_power_monitor.HardwareINA219Adapter")
    def test_production_mode_initialization_successful_mocked(
        self, MockHardwareAdapter
    ):
        """Test initialization in production mode with mocked hardware adapter."""
        # Create a mock adapter instance
        mock_adapter_instance = MockHardwareAdapter.return_value
        mock_adapter_instance.sensor = MagicMock()  # Mock sensor is set
        mock_adapter_instance.initialize.return_value = None  # initialize() succeeds

        monitor = INA219PowerMonitor(self.test_config, production=True)
        self.assertIsNotNone(monitor)
        self.assertTrue(monitor.production)

        # Verify the adapter was created with the correct i2c address
        MockHardwareAdapter.assert_called_once_with(0x40)
        # Verify initialize was called
        mock_adapter_instance.initialize.assert_called_once()
        # Verify the adapter is set
        self.assertEqual(monitor.sensor_adapter, mock_adapter_instance)

    @patch("sensors.ina219_power_monitor.HardwareINA219Adapter._initialize_sensor")
    def test_production_mode_initialization_failure_mocked(self, mock_init_sensor):
        """Test initialization failure in production mode with mocked hardware error."""
        mock_init_sensor.side_effect = SensorReadError("Mocked hardware init failure")
        with self.assertRaises(SensorReadError):
            INA219PowerMonitor(self.test_config, production=True)
        mock_init_sensor.assert_called_once()

    # Mocking the entire HardwareINA219Adapter for read tests
    @patch("sensors.ina219_power_monitor.HardwareINA219Adapter")
    def test_production_mode_readings_mocked(self, MockHardwareAdapter):
        """Test taking readings in production mode with mocked hardware adapter."""
        mock_adapter_instance = MockHardwareAdapter.return_value
        mock_adapter_instance.read_voltage.return_value = 12.1  # V
        mock_adapter_instance.read_current_ma.return_value = 1500.0  # mA
        mock_adapter_instance.read_power_mw.return_value = 12.1 * 1500.0  # mW

        monitor = INA219PowerMonitor(self.test_config, production=True)
        # Ensure our mock is actually used
        self.assertIsInstance(monitor.sensor_adapter, MagicMock)

        voltage = monitor.read_voltage()
        current = monitor.read_current()
        power = monitor.read_power()

        self.assertEqual(voltage, 12.1)
        self.assertEqual(current, 1.5)  # 1500mA / 1000
        self.assertEqual(power, (12.1 * 1500.0) / 1000.0)  # mW to W

        mock_adapter_instance.read_voltage.assert_called_once()
        mock_adapter_instance.read_current_ma.assert_called_once()
        mock_adapter_instance.read_power_mw.assert_called_once()

        reading = monitor.get_reading()
        self.assertEqual(reading.voltage, 12.1)
        self.assertEqual(reading.current, 1.5)

    @patch("sensors.ina219_power_monitor.HardwareINA219Adapter")
    def test_production_mode_read_failure_mocked(self, MockHardwareAdapter):
        """Test sensor read failure in production mode with mocked adapter."""
        mock_adapter_instance = MockHardwareAdapter.return_value
        mock_adapter_instance.read_voltage.side_effect = SensorReadError(
            "Mocked voltage read error"
        )

        monitor = INA219PowerMonitor(self.test_config, production=True)

        with self.assertRaises(SensorReadError) as cm:
            monitor.read_voltage()
        self.assertIn("Mocked voltage read error", str(cm.exception))

        with self.assertRaises(SensorReadError):  # get_reading should also fail
            monitor.get_reading()

    @patch("sensors.ina219_power_monitor.HardwareINA219Adapter._initialize_sensor")
    def test_health_check_production_unhealthy_on_init_fail(self, mock_init_sensor):
        """Test health check is False if hardware init fails."""
        mock_init_sensor.side_effect = SensorReadError("Mocked init fail")
        # We expect INA219PowerMonitor construction to fail if _initialize_sensor fails
        with self.assertRaises(SensorReadError):
            monitor = INA219PowerMonitor(self.test_config, production=True)
        # If construction itself fails, we can't call is_healthy() on the instance.
        # This test thus verifies that errors during critical setup (like sensor init)
        # are propagated, preventing an unhealthy monitor from being used.


class TestINA219PowerReadingDataClass(unittest.TestCase):
    """Test cases for PowerReading data class (unchanged by adapter refactor)."""

    def test_power_reading_creation(self):
        """Test PowerReading data class creation."""
        import time  # Ensure time is imported for this test

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
