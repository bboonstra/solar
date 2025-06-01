#!/usr/bin/env python3
"""
Unit Tests for PiPower Runner

This module contains unit tests for the PiPower runner class.
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from runners.base_runner import RunnerState
from runners.pipower_runner import PiPowerRunner, PowerStats
from sensors.pipower_monitor import PiPowerReading, SensorReadError


class TestPiPowerRunner(unittest.TestCase):
    """Test cases for PiPower Runner functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "enabled": True,
            "measurement_interval": 0.1,
            "label": "Test PiPower",
            "log_readings": False,
            "bt_lv_pin": 17,
            "adc_channel": 0,
            "in_dt_pin": 18,
            "chg_pin": 27,
            "lo_dt_pin": 22,
            "low_battery_alert_threshold": 2,
            "no_usb_alert_threshold": 2,
        }
        # Patch PiPowerMonitor during setup
        self.monitor_patcher = patch("runners.pipower_runner.PiPowerMonitor")
        self.mock_monitor_class = self.monitor_patcher.start()
        self.mock_monitor = self.mock_monitor_class.return_value
        self.runner = PiPowerRunner("test_pipower", self.config)

    def tearDown(self):
        """Clean up after tests."""
        if self.runner.is_running:
            self.runner.stop()
        self.monitor_patcher.stop()

    def test_initialization(self):
        """Test runner initialization."""
        self.assertEqual(self.runner.name, "test_pipower")
        self.assertEqual(self.runner.state, RunnerState.STOPPED)
        self.assertTrue(self.runner.enabled)
        self.assertEqual(self.runner.interval, 0.1)
        self.assertEqual(self.runner.label, "Test PiPower")
        self.assertEqual(self.runner._low_battery_alert_threshold, 2)
        self.assertEqual(self.runner._no_usb_alert_threshold, 2)

    def test_start_stop(self):
        """Test starting and stopping the runner."""
        # Configure mock monitor
        self.mock_monitor.get_reading.return_value = PiPowerReading(
            battery_voltage=7.4,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=False,
            timestamp=time.time(),
        )

        # Start the runner
        self.assertTrue(self.runner.start())
        self.assertEqual(self.runner.state, RunnerState.RUNNING)
        self.assertTrue(self.runner.is_running)

        # Wait for some work cycles
        time.sleep(0.3)
        self.assertGreater(len(self.runner._reading_history), 0)

        # Stop the runner
        self.assertTrue(self.runner.stop())
        self.assertEqual(self.runner.state, RunnerState.STOPPED)
        self.assertFalse(self.runner.is_running)

    def test_power_alerts(self):
        """Test power alert generation."""
        # Start with normal readings
        normal_reading = PiPowerReading(
            battery_voltage=7.4,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=False,
            timestamp=time.time(),
        )
        self.mock_monitor.get_reading.return_value = normal_reading

        self.runner.start()
        time.sleep(0.3)  # Let it take some normal readings

        # Verify no alerts initially
        self.assertEqual(self.runner._consecutive_low_battery, 0)
        self.assertEqual(self.runner._consecutive_no_usb, 0)

        # Simulate low battery condition
        low_battery_reading = PiPowerReading(
            battery_voltage=6.5,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=True,
            timestamp=time.time(),
        )
        self.mock_monitor.get_reading.return_value = low_battery_reading
        time.sleep(0.3)  # Let it detect low battery
        self.assertGreaterEqual(self.runner._consecutive_low_battery, 2)

        # Simulate USB power loss
        no_usb_reading = PiPowerReading(
            battery_voltage=6.5,
            is_usb_power_input=False,
            is_charging=False,
            is_low_battery=True,
            timestamp=time.time(),
        )
        self.mock_monitor.get_reading.return_value = no_usb_reading
        time.sleep(0.3)  # Let it detect USB loss
        self.assertGreaterEqual(self.runner._consecutive_no_usb, 2)

    def test_power_stats(self):
        """Test power statistics calculation."""
        # Generate test readings that will be cycled through
        readings = [
            PiPowerReading(
                battery_voltage=7.4,
                is_usb_power_input=True,
                is_charging=True,
                is_low_battery=False,
                timestamp=time.time(),
            ),
            PiPowerReading(
                battery_voltage=7.2,
                is_usb_power_input=True,
                is_charging=False,
                is_low_battery=False,
                timestamp=time.time(),
            ),
            PiPowerReading(
                battery_voltage=7.0,
                is_usb_power_input=False,
                is_charging=False,
                is_low_battery=True,
                timestamp=time.time(),
            ),
        ]

        # Configure mock to cycle through readings repeatedly
        def reading_cycle():
            while True:
                for reading in readings:
                    yield reading

        self.mock_monitor.get_reading.side_effect = reading_cycle()

        self.runner.start()
        time.sleep(0.3)  # Let it collect readings

        stats = self.runner.get_power_stats()
        self.assertIsNotNone(stats)
        self.assertIsInstance(stats, PowerStats)

        # Check stats calculations
        self.assertAlmostEqual(stats.avg_battery_voltage, 7.2, places=1)
        self.assertEqual(stats.min_battery_voltage, 7.0)
        self.assertEqual(stats.max_battery_voltage, 7.4)
        self.assertGreaterEqual(stats.usb_power_percent, 60)  # 2 out of 3 readings
        self.assertGreaterEqual(stats.charging_percent, 30)  # 1 out of 3 readings
        self.assertGreaterEqual(stats.low_battery_percent, 30)  # 1 out of 3 readings

    def test_error_handling(self):
        """Test error handling during work cycle."""
        # Start normally
        self.mock_monitor.get_reading.return_value = PiPowerReading(
            battery_voltage=7.4,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=False,
            timestamp=time.time(),
        )

        self.runner.start()
        time.sleep(0.2)  # Let it run normally

        # Introduce sensor read error
        self.mock_monitor.get_reading.side_effect = SensorReadError("Test sensor error")
        time.sleep(0.3)  # Let error occur

        # Runner should continue running (default error handling for SensorReadError)
        self.assertTrue(self.runner.is_running)
        self.assertGreater(self.runner._error_count, 0)
        self.assertIn("Test sensor error", str(self.runner._last_error))

    def test_enhanced_status(self):
        """Test enhanced status reporting."""
        self.mock_monitor.is_healthy.return_value = True

        reading = PiPowerReading(
            battery_voltage=7.4,
            is_usb_power_input=True,
            is_charging=True,
            is_low_battery=False,
            timestamp=time.time(),
        )
        self.mock_monitor.get_reading.return_value = reading

        self.runner.start()
        time.sleep(0.2)

        status = self.runner.get_enhanced_status()

        self.assertIn("base_status", status)
        self.assertEqual(status["label"], "Test PiPower")
        self.assertTrue(status["power_monitor_healthy"])
        self.assertIsNotNone(status["last_reading"])
        self.assertEqual(status["last_reading"]["battery_voltage"], 7.4)
        self.assertTrue(status["last_reading"]["is_usb_power_input"])
        self.assertTrue(status["last_reading"]["is_charging"])
        self.assertFalse(status["last_reading"]["is_low_battery"])
        self.assertIn("power_stats", status)
        self.assertIn("alert_counts", status)
        self.assertIn("alert_thresholds", status)


