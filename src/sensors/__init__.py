"""
Sensor Modules for SOLAR Robot

This package contains sensor implementations for the SOLAR robot system.
Each sensor module provides interfaces for both hardware (production) and
simulated (development) modes.

Available Sensors:
    - INA219PowerMonitor: Voltage, current, and power monitoring

Exports:
    - INA219PowerMonitor: Main power monitor class
    - PowerReading: Data class for power measurements
    - SensorReadError: Exception for sensor read failures
"""

from .ina219_power_monitor import (INA219PowerMonitor, PowerReading,
                                   SensorReadError)

__all__ = ["INA219PowerMonitor", "PowerReading", "SensorReadError"]
