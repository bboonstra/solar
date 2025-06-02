"""
INA219 Runner Module for SOLAR Robot

This module provides a threaded runner for the INA219 power monitor.
It continuously monitors power consumption in a separate thread.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sensors import INA219PowerMonitor
from sensors.ina219_power_monitor import PowerReading, SensorReadError

from .base_runner import BaseRunner


@dataclass
class PowerStats:
    """Statistics for power readings over time."""

    avg_voltage: float
    avg_current: float
    avg_power: float
    min_power: float
    max_power: float
    sample_count: int


class INA219Runner(BaseRunner):
    """
    Threaded runner for INA219 power monitoring.

    Continuously takes power readings and maintains statistics.
    Provides alerts for power threshold violations.
    """

    def __init__(
        self, runner_id: str, config: Dict[str, Any], production: bool = False
    ):
        """
        Initialize the INA219 runner.

        Args:
            runner_id: Unique identifier for this runner instance
            config: Configuration dictionary for this runner instance
            production: Whether running in production mode
        """
        # Get runner-specific config
        self.label = config.get("label", runner_id)

        # Convert hex string to integer for i2c_address
        i2c_addr_str = config.get("i2c_address", "0x40")
        self.i2c_address = int(i2c_addr_str, 16)

        # Create a config dict that matches the old structure for INA219PowerMonitor
        ina219_config = {
            "ina219": {
                "i2c_address": self.i2c_address,
                "measurement_interval": config.get("measurement_interval", 1.0),
                "log_measurements": config.get("log_measurements", True),
                "low_power_threshold": config.get("low_power_threshold", 0.5),
                "high_power_threshold": config.get("high_power_threshold", 10.0),
            }
        }

        super().__init__(runner_id, config, production)

        # INA219-specific configuration
        self.log_measurements = self._get_config_value("log_measurements", True)
        self.low_power_threshold = self._get_config_value("low_power_threshold", 0.5)
        self.high_power_threshold = self._get_config_value("high_power_threshold", 10.0)

        # Statistics tracking
        self.max_history_size = 100  # Keep last 100 readings for stats
        self._reading_history: deque = deque(maxlen=self.max_history_size)
        self._last_reading: Optional[PowerReading] = None

        # Power monitor instance
        self.power_monitor: Optional[INA219PowerMonitor] = None

        # Alert tracking
        self._consecutive_low_power = 0
        self._consecutive_high_power = 0
        self._low_power_alert_threshold = 3  # Alert after 3 consecutive readings
        self._high_power_alert_threshold = 3

        # Store the full config for the power monitor
        self._ina219_config = ina219_config

    def _initialize(self) -> bool:
        """Initialize the INA219 power monitor."""
        try:
            # Create power monitor with instance-specific config
            self.power_monitor = INA219PowerMonitor(
                self._ina219_config, self.production
            )

            # Take a test reading to verify functionality
            test_reading = self.power_monitor.get_reading()
            self.logger.debug(
                f"{self.label} initialized successfully - "
                f"Test reading: {test_reading.voltage:.2f}V, "
                f"{test_reading.current:.3f}A, {test_reading.power:.2f}W"
            )
            return True

        except SensorReadError as e:
            self.logger.error(f"Failed to initialize {self.label}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error initializing {self.label}: {e}")
            return False

    def _work_cycle(self) -> None:
        """Perform one power monitoring cycle."""
        if not self.power_monitor:
            raise RuntimeError(f"{self.label} not initialized")

        try:
            # Take a power reading
            reading = self.power_monitor.get_reading()
            self._last_reading = reading
            self._reading_history.append(reading)

            # Log the reading if enabled
            if self.log_measurements:
                self.logger.debug(
                    f"{self.label} - V: {reading.voltage:.2f}V, "
                    f"I: {reading.current:.3f}A, P: {reading.power:.2f}W"
                )

            # Check thresholds and generate alerts
            self._check_power_alerts(reading)

        except SensorReadError as e:
            self.logger.error(f"Sensor read error in {self.label}: {e}")
            # Don't stop the runner for sensor errors, just log them
            raise  # Re-raise so base class can handle it

    def _check_power_alerts(self, reading: PowerReading) -> None:
        """Check power reading against thresholds and generate alerts."""
        # Check low power threshold
        if reading.power < self.low_power_threshold:
            self._consecutive_low_power += 1
            self._consecutive_high_power = 0

            if self._consecutive_low_power == self._low_power_alert_threshold:
                self.logger.warning(
                    f"{self.label} - LOW POWER ALERT: {reading.power:.2f}W for "
                    f"{self._consecutive_low_power} consecutive readings "
                    f"(threshold: {self.low_power_threshold}W)"
                )

        # Check high power threshold
        elif reading.power > self.high_power_threshold:
            self._consecutive_high_power += 1
            self._consecutive_low_power = 0

            if self._consecutive_high_power == self._high_power_alert_threshold:
                self.logger.warning(
                    f"{self.label} - HIGH POWER ALERT: {reading.power:.2f}W for "
                    f"{self._consecutive_high_power} consecutive readings "
                    f"(threshold: {self.high_power_threshold}W)"
                )

        # Normal power range
        else:
            self._consecutive_low_power = 0
            self._consecutive_high_power = 0

    def is_healthy(self) -> bool:
        """Check if the INA219 runner is healthy."""
        if not self.power_monitor:
            return False

        # Check if we have recent readings
        if not self._last_reading:
            return False

        # Check if last reading is recent (within 2x the interval)
        time_since_last = time.time() - self._last_reading.timestamp
        if time_since_last > (self.interval * 2):
            return False

        # Use the power monitor's health check
        return self.power_monitor.is_healthy()

    def get_last_reading(self) -> Optional[PowerReading]:
        """Get the last power reading."""
        return self._last_reading

    def get_power_stats(self) -> Optional[PowerStats]:
        """
        Calculate power statistics from recent readings.

        Returns:
            PowerStats object or None if no readings available
        """
        if not self._reading_history:
            return None

        readings = list(self._reading_history)

        voltages = [r.voltage for r in readings]
        currents = [r.current for r in readings]
        powers = [r.power for r in readings]

        return PowerStats(
            avg_voltage=sum(voltages) / len(voltages),
            avg_current=sum(currents) / len(currents),
            avg_power=sum(powers) / len(powers),
            min_power=min(powers),
            max_power=max(powers),
            sample_count=len(readings),
        )

    def get_reading_history(self, count: Optional[int] = None) -> List[PowerReading]:
        """
        Get recent power readings.

        Args:
            count: Maximum number of readings to return (default: all)

        Returns:
            List of PowerReading objects
        """
        readings = list(self._reading_history)
        if count is not None:
            readings = readings[-count:]
        return readings

    def _cleanup(self) -> None:
        """Cleanup INA219-specific resources."""
        if self.power_monitor:
            self.logger.debug("Cleaning up INA219 power monitor")
            # INA219PowerMonitor doesn't have explicit cleanup,
            # but we can clear our reference
            self.power_monitor = None

    def _handle_error(self, error: Exception) -> bool:
        """
        Handle errors specific to INA219 operations.

        Args:
            error: The exception that occurred

        Returns:
            True to continue running, False to stop runner
        """
        if isinstance(error, SensorReadError):
            # For sensor read errors, continue running but increment error count
            self.logger.warning(
                f"Sensor read error in {self.label} (continuing): {error}"
            )
            return True

        # For other errors, use default handling
        return super()._handle_error(error)

    def get_enhanced_status(self) -> Dict[str, Any]:
        """
        Get enhanced status information including power statistics.

        Returns:
            Dictionary with comprehensive status information
        """
        base_status = self.get_status()

        enhanced = {
            "base_status": base_status,
            "label": self.label,
            "i2c_address": f"0x{self.i2c_address:02X}",
            "power_monitor_healthy": (
                self.power_monitor.is_healthy() if self.power_monitor else False
            ),
            "last_reading": None,
            "power_stats": None,
            "alert_counts": {
                "consecutive_low_power": self._consecutive_low_power,
                "consecutive_high_power": self._consecutive_high_power,
            },
            "thresholds": {
                "low_power": self.low_power_threshold,
                "high_power": self.high_power_threshold,
            },
            "history_size": len(self._reading_history),
        }

        # Add last reading info
        if self._last_reading:
            enhanced["last_reading"] = {
                "voltage": self._last_reading.voltage,
                "current": self._last_reading.current,
                "power": self._last_reading.power,
                "timestamp": self._last_reading.timestamp,
            }

        # Add power statistics
        stats = self.get_power_stats()
        if stats:
            enhanced["power_stats"] = {
                "avg_voltage": stats.avg_voltage,
                "avg_current": stats.avg_current,
                "avg_power": stats.avg_power,
                "min_power": stats.min_power,
                "max_power": stats.max_power,
                "sample_count": stats.sample_count,
            }

        return enhanced
