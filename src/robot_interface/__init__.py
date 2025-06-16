"""
Robot Interface Package for SOLAR Robot

This package provides comprehensive robot interfacing capabilities including:
- REST API server for external communication
- Local database for data persistence
- Offline queue management for commands and data
- Deep tracking of robot status and activities
- Photo management and storage
"""

from .api_server import RobotAPIServer
from .database import RobotDatabase
from .models import PhotoMetadata, RobotCommand, RobotStatus, SensorData, SystemHealth
from .queue_manager import QueueManager

__all__ = [
    "RobotAPIServer",
    "RobotDatabase",
    "QueueManager",
    "RobotStatus",
    "SensorData",
    "RobotCommand",
    "PhotoMetadata",
    "SystemHealth",
]
