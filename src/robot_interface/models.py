"""
Data Models for Robot Interface

This module defines the data models used throughout the robot interface system.
All models use Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RobotState(str, Enum):
    """Robot operational states."""

    IDLE = "idle"
    ACTIVE = "active"
    DOCKING = "docking"
    CHARGING = "charging"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    MISSION = "mission"


class CommandType(str, Enum):
    """Types of robot commands."""

    SYSTEM_CHECK = "system_check"
    CALIBRATE_SENSORS = "calibrate_sensors"
    UPDATE_CONFIG = "update_config"
    START_MISSION = "start_mission"
    RETURN_TO_DOCK = "return_to_dock"
    EMERGENCY_STOP = "emergency_stop"
    RESTART_SYSTEM = "restart_system"
    TAKE_PHOTO = "take_photo"
    CUSTOM = "custom"


class CommandStatus(str, Enum):
    """Command execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SensorType(str, Enum):
    """Types of sensors."""

    SOIL_MOISTURE = "soil_moisture"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"
    BATTERY = "battery"
    GPS = "gps"
    CAMERA = "camera"
    MOTION = "motion"


class QueuePriority(str, Enum):
    """Queue priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RobotStatus(BaseModel):
    """Robot status information."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Operational status
    state: RobotState = RobotState.IDLE
    battery_level: float = Field(ge=0.0, le=100.0)
    battery_voltage: Optional[float] = None
    battery_current: Optional[float] = None
    is_charging: bool = False
    is_docked: bool = False

    # System health
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    temperature: Optional[float] = None

    # Location and movement
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    heading: Optional[float] = Field(None, ge=0.0, le=360.0)
    speed: Optional[float] = Field(None, ge=0.0)

    # Activity tracking
    last_activity: Optional[datetime] = None
    activity_description: Optional[str] = None
    mission_id: Optional[str] = None

    # Error tracking
    error_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = None
    error_severity: Optional[str] = None

    # Connectivity
    wifi_strength: Optional[int] = Field(None, ge=0, le=100)
    is_online: bool = True
    last_heartbeat: Optional[datetime] = None

    # Custom data
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class SensorData(BaseModel):
    """Sensor data reading."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sensor_type: SensorType
    sensor_id: str

    # Sensor values
    value: Union[float, int, str, bool]
    unit: Optional[str] = None

    # Location context
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

    # Quality indicators
    accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class RobotCommand(BaseModel):
    """Robot command definition."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Command details
    command_type: CommandType
    status: CommandStatus = CommandStatus.PENDING
    priority: QueuePriority = QueuePriority.NORMAL

    # Command parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[float] = None  # seconds

    # Execution tracking
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    return_code: Optional[int] = None

    # Metadata
    source: Optional[str] = None  # API, local, scheduled, etc.
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class PhotoMetadata(BaseModel):
    """Photo metadata and information."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # File information
    filename: str
    file_path: str
    file_size: int = Field(ge=0)
    mime_type: str = "image/jpeg"

    # Image properties
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)
    resolution: Optional[str] = None

    # Location and context
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    heading: Optional[float] = Field(None, ge=0.0, le=360.0)

    # Camera settings
    camera_id: Optional[str] = None
    exposure_time: Optional[float] = None
    iso: Optional[int] = None
    aperture: Optional[float] = None

    # Content analysis
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    # Storage status
    uploaded: bool = False
    uploaded_at: Optional[datetime] = None
    storage_url: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class SystemHealth(BaseModel):
    """System health information."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Overall health
    overall_health: float = Field(ge=0.0, le=100.0)
    health_status: str = "unknown"  # excellent, good, fair, poor, critical

    # Component health
    sensors_health: float = Field(ge=0.0, le=100.0)
    motors_health: float = Field(ge=0.0, le=100.0)
    battery_health: float = Field(ge=0.0, le=100.0)
    communication_health: float = Field(ge=0.0, le=100.0)
    software_health: float = Field(ge=0.0, le=100.0)

    # System metrics
    uptime: float = Field(ge=0.0)  # seconds
    temperature: Optional[float] = None
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_usage: Optional[float] = Field(None, ge=0.0, le=100.0)

    # Error tracking
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    critical_errors: List[str] = Field(default_factory=list)

    # Performance metrics
    response_time: Optional[float] = None  # milliseconds
    throughput: Optional[float] = None  # operations per second

    # Recommendations
    recommendations: List[str] = Field(default_factory=list)
    maintenance_due: bool = False
    next_maintenance: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class APIResponse(BaseModel):
    """Standard API response format."""

    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class QueueItem(BaseModel):
    """Queue item for offline processing."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    priority: QueuePriority = QueuePriority.NORMAL
    item_type: str  # "command", "data", "photo"
    payload: Dict[str, Any]
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    next_retry: Optional[datetime] = None
    processed: bool = False
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
