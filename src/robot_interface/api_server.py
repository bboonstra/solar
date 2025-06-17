"""
FastAPI Server for Robot Interface

This module provides the REST API endpoints for robot interfacing.
Matches the structure of Next.js API routes with local database storage.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .database import RobotDatabase
from .models import (
    CommandStatus,
    CommandType,
    PhotoMetadata,
    RobotCommand,
    RobotState,
    RobotStatus,
    SensorData,
    SensorType,
)
from .queue_manager import QueueManager


# Simplified request models to match frontend
class RobotStatusUpdate(BaseModel):
    """Request model for robot status updates from the frontend."""

    last_docking: Optional[str] = None
    battery_level: Optional[float] = None
    operational_status: Optional[str] = "unknown"
    last_activity: Optional[str] = None


class SensorDataPacket(BaseModel):
    """Request model for a packet of sensor data from the frontend."""

    soil_moisture: float
    temperature: float
    humidity: float
    light_level: float
    battery_level: float
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None


class CommandRequest(BaseModel):
    """Request model for sending a command from the frontend."""

    command: str


class RobotAPIServer:
    """FastAPI server for robot interface."""

    def __init__(
        self,
        database: RobotDatabase,
        queue_manager: QueueManager,
        config: Dict[str, Any],
    ):
        """
        Initialize the API server.

        Args:
            database: Database instance for data persistence
            queue_manager: Queue manager for offline processing
            config: Configuration dictionary
        """
        self.database = database
        self.queue_manager = queue_manager
        self.config = config
        self.logger = logging.getLogger(__name__)

        # API configuration
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 8000)
        self.debug = config.get("debug", False)
        self.upload_dir = Path(config.get("upload_dir", "data/photos"))
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Create FastAPI app
        self.app = FastAPI(
            title="SOLAR Robot API",
            description="REST API for SOLAR robot interfacing",
            version="1.0.0",
            debug=self.debug,
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register routes
        self._register_routes()

        # Server state
        self._server = None
        self._running = False

    def _register_routes(self) -> None:
        """Register API routes."""

        @self.app.get("/api/robot-status", response_class=JSONResponse)
        async def get_robot_status():
            """Get latest robot status."""
            try:
                status_data = await self.database.get_latest_robot_status()

                if status_data:
                    response_data = {
                        "last_docking": (
                            status_data.last_activity.isoformat()
                            if status_data.last_activity
                            else None
                        ),
                        "battery_level": status_data.battery_level,
                        "operational_status": status_data.state.value,
                        "last_activity": status_data.activity_description
                        or "No activity recorded",
                    }
                else:
                    response_data = {
                        "last_docking": (
                            datetime.now() - timedelta(hours=8)
                        ).isoformat(),
                        "battery_level": 85.5,
                        "operational_status": "unknown",
                        "last_activity": "No status available",
                    }

                return JSONResponse(content={"success": True, "status": response_data})

            except Exception as e:
                self.logger.error(f"Error fetching robot status: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to fetch robot status"},
                )

        @self.app.post("/api/robot-status", response_class=JSONResponse)
        async def update_robot_status(status_update: RobotStatusUpdate):
            """Update robot status."""
            try:
                # Create a comprehensive internal status object from the simple request
                try:
                    state = RobotState(status_update.operational_status)
                except ValueError:
                    state = RobotState.IDLE

                status_data = RobotStatus(
                    state=state,
                    battery_level=status_update.battery_level or 0.0,
                    is_docked=status_update.last_docking is not None,
                    last_activity=(
                        datetime.fromisoformat(status_update.last_docking)
                        if status_update.last_docking
                        else datetime.utcnow()
                    ),
                    activity_description=status_update.last_activity,
                    last_heartbeat=datetime.utcnow(),
                )

                # Save to local database
                if not await self.database.save_robot_status(status_data):
                    raise HTTPException(
                        status_code=500, detail="Failed to save status locally"
                    )

                # Queue for potential cloud sync
                await self.queue_manager.queue_sensor_data(
                    SensorData(
                        sensor_type=SensorType.BATTERY,
                        sensor_id="status_update",
                        value=status_data.battery_level,
                        metadata={"status_update": True, **status_update.dict()},
                    )
                )

                response_data = {
                    "id": 1,  # Fixed ID to mimic Supabase upsert
                    "last_docking": status_update.last_docking,
                    "battery_level": status_update.battery_level,
                    "operational_status": status_update.operational_status,
                    "last_activity": status_update.last_activity,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                return JSONResponse(
                    content={
                        "success": True,
                        "message": "Status updated successfully",
                        "data": response_data,
                    }
                )

            except Exception as e:
                self.logger.error(f"Error updating robot status: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "success": False,
                        "error": "Failed to update robot status",
                    },
                )

        @self.app.get("/api/robot-data", response_class=JSONResponse)
        async def get_robot_data():
            """Get recent sensor data."""
            try:
                sensor_data = await self.database.get_recent_sensor_data(50)
                return JSONResponse(
                    content={"success": True, "data": [d.dict() for d in sensor_data]}
                )
            except Exception as e:
                self.logger.error(f"Error fetching robot data: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to fetch robot data"},
                )

        @self.app.post("/api/robot-data", response_class=JSONResponse)
        async def create_robot_data(data_packet: SensorDataPacket):
            """Create a new robot data record."""
            try:
                data_map = data_packet.dict()
                timestamp = datetime.utcnow()
                first_record = None

                for key, value in data_map.items():
                    if value is None or key in ["location_lat", "location_lng"]:
                        continue

                    try:
                        sensor_type = SensorType(key)
                        sensor_data = SensorData(
                            sensor_type=sensor_type,
                            sensor_id=f"{key}_sensor",
                            value=value,
                            latitude=data_packet.location_lat,
                            longitude=data_packet.location_lng,
                        )
                        if await self.database.save_sensor_data(sensor_data):
                            await self.queue_manager.queue_sensor_data(sensor_data)
                            if not first_record:
                                first_record = data_packet.dict()
                    except ValueError:
                        self.logger.warning(
                            f"Skipping unknown sensor type in data packet: {key}"
                        )

                if first_record:
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Data received successfully",
                            "data": first_record,
                            "timestamp": timestamp.isoformat(),
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=400, detail="No valid sensor data in packet"
                    )

            except Exception as e:
                self.logger.error(f"Error processing robot data: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to process robot data"},
                )

        @self.app.get("/api/robot-commands", response_class=JSONResponse)
        async def get_robot_commands():
            """Get recent robot commands."""
            try:
                commands = await self.database.get_recent_commands(10)
                # Mimic frontend structure
                response_data = [
                    {
                        "id": cmd.id,
                        "command": cmd.command_type.value,
                        "status": cmd.status.value,
                        "sent_at": cmd.timestamp.isoformat(),
                    }
                    for cmd in commands
                ]
                return JSONResponse(
                    content={"success": True, "commands": response_data}
                )
            except Exception as e:
                self.logger.error(f"Error fetching robot commands: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to fetch commands"},
                )

        @self.app.post("/api/robot-commands", response_class=JSONResponse)
        async def send_robot_command(req: CommandRequest):
            """Send a command to the robot."""
            try:
                # Validate command
                valid_commands = [item.value for item in CommandType]
                if req.command not in valid_commands:
                    raise HTTPException(status_code=400, detail="Invalid command")

                command = RobotCommand(
                    command_type=CommandType(req.command),
                    status=CommandStatus.PENDING,  # "sent" in frontend, maps to PENDING here
                    source="api",
                    queued_at=datetime.utcnow(),
                )

                if await self.database.save_robot_command(command):
                    await self.queue_manager.queue_command(command)
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": f'Command "{req.command}" sent successfully',
                            "command_id": str(command.id),
                            "timestamp": command.timestamp.isoformat(),
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=500, detail="Failed to save command"
                    )

            except HTTPException as he:
                raise he
            except Exception as e:
                self.logger.error(f"Error sending robot command: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to send command"},
                )

        @self.app.get("/api/robot-photos", response_class=JSONResponse)
        async def get_robot_photos():
            """Get recent robot photos."""
            try:
                photos = await self.database.get_recent_photos(20)
                # Mimic frontend structure
                response_data = [
                    {
                        "id": p.id,
                        "filename": p.filename,
                        "url": p.storage_url
                        or f"/local_photos/{p.filename}",  # Provide local path as fallback
                        "description": p.description,
                        "file_size": p.file_size,
                        "mime_type": p.mime_type,
                        "timestamp": p.timestamp.isoformat(),
                    }
                    for p in photos
                ]
                return JSONResponse(content={"success": True, "photos": response_data})
            except Exception as e:
                self.logger.error(f"Error fetching robot photos: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to fetch photos"},
                )

        @self.app.post("/api/robot-photos", response_class=JSONResponse)
        async def upload_robot_photo(
            photo: UploadFile = File(...), description: Optional[str] = Form(None)
        ):
            """Upload a photo to the robot."""
            try:
                if not photo.content_type or not photo.content_type.startswith(
                    "image/"
                ):
                    raise HTTPException(status_code=400, detail="File must be an image")

                file_ext = Path(photo.filename).suffix if photo.filename else ".jpg"
                filename = f"{int(datetime.utcnow().timestamp())}{file_ext}"
                file_path = self.upload_dir / filename

                # Save file locally
                async with aiofiles.open(file_path, "wb") as f:
                    content = await photo.read()
                    await f.write(content)

                # Create metadata
                photo_metadata = PhotoMetadata(
                    filename=filename,
                    file_path=str(file_path),
                    file_size=len(content),
                    mime_type=photo.content_type,
                    description=description,
                    storage_url=f"/local_photos/{filename}",  # Placeholder URL
                )

                if await self.database.save_photo_metadata(photo_metadata):
                    await self.queue_manager.queue_photo(photo_metadata)

                    response_data = {
                        "filename": photo_metadata.filename,
                        "url": photo_metadata.storage_url,
                        "description": photo_metadata.description,
                        "file_size": photo_metadata.file_size,
                        "mime_type": photo_metadata.mime_type,
                    }
                    return JSONResponse(
                        content={
                            "success": True,
                            "message": "Photo uploaded successfully",
                            "data": response_data,
                            "timestamp": photo_metadata.timestamp.isoformat(),
                        }
                    )
                else:
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=500, detail="Failed to save photo metadata"
                    )

            except HTTPException as he:
                raise he
            except Exception as e:
                self.logger.error(f"Error uploading photo: {e}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"success": False, "error": "Failed to upload photo"},
                )

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    async def start(self) -> bool:
        """Start the API server."""
        try:
            from uvicorn.config import Config
            from uvicorn.server import Server

            config = Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="debug" if self.debug else "info",
                access_log=True,
            )

            self._server = Server(config=config)
            self._running = True

            await self._server.serve()
            return True

        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")
            self._running = False
            return False

    async def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.should_exit = True
            self._running = False
            self.logger.info("API server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
