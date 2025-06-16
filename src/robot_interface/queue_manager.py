"""
Queue Manager for Robot Interface

This module provides offline queue management for robot commands and data.
Handles retry logic, priority queuing, and connection loss scenarios.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from .database import RobotDatabase
from .models import (
    CommandStatus,
    CommandType,
    PhotoMetadata,
    QueueItem,
    QueuePriority,
    RobotCommand,
    SensorData,
)


class QueueManager:
    """Manages offline queue for robot commands and data."""

    def __init__(self, database: RobotDatabase, config: Dict[str, Any]):
        """
        Initialize the queue manager.

        Args:
            database: Database instance for persistence
            config: Configuration dictionary
        """
        self.database = database
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Queue configuration
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 60)  # seconds
        self.batch_size = config.get("batch_size", 10)
        self.processing_interval = config.get("processing_interval", 30)  # seconds

        # Processing state
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # Callbacks for processing different item types
        self._processors: Dict[str, Callable] = {
            "command": self._process_command,
            "data": self._process_data,
            "photo": self._process_photo,
        }

        # Statistics
        self.stats = {
            "processed": 0,
            "failed": 0,
            "retried": 0,
            "pending": 0,
        }

    async def start(self) -> bool:
        """Start the queue processing."""
        if self._running:
            self.logger.warning("Queue manager already running")
            return True

        try:
            self._running = True
            self._stop_event.clear()
            self._processing_task = asyncio.create_task(self._processing_loop())
            self.logger.info("Queue manager started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start queue manager: {e}")
            self._running = False
            return False

    async def stop(self) -> None:
        """Stop the queue processing."""
        if not self._running:
            return

        self.logger.info("Stopping queue manager...")
        self._running = False
        self._stop_event.set()

        if self._processing_task:
            try:
                await asyncio.wait_for(self._processing_task, timeout=10.0)
            except asyncio.TimeoutError:
                self.logger.warning("Queue manager did not stop gracefully")
                self._processing_task.cancel()

        self.logger.info("Queue manager stopped")

    async def _processing_loop(self) -> None:
        """Main processing loop for queue items."""
        while self._running and not self._stop_event.is_set():
            try:
                # Get pending items
                pending_items = await self.database.get_pending_queue_items(
                    self.batch_size
                )
                self.stats["pending"] = len(pending_items)

                if not pending_items:
                    # No items to process, wait before next check
                    await asyncio.sleep(self.processing_interval)
                    continue

                # Process items in parallel
                tasks = []
                for item in pending_items:
                    if self._should_process_item(item):
                        task = asyncio.create_task(self._process_item(item))
                        tasks.append(task)

                if tasks:
                    # Wait for all tasks to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Update statistics
                    for result in results:
                        if isinstance(result, Exception):
                            self.stats["failed"] += 1
                        else:
                            self.stats["processed"] += 1

                # Wait before next processing cycle
                await asyncio.sleep(self.processing_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(self.processing_interval)

    def _should_process_item(self, item: QueueItem) -> bool:
        """Check if item should be processed now."""
        # Check if item is ready for retry
        if item.next_retry and datetime.utcnow() < item.next_retry:
            return False

        # Check if max retries exceeded
        if item.retry_count >= item.max_retries:
            return False

        return True

    async def _process_item(self, item: QueueItem) -> bool:
        """Process a single queue item."""
        try:
            processor = self._processors.get(item.item_type)
            if not processor:
                self.logger.error(f"Unknown item type: {item.item_type}")
                await self._mark_item_failed(
                    item, f"Unknown item type: {item.item_type}"
                )
                return False

            # Process the item
            success = await processor(item)

            if success:
                await self.database.mark_queue_item_processed(item.id, success=True)
                self.logger.debug(f"Successfully processed item {item.id}")
                return True
            else:
                # Increment retry count
                item.retry_count += 1
                self.stats["retried"] += 1

                if item.retry_count >= item.max_retries:
                    await self._mark_item_failed(item, "Max retries exceeded")
                    return False
                else:
                    # Schedule retry
                    item.next_retry = datetime.utcnow() + timedelta(
                        seconds=self.retry_delay * (2 ** (item.retry_count - 1))
                    )
                    await self.database.save_queue_item(item)
                    self.logger.debug(f"Scheduled retry for item {item.id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error processing item {item.id}: {e}")
            await self._mark_item_failed(item, str(e))
            return False

    async def _mark_item_failed(self, item: QueueItem, error_message: str) -> None:
        """Mark item as failed."""
        item.processed = True
        item.processed_at = datetime.utcnow()
        item.error_message = error_message
        await self.database.save_queue_item(item)

    async def _process_command(self, item: QueueItem) -> bool:
        """Process a command item."""
        try:
            command_data = item.payload
            command = RobotCommand(
                id=UUID(command_data["id"]),
                command_type=CommandType(command_data["command_type"]),
                parameters=command_data.get("parameters", {}),
                priority=QueuePriority(command_data.get("priority", "normal")),
                source=command_data.get("source", "queue"),
                user_id=command_data.get("user_id"),
                metadata=command_data.get("metadata", {}),
            )

            # Execute the command (this would integrate with the robot's command system)
            success = await self._execute_command(command)

            if success:
                # Update command status
                await self.database.save_robot_command(command)
                await self.database.update_command_status(
                    command.id, CommandStatus.COMPLETED, {"success": True}
                )
                return True
            else:
                await self.database.update_command_status(
                    command.id, CommandStatus.FAILED, None, "Command execution failed"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            return False

    async def _process_data(self, item: QueueItem) -> bool:
        """Process a data item."""
        try:
            data = item.payload
            sensor_data = SensorData(
                id=UUID(data["id"]),
                sensor_type=data["sensor_type"],
                sensor_id=data["sensor_id"],
                value=data["value"],
                unit=data.get("unit"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                altitude=data.get("altitude"),
                accuracy=data.get("accuracy"),
                confidence=data.get("confidence"),
                metadata=data.get("metadata", {}),
            )

            # Save to database
            success = await self.database.save_sensor_data(sensor_data)
            return success

        except Exception as e:
            self.logger.error(f"Error processing data: {e}")
            return False

    async def _process_photo(self, item: QueueItem) -> bool:
        """Process a photo item."""
        try:
            photo_data = item.payload
            photo = PhotoMetadata(
                id=UUID(photo_data["id"]),
                filename=photo_data["filename"],
                file_path=photo_data["file_path"],
                file_size=photo_data["file_size"],
                mime_type=photo_data.get("mime_type", "image/jpeg"),
                width=photo_data.get("width"),
                height=photo_data.get("height"),
                resolution=photo_data.get("resolution"),
                latitude=photo_data.get("latitude"),
                longitude=photo_data.get("longitude"),
                altitude=photo_data.get("altitude"),
                heading=photo_data.get("heading"),
                camera_id=photo_data.get("camera_id"),
                exposure_time=photo_data.get("exposure_time"),
                iso=photo_data.get("iso"),
                aperture=photo_data.get("aperture"),
                tags=photo_data.get("tags", []),
                description=photo_data.get("description"),
                metadata=photo_data.get("metadata", {}),
            )

            # Save to database
            success = await self.database.save_photo_metadata(photo)
            return success

        except Exception as e:
            self.logger.error(f"Error processing photo: {e}")
            return False

    async def _execute_command(self, command: RobotCommand) -> bool:
        """Execute a robot command."""
        # This would integrate with the robot's command execution system
        # For now, we'll simulate command execution

        try:
            self.logger.info(f"Executing command: {command.command_type.value}")

            # Simulate command execution time
            await asyncio.sleep(1.0)

            # Simulate different command types
            if command.command_type == CommandType.SYSTEM_CHECK:
                command.result = {"status": "healthy", "checks_passed": 5}
            elif command.command_type == CommandType.CALIBRATE_SENSORS:
                command.result = {"calibrated_sensors": ["temp", "humidity", "light"]}
            elif command.command_type == CommandType.TAKE_PHOTO:
                command.result = {"photo_path": "/data/photos/photo_001.jpg"}
            else:
                command.result = {"status": "completed"}

            return True

        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            command.error_message = str(e)
            return False

    # Public API methods
    async def queue_command(self, command: RobotCommand) -> bool:
        """Queue a command for processing."""
        try:
            queue_item = QueueItem(
                priority=command.priority,
                item_type="command",
                payload={
                    "id": str(command.id),
                    "command_type": command.command_type.value,
                    "parameters": command.parameters,
                    "priority": command.priority.value,
                    "source": command.source,
                    "user_id": command.user_id,
                    "metadata": command.metadata,
                },
                max_retries=self.max_retries,
            )

            success = await self.database.save_queue_item(queue_item)
            if success:
                self.logger.info(f"Queued command: {command.command_type.value}")

            return success

        except Exception as e:
            self.logger.error(f"Failed to queue command: {e}")
            return False

    async def queue_sensor_data(self, data: SensorData) -> bool:
        """Queue sensor data for processing."""
        try:
            queue_item = QueueItem(
                priority=QueuePriority.NORMAL,
                item_type="data",
                payload={
                    "id": str(data.id),
                    "sensor_type": data.sensor_type.value,
                    "sensor_id": data.sensor_id,
                    "value": data.value,
                    "unit": data.unit,
                    "latitude": data.latitude,
                    "longitude": data.longitude,
                    "altitude": data.altitude,
                    "accuracy": data.accuracy,
                    "confidence": data.confidence,
                    "metadata": data.metadata,
                },
                max_retries=self.max_retries,
            )

            success = await self.database.save_queue_item(queue_item)
            return success

        except Exception as e:
            self.logger.error(f"Failed to queue sensor data: {e}")
            return False

    async def queue_photo(self, photo: PhotoMetadata) -> bool:
        """Queue photo metadata for processing."""
        try:
            queue_item = QueueItem(
                priority=QueuePriority.NORMAL,
                item_type="photo",
                payload={
                    "id": str(photo.id),
                    "filename": photo.filename,
                    "file_path": photo.file_path,
                    "file_size": photo.file_size,
                    "mime_type": photo.mime_type,
                    "width": photo.width,
                    "height": photo.height,
                    "resolution": photo.resolution,
                    "latitude": photo.latitude,
                    "longitude": photo.longitude,
                    "altitude": photo.altitude,
                    "heading": photo.heading,
                    "camera_id": photo.camera_id,
                    "exposure_time": photo.exposure_time,
                    "iso": photo.iso,
                    "aperture": photo.aperture,
                    "tags": photo.tags,
                    "description": photo.description,
                    "metadata": photo.metadata,
                },
                max_retries=self.max_retries,
            )

            success = await self.database.save_queue_item(queue_item)
            return success

        except Exception as e:
            self.logger.error(f"Failed to queue photo: {e}")
            return False

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status and statistics."""
        try:
            pending_items = await self.database.get_pending_queue_items(1000)

            status = {
                "running": self._running,
                "pending_count": len(pending_items),
                "statistics": self.stats.copy(),
                "item_types": {},
            }

            # Count by item type
            for item in pending_items:
                item_type = item.item_type
                if item_type not in status["item_types"]:
                    status["item_types"][item_type] = 0
                status["item_types"][item_type] += 1

            return status

        except Exception as e:
            self.logger.error(f"Failed to get queue status: {e}")
            return {"error": str(e)}

    async def clear_queue(self, item_type: Optional[str] = None) -> int:
        """Clear queue items, optionally by type."""
        try:
            # This would require additional database methods
            # For now, we'll return a placeholder
            self.logger.info(f"Clear queue requested for type: {item_type}")
            return 0

        except Exception as e:
            self.logger.error(f"Failed to clear queue: {e}")
            return 0
