"""
Database Module for Robot Interface

This module provides database functionality for storing robot data locally.
Uses SQLAlchemy with async support for efficient data management.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import Column

from .models import (
    CommandStatus,
    CommandType,
    PhotoMetadata,
    QueueItem,
    QueuePriority,
    RobotCommand,
    RobotState,
    RobotStatus,
    SensorData,
    SensorType,
)

Base = declarative_base()


class RobotStatusTable(Base):
    """Database table for robot status."""

    __tablename__ = "robot_status"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    state = Column(String, nullable=False)
    battery_level = Column(Float, nullable=False)
    battery_voltage = Column(Float)
    battery_current = Column(Float)
    is_charging = Column(Boolean, default=False)
    is_docked = Column(Boolean, default=False)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    temperature = Column(Float)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    heading = Column(Float)
    speed = Column(Float)
    last_activity = Column(DateTime)
    activity_description = Column(Text)
    mission_id = Column(String)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    error_severity = Column(String)
    wifi_strength = Column(Integer)
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime)
    metadata = Column(Text)  # JSON string


class SensorDataTable(Base):
    """Database table for sensor data."""

    __tablename__ = "sensor_data"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    sensor_type = Column(String, nullable=False, index=True)
    sensor_id = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=False)  # JSON string for mixed types
    unit = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    accuracy = Column(Float)
    confidence = Column(Float)
    metadata = Column(Text)  # JSON string


class RobotCommandTable(Base):
    """Database table for robot commands."""

    __tablename__ = "robot_commands"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    command_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    priority = Column(String, nullable=False, index=True)
    parameters = Column(Text)  # JSON string
    timeout = Column(Float)
    queued_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    result = Column(Text)  # JSON string
    error_message = Column(Text)
    return_code = Column(Integer)
    source = Column(String)
    user_id = Column(String)
    metadata = Column(Text)  # JSON string


class PhotoMetadataTable(Base):
    """Database table for photo metadata."""

    __tablename__ = "photo_metadata"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, default="image/jpeg")
    width = Column(Integer)
    height = Column(Integer)
    resolution = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    heading = Column(Float)
    camera_id = Column(String)
    exposure_time = Column(Float)
    iso = Column(Integer)
    aperture = Column(Float)
    tags = Column(Text)  # JSON string
    description = Column(Text)
    uploaded = Column(Boolean, default=False)
    uploaded_at = Column(DateTime)
    storage_url = Column(String)
    metadata = Column(Text)  # JSON string


class SystemHealthTable(Base):
    """Database table for system health."""

    __tablename__ = "system_health"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    overall_health = Column(Float, nullable=False)
    health_status = Column(String, nullable=False)
    sensors_health = Column(Float, nullable=False)
    motors_health = Column(Float, nullable=False)
    battery_health = Column(Float, nullable=False)
    communication_health = Column(Float, nullable=False)
    software_health = Column(Float, nullable=False)
    uptime = Column(Float, nullable=False)
    temperature = Column(Float)
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    critical_errors = Column(Text)  # JSON string
    response_time = Column(Float)
    throughput = Column(Float)
    recommendations = Column(Text)  # JSON string
    maintenance_due = Column(Boolean, default=False)
    next_maintenance = Column(DateTime)
    metadata = Column(Text)  # JSON string


class QueueItemTable(Base):
    """Database table for queue items."""

    __tablename__ = "queue_items"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    priority = Column(String, nullable=False, index=True)
    item_type = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON string
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry = Column(DateTime)
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime)
    error_message = Column(Text)


class RobotDatabase:
    """Database manager for robot interface data."""

    def __init__(self, db_path: str = "data/robot.db"):
        """
        Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(__name__)

        # Create async engine
        self.async_engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
            future=True,
        )

        # Create sync engine for initialization
        self.sync_engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
        )

        # Session factories
        self.async_session_factory = sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self) -> bool:
        """Initialize the database and create tables."""
        try:
            # Create tables using sync engine
            Base.metadata.create_all(self.sync_engine)

            # Test async connection
            async with self.async_session_factory() as session:
                await session.execute(select(1))

            self.logger.info(f"Database initialized at {self.db_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False

    async def close(self) -> None:
        """Close database connections."""
        await self.async_engine.dispose()
        self.sync_engine.dispose()
        self.logger.info("Database connections closed")

    # Robot Status Methods
    async def save_robot_status(self, status: RobotStatus) -> bool:
        """Save robot status to database."""
        try:
            async with self.async_session_factory() as session:
                db_status = RobotStatusTable(
                    id=str(status.id),
                    timestamp=status.timestamp,
                    state=status.state.value,
                    battery_level=status.battery_level,
                    battery_voltage=status.battery_voltage,
                    battery_current=status.battery_current,
                    is_charging=status.is_charging,
                    is_docked=status.is_docked,
                    cpu_usage=status.cpu_usage,
                    memory_usage=status.memory_usage,
                    disk_usage=status.disk_usage,
                    temperature=status.temperature,
                    latitude=status.latitude,
                    longitude=status.longitude,
                    altitude=status.altitude,
                    heading=status.heading,
                    speed=status.speed,
                    last_activity=status.last_activity,
                    activity_description=status.activity_description,
                    mission_id=status.mission_id,
                    error_count=status.error_count,
                    last_error=status.last_error,
                    error_severity=status.error_severity,
                    wifi_strength=status.wifi_strength,
                    is_online=status.is_online,
                    last_heartbeat=status.last_heartbeat,
                    metadata=str(status.metadata),
                )
                session.add(db_status)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save robot status: {e}")
            return False

    async def get_latest_robot_status(self) -> Optional[RobotStatus]:
        """Get the latest robot status."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(
                    select(RobotStatusTable)
                    .order_by(RobotStatusTable.timestamp.desc())
                    .limit(1)
                )
                db_status = result.scalar_one_or_none()

                if db_status:
                    return RobotStatus(
                        id=UUID(db_status.id),
                        timestamp=db_status.timestamp,
                        state=RobotState(db_status.state),
                        battery_level=db_status.battery_level,
                        battery_voltage=db_status.battery_voltage,
                        battery_current=db_status.battery_current,
                        is_charging=db_status.is_charging,
                        is_docked=db_status.is_docked,
                        cpu_usage=db_status.cpu_usage,
                        memory_usage=db_status.memory_usage,
                        disk_usage=db_status.disk_usage,
                        temperature=db_status.temperature,
                        latitude=db_status.latitude,
                        longitude=db_status.longitude,
                        altitude=db_status.altitude,
                        heading=db_status.heading,
                        speed=db_status.speed,
                        last_activity=db_status.last_activity,
                        activity_description=db_status.activity_description,
                        mission_id=db_status.mission_id,
                        error_count=db_status.error_count,
                        last_error=db_status.last_error,
                        error_severity=db_status.error_severity,
                        wifi_strength=db_status.wifi_strength,
                        is_online=db_status.is_online,
                        last_heartbeat=db_status.last_heartbeat,
                        metadata=eval(db_status.metadata) if db_status.metadata else {},
                    )
                return None
        except Exception as e:
            self.logger.error(f"Failed to get latest robot status: {e}")
            return None

    # Sensor Data Methods
    async def save_sensor_data(self, data: SensorData) -> bool:
        """Save sensor data to database."""
        try:
            async with self.async_session_factory() as session:
                db_data = SensorDataTable(
                    id=str(data.id),
                    timestamp=data.timestamp,
                    sensor_type=data.sensor_type.value,
                    sensor_id=data.sensor_id,
                    value=str(data.value),
                    unit=data.unit,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    altitude=data.altitude,
                    accuracy=data.accuracy,
                    confidence=data.confidence,
                    metadata=str(data.metadata),
                )
                session.add(db_data)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save sensor data: {e}")
            return False

    async def get_recent_sensor_data(self, limit: int = 50) -> List[SensorData]:
        """Get recent sensor data."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(
                    select(SensorDataTable)
                    .order_by(SensorDataTable.timestamp.desc())
                    .limit(limit)
                )
                db_data_list = result.scalars().all()

                sensor_data_list = []
                for db_data in db_data_list:
                    # Parse value based on type
                    try:
                        value = eval(db_data.value)
                    except:
                        value = db_data.value

                    sensor_data = SensorData(
                        id=UUID(db_data.id),
                        timestamp=db_data.timestamp,
                        sensor_type=SensorType(db_data.sensor_type),
                        sensor_id=db_data.sensor_id,
                        value=value,
                        unit=db_data.unit,
                        latitude=db_data.latitude,
                        longitude=db_data.longitude,
                        altitude=db_data.altitude,
                        accuracy=db_data.accuracy,
                        confidence=db_data.confidence,
                        metadata=eval(db_data.metadata) if db_data.metadata else {},
                    )
                    sensor_data_list.append(sensor_data)

                return sensor_data_list
        except Exception as e:
            self.logger.error(f"Failed to get recent sensor data: {e}")
            return []

    # Robot Command Methods
    async def save_robot_command(self, command: RobotCommand) -> bool:
        """Save robot command to database."""
        try:
            async with self.async_session_factory() as session:
                db_command = RobotCommandTable(
                    id=str(command.id),
                    timestamp=command.timestamp,
                    command_type=command.command_type.value,
                    status=command.status.value,
                    priority=command.priority.value,
                    parameters=str(command.parameters),
                    timeout=command.timeout,
                    queued_at=command.queued_at,
                    started_at=command.started_at,
                    completed_at=command.completed_at,
                    result=str(command.result) if command.result else None,
                    error_message=command.error_message,
                    return_code=command.return_code,
                    source=command.source,
                    user_id=command.user_id,
                    metadata=str(command.metadata),
                )
                session.add(db_command)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save robot command: {e}")
            return False

    async def get_recent_commands(self, limit: int = 10) -> List[RobotCommand]:
        """Get recent robot commands."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(
                    select(RobotCommandTable)
                    .order_by(RobotCommandTable.timestamp.desc())
                    .limit(limit)
                )
                db_command_list = result.scalars().all()

                command_list = []
                for db_command in db_command_list:
                    command = RobotCommand(
                        id=UUID(db_command.id),
                        timestamp=db_command.timestamp,
                        command_type=CommandType(db_command.command_type),
                        status=CommandStatus(db_command.status),
                        priority=QueuePriority(db_command.priority),
                        parameters=(
                            eval(db_command.parameters) if db_command.parameters else {}
                        ),
                        timeout=db_command.timeout,
                        queued_at=db_command.queued_at,
                        started_at=db_command.started_at,
                        completed_at=db_command.completed_at,
                        result=eval(db_command.result) if db_command.result else None,
                        error_message=db_command.error_message,
                        return_code=db_command.return_code,
                        source=db_command.source,
                        user_id=db_command.user_id,
                        metadata=(
                            eval(db_command.metadata) if db_command.metadata else {}
                        ),
                    )
                    command_list.append(command)

                return command_list
        except Exception as e:
            self.logger.error(f"Failed to get recent commands: {e}")
            return []

    async def update_command_status(
        self,
        command_id: UUID,
        status: CommandStatus,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update command status."""
        try:
            async with self.async_session_factory() as session:
                stmt = (
                    update(RobotCommandTable)
                    .where(RobotCommandTable.id == str(command_id))
                    .values(
                        status=status.value,
                        result=str(result) if result else None,
                        error_message=error_message,
                        completed_at=(
                            datetime.utcnow()
                            if status in [CommandStatus.COMPLETED, CommandStatus.FAILED]
                            else None
                        ),
                    )
                )
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to update command status: {e}")
            return False

    # Photo Metadata Methods
    async def save_photo_metadata(self, photo: PhotoMetadata) -> bool:
        """Save photo metadata to database."""
        try:
            async with self.async_session_factory() as session:
                db_photo = PhotoMetadataTable(
                    id=str(photo.id),
                    timestamp=photo.timestamp,
                    filename=photo.filename,
                    file_path=photo.file_path,
                    file_size=photo.file_size,
                    mime_type=photo.mime_type,
                    width=photo.width,
                    height=photo.height,
                    resolution=photo.resolution,
                    latitude=photo.latitude,
                    longitude=photo.longitude,
                    altitude=photo.altitude,
                    heading=photo.heading,
                    camera_id=photo.camera_id,
                    exposure_time=photo.exposure_time,
                    iso=photo.iso,
                    aperture=photo.aperture,
                    tags=str(photo.tags),
                    description=photo.description,
                    uploaded=photo.uploaded,
                    uploaded_at=photo.uploaded_at,
                    storage_url=photo.storage_url,
                    metadata=str(photo.metadata),
                )
                session.add(db_photo)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save photo metadata: {e}")
            return False

    async def get_recent_photos(self, limit: int = 20) -> List[PhotoMetadata]:
        """Get recent photo metadata."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(
                    select(PhotoMetadataTable)
                    .order_by(PhotoMetadataTable.timestamp.desc())
                    .limit(limit)
                )
                db_photo_list = result.scalars().all()

                photo_list = []
                for db_photo in db_photo_list:
                    photo = PhotoMetadata(
                        id=UUID(db_photo.id),
                        timestamp=db_photo.timestamp,
                        filename=db_photo.filename,
                        file_path=db_photo.file_path,
                        file_size=db_photo.file_size,
                        mime_type=db_photo.mime_type,
                        width=db_photo.width,
                        height=db_photo.height,
                        resolution=db_photo.resolution,
                        latitude=db_photo.latitude,
                        longitude=db_photo.longitude,
                        altitude=db_photo.altitude,
                        heading=db_photo.heading,
                        camera_id=db_photo.camera_id,
                        exposure_time=db_photo.exposure_time,
                        iso=db_photo.iso,
                        aperture=db_photo.aperture,
                        tags=eval(db_photo.tags) if db_photo.tags else [],
                        description=db_photo.description,
                        uploaded=db_photo.uploaded,
                        uploaded_at=db_photo.uploaded_at,
                        storage_url=db_photo.storage_url,
                        metadata=eval(db_photo.metadata) if db_photo.metadata else {},
                    )
                    photo_list.append(photo)

                return photo_list
        except Exception as e:
            self.logger.error(f"Failed to get recent photos: {e}")
            return []

    # Queue Item Methods
    async def save_queue_item(self, item: QueueItem) -> bool:
        """Save queue item to database."""
        try:
            async with self.async_session_factory() as session:
                db_item = QueueItemTable(
                    id=str(item.id),
                    timestamp=item.timestamp,
                    priority=item.priority.value,
                    item_type=item.item_type,
                    payload=str(item.payload),
                    retry_count=item.retry_count,
                    max_retries=item.max_retries,
                    next_retry=item.next_retry,
                    processed=item.processed,
                    processed_at=item.processed_at,
                    error_message=item.error_message,
                )
                session.add(db_item)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to save queue item: {e}")
            return False

    async def get_pending_queue_items(self, limit: int = 100) -> List[QueueItem]:
        """Get pending queue items ordered by priority and timestamp."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute(
                    select(QueueItemTable)
                    .where(QueueItemTable.processed == False)
                    .order_by(
                        QueueItemTable.priority.desc(), QueueItemTable.timestamp.asc()
                    )
                    .limit(limit)
                )
                db_item_list = result.scalars().all()

                item_list = []
                for db_item in db_item_list:
                    item = QueueItem(
                        id=UUID(db_item.id),
                        timestamp=db_item.timestamp,
                        priority=QueuePriority(db_item.priority),
                        item_type=db_item.item_type,
                        payload=eval(db_item.payload),
                        retry_count=db_item.retry_count,
                        max_retries=db_item.max_retries,
                        next_retry=db_item.next_retry,
                        processed=db_item.processed,
                        processed_at=db_item.processed_at,
                        error_message=db_item.error_message,
                    )
                    item_list.append(item)

                return item_list
        except Exception as e:
            self.logger.error(f"Failed to get pending queue items: {e}")
            return []

    async def mark_queue_item_processed(
        self, item_id: UUID, success: bool = True, error_message: Optional[str] = None
    ) -> bool:
        """Mark queue item as processed."""
        try:
            async with self.async_session_factory() as session:
                stmt = (
                    update(QueueItemTable)
                    .where(QueueItemTable.id == str(item_id))
                    .values(
                        processed=True,
                        processed_at=datetime.utcnow(),
                        error_message=error_message if not success else None,
                    )
                )
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            self.logger.error(f"Failed to mark queue item as processed: {e}")
            return False

    # Cleanup Methods
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old data older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0

        try:
            async with self.async_session_factory() as session:
                # Clean up old status records
                result = await session.execute(
                    select(func.count(RobotStatusTable.id)).where(
                        RobotStatusTable.timestamp < cutoff_date
                    )
                )
                status_count = result.scalar()

                await session.execute(
                    RobotStatusTable.__table__.delete().where(
                        RobotStatusTable.timestamp < cutoff_date
                    )
                )

                # Clean up old sensor data
                result = await session.execute(
                    select(func.count(SensorDataTable.id)).where(
                        SensorDataTable.timestamp < cutoff_date
                    )
                )
                sensor_count = result.scalar()

                await session.execute(
                    SensorDataTable.__table__.delete().where(
                        SensorDataTable.timestamp < cutoff_date
                    )
                )

                # Clean up old commands
                result = await session.execute(
                    select(func.count(RobotCommandTable.id)).where(
                        RobotCommandTable.timestamp < cutoff_date
                    )
                )
                command_count = result.scalar()

                await session.execute(
                    RobotCommandTable.__table__.delete().where(
                        RobotCommandTable.timestamp < cutoff_date
                    )
                )

                # Clean up old photos
                result = await session.execute(
                    select(func.count(PhotoMetadataTable.id)).where(
                        PhotoMetadataTable.timestamp < cutoff_date
                    )
                )
                photo_count = result.scalar()

                await session.execute(
                    PhotoMetadataTable.__table__.delete().where(
                        PhotoMetadataTable.timestamp < cutoff_date
                    )
                )

                # Clean up old queue items
                result = await session.execute(
                    select(func.count(QueueItemTable.id)).where(
                        QueueItemTable.timestamp < cutoff_date
                    )
                )
                queue_count = result.scalar()

                await session.execute(
                    QueueItemTable.__table__.delete().where(
                        QueueItemTable.timestamp < cutoff_date
                    )
                )

                await session.commit()

                deleted_count = (
                    status_count
                    + sensor_count
                    + command_count
                    + photo_count
                    + queue_count
                )
                self.logger.info(f"Cleaned up {deleted_count} old records")

        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")

        return deleted_count
