"""
PiPower Runner Module for SOLAR Robot

This module provides a threaded runner for monitoring the PiPower V2 UPS.
It continuously monitors battery status, power input, and charging state.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sensors.pipower_monitor import PiPowerMonitor, PiPowerReading, SensorReadError

from .base_runner import BaseRunner


@dataclass
class PowerStats:
    """Statistics for power readings over time."""

    avg_battery_voltage: Optional[float]
    min_battery_voltage: Optional[float]
    max_battery_voltage: Optional[float]
    usb_power_percent: float  # Percentage of time USB power was available
    charging_percent: float  # Percentage of time spent charging
    low_battery_percent: float  # Percentage of time in low battery state
    sample_count: int


class PiPowerRunner(BaseRunner):
    """
    Threaded runner for PiPower monitoring.

    Continuously takes power readings and maintains statistics.
    Provides alerts for power conditions like low battery and power input changes.
    """

    def __init__(
        self, runner_id: str, config: Dict[str, Any], production: bool = False
    ):
        """
        Initialize the PiPower runner.

        Args:
            runner_id: Unique identifier for this runner instance
            config: Configuration dictionary for this runner instance
            production: Whether running in production mode
        """
        super().__init__(runner_id, config, production)

        # Get runner-specific config
        self.label = config.get("label", runner_id)

        # Statistics tracking
        self.max_history_size = 100  # Keep last 100 readings for stats
        self._reading_history: deque = deque(maxlen=self.max_history_size)
        self._last_reading: Optional[PiPowerReading] = None

        # Alert tracking
        self._consecutive_low_battery = 0
        self._consecutive_no_usb = 0
        self._low_battery_alert_threshold = self._get_config_value(
            "low_battery_alert_threshold", 3
        )
        self._no_usb_alert_threshold = self._get_config_value(
            "no_usb_alert_threshold", 3
        )

        # Power monitor instance
        self.power_monitor: Optional[PiPowerMonitor] = None

    def _initialize(self) -> bool:
        """Initialize the PiPower monitor."""
        try:
            # Create power monitor with instance-specific config
            self.power_monitor = PiPowerMonitor(
                {"pipower": self.config}, self.production
            )

            # Take a test reading to verify functionality
            test_reading = self.power_monitor.get_reading()

            status_parts = []
            if test_reading.battery_voltage is not None:
                status_parts.append(f"Battery: {test_reading.battery_voltage:.2f}V")
            if test_reading.is_usb_power_input is not None:
                status_parts.append(
                    "USB Power" if test_reading.is_usb_power_input else "No USB"
                )
            if test_reading.is_charging is not None:
                status_parts.append(
                    "Charging" if test_reading.is_charging else "Not Charging"
                )
            if test_reading.is_low_battery is not None:
                status_parts.append(
                    "LOW BATT" if test_reading.is_low_battery else "Battery OK"
                )

            self.logger.info(
                f"{self.label} initialized successfully - "
                f"Status: {', '.join(status_parts)}"
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

            # Check conditions and generate alerts
            self._check_power_alerts(reading)

        except SensorReadError as e:
            self.logger.error(f"Sensor read error in {self.label}: {e}")
            raise  # Re-raise so base class can handle it

    def _check_power_alerts(self, reading: PiPowerReading) -> None:
        """Check power reading conditions and generate alerts."""
        # Check low battery condition
        if reading.is_low_battery:
            self._consecutive_low_battery += 1
            if self._consecutive_low_battery == self._low_battery_alert_threshold:
                voltage_str = (
                    f" ({reading.battery_voltage:.2f}V)"
                    if reading.battery_voltage is not None
                    else ""
                )
                self.logger.warning(
                    f"{self.label} - LOW BATTERY ALERT{voltage_str} - "
                    f"Low battery detected for {self._consecutive_low_battery} consecutive readings"
                )
        else:
            self._consecutive_low_battery = 0

        # Check USB power input
        if not reading.is_usb_power_input:
            self._consecutive_no_usb += 1
            if self._consecutive_no_usb == self._no_usb_alert_threshold:
                self.logger.warning(
                    f"{self.label} - USB POWER LOST - "
                    f"No USB power detected for {self._consecutive_no_usb} consecutive readings"
                )
        else:
            if self._consecutive_no_usb >= self._no_usb_alert_threshold:
                self.logger.info(f"{self.label} - USB power restored")
            self._consecutive_no_usb = 0

    def is_healthy(self) -> bool:
        """Check if the PiPower runner is healthy."""
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

    def get_last_reading(self) -> Optional[PiPowerReading]:
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
        voltages = [
            r.battery_voltage for r in readings if r.battery_voltage is not None
        ]
        usb_power_count = sum(1 for r in readings if r.is_usb_power_input)
        charging_count = sum(1 for r in readings if r.is_charging)
        low_battery_count = sum(1 for r in readings if r.is_low_battery)

        return PowerStats(
            avg_battery_voltage=sum(voltages) / len(voltages) if voltages else None,
            min_battery_voltage=min(voltages) if voltages else None,
            max_battery_voltage=max(voltages) if voltages else None,
            usb_power_percent=(usb_power_count / len(readings)) * 100,
            charging_percent=(charging_count / len(readings)) * 100,
            low_battery_percent=(low_battery_count / len(readings)) * 100,
            sample_count=len(readings),
        )

    def get_reading_history(self, count: Optional[int] = None) -> List[PiPowerReading]:
        """
        Get recent power readings.

        Args:
            count: Maximum number of readings to return (default: all)

        Returns:
            List of PiPowerReading objects
        """
        readings = list(self._reading_history)
        if count is not None:
            readings = readings[-count:]
        return readings

    def _cleanup(self) -> None:
        """Cleanup PiPower-specific resources."""
        if self.power_monitor:
            self.logger.info("Cleaning up PiPower monitor")
            self.power_monitor.cleanup()
            self.power_monitor = None

    def _handle_error(self, error: Exception) -> bool:
        """
        Handle errors specific to PiPower operations.

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
        stats = self.get_power_stats()

        enhanced = {
            "base_status": base_status,
            "label": self.label,
            "power_monitor_healthy": (
                self.power_monitor.is_healthy() if self.power_monitor else False
            ),
            "last_reading": None,
            "power_stats": None,
            "alert_counts": {
                "consecutive_low_battery": self._consecutive_low_battery,
                "consecutive_no_usb": self._consecutive_no_usb,
            },
            "alert_thresholds": {
                "low_battery": self._low_battery_alert_threshold,
                "no_usb": self._no_usb_alert_threshold,
            },
            "history_size": len(self._reading_history),
        }

        # Add last reading info
        if self._last_reading:
            enhanced["last_reading"] = {
                "battery_voltage": self._last_reading.battery_voltage,
                "is_usb_power_input": self._last_reading.is_usb_power_input,
                "is_charging": self._last_reading.is_charging,
                "is_low_battery": self._last_reading.is_low_battery,
                "timestamp": self._last_reading.timestamp,
            }

        # Add power statistics
        if stats:
            enhanced["power_stats"] = {
                "avg_battery_voltage": stats.avg_battery_voltage,
                "min_battery_voltage": stats.min_battery_voltage,
                "max_battery_voltage": stats.max_battery_voltage,
                "usb_power_percent": stats.usb_power_percent,
                "charging_percent": stats.charging_percent,
                "low_battery_percent": stats.low_battery_percent,
                "sample_count": stats.sample_count,
            }

        return enhanced
