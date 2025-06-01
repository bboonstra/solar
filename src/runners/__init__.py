"""
Runner System for SOLAR Robot

This package implements the threaded runner system for concurrent sensor
monitoring and system operations. The architecture provides:

- Thread-safe concurrent execution
- Automatic error recovery
- Health monitoring
- Graceful shutdown handling
- Extensible base classes for new runners

Core Components:
    - BaseRunner: Abstract base class for all runners
    - RunnerManager: Central coordinator for all runners
    - INA219Runner: Power monitoring runner implementation

Usage:
    from runners import RunnerManager

    runner_manager = RunnerManager(config, production=False)
    runner_manager.start()
"""

from .base_runner import BaseRunner, RunnerState, RunnerStatus
from .ina219_runner import INA219Runner, PowerStats
from .runner_manager import RunnerManager, SystemStatus

__all__ = [
    "BaseRunner",
    "RunnerState",
    "RunnerStatus",
    "INA219Runner",
    "PowerStats",
    "RunnerManager",
    "SystemStatus",
]