class TestPowerStatsDataClass(unittest.TestCase):
    """Test cases for PowerStats data class."""

    def test_power_stats_creation(self):
        """Test PowerStats data class creation and attributes."""
        stats = PowerStats(
            avg_battery_voltage=7.4,
            min_battery_voltage=7.0,
            max_battery_voltage=7.8,
            usb_power_percent=80.0,
            charging_percent=60.0,
            low_battery_percent=20.0,
            sample_count=10,
        )

        self.assertEqual(stats.avg_battery_voltage, 7.4)
        self.assertEqual(stats.min_battery_voltage, 7.0)
        self.assertEqual(stats.max_battery_voltage, 7.8)
        self.assertEqual(stats.usb_power_percent, 80.0)
        self.assertEqual(stats.charging_percent, 60.0)
        self.assertEqual(stats.low_battery_percent, 20.0)
        self.assertEqual(stats.sample_count, 10)

    def test_power_stats_optional_voltage(self):
        """Test PowerStats with optional voltage values."""
        stats = PowerStats(
            avg_battery_voltage=None,
            min_battery_voltage=None,
            max_battery_voltage=None,
            usb_power_percent=80.0,
            charging_percent=60.0,
            low_battery_percent=20.0,
            sample_count=10,
        )

        self.assertIsNone(stats.avg_battery_voltage)
        self.assertIsNone(stats.min_battery_voltage)
        self.assertIsNone(stats.max_battery_voltage)
        self.assertEqual(stats.usb_power_percent, 80.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
