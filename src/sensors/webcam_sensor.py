"""
Webcam Sensor Module for SOLAR Robot

This module provides an interface for webcams, specifically tested with
Logitech HD C270, to capture images.
"""

import abc
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import cv2  # OpenCV for camera access
import numpy as np  # For creating simulated images

from config.paths import ROOT_DIR


# Custom Exception for sensor reading errors
class SensorConfigError(ValueError):
    """Custom exception for errors in sensor configuration."""

    pass


class SensorCaptureError(IOError):
    """Custom exception for errors encountered during image capture."""

    pass


@dataclass
class ImageReading:
    """Data class for captured image results."""

    image: Any  # Typically a NumPy array (cv2 image)
    timestamp: float  # Unix timestamp
    file_path: Optional[str] = None  # Path where image was saved


class WebcamAdapter(abc.ABC):
    """Abstract base class for webcam adapters."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialize the webcam hardware or simulation."""
        pass

    @abc.abstractmethod
    def capture_image(self) -> np.ndarray:
        """Capture an image from the webcam."""
        pass

    @abc.abstractmethod
    def release(self) -> None:
        """Release the webcam hardware."""
        pass

    @abc.abstractmethod
    def is_healthy(self) -> bool:
        """Check if the adapter and camera are operational."""
        pass


class HardwareWebcamAdapter(WebcamAdapter):
    """Adapter for a physical webcam using OpenCV."""

    def __init__(
        self, camera_id: int = 0, resolution: Optional[Tuple[int, int]] = None
    ):
        self.camera_id = camera_id
        self.resolution = resolution  # e.g., (1280, 720)
        self.cap: Optional[cv2.VideoCapture] = None
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    def initialize(self) -> None:
        try:
            self.logger.info(f"Initializing hardware webcam (ID: {self.camera_id})...")
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_AVFOUNDATION)
            if not self.cap.isOpened():
                self.cap = None  # Ensure cap is None if not opened
                raise SensorCaptureError(
                    f"Cannot open webcam (ID: {self.camera_id}). Check if it is connected and not in use."
                )

            if self.resolution:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.logger.info(
                    f"Set webcam resolution to {self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}"
                )

            # Try to grab a frame to confirm it's working
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.release()  # Release if initial frame grab fails
                raise SensorCaptureError(
                    f"Failed to grab initial frame from webcam (ID: {self.camera_id})."
                )

            self.logger.info(
                f"Hardware webcam (ID: {self.camera_id}) initialized successfully."
            )
            self._initialized = True
        except Exception as e:
            self.release()  # Ensure cleanup on any initialization error
            self.logger.error(
                f"Failed to initialize webcam (ID: {self.camera_id}): {e}"
            )
            raise SensorConfigError(
                f"Failed to initialize webcam (ID: {self.camera_id}): {e}"
            ) from e

    def capture_image(self) -> np.ndarray:
        if not self.cap or not self._initialized:
            raise SensorCaptureError("Webcam not initialized or already released.")
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise SensorCaptureError(
                    "Failed to capture image from webcam. No frame received."
                )
            return frame
        except Exception as e:
            self.logger.error(f"Error capturing image from webcam: {e}")
            raise SensorCaptureError(f"Error capturing image from webcam: {e}") from e

    def release(self) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.logger.info(f"Hardware webcam (ID: {self.camera_id}) released.")
        self.cap = None
        self._initialized = False

    def is_healthy(self) -> bool:
        if not self.cap or not self.cap.isOpened() or not self._initialized:
            return False
        # Try a quick frame grab
        try:
            ret, _ = self.cap.read()
            if not ret:  # if read fails, try to re-initialize
                self.logger.warning(
                    f"Webcam {self.camera_id} failed health check (read failed). Attempting re-init."
                )
                self.release()
                self.initialize()  # try to recover
                return self.cap is not None and self.cap.isOpened()
            return True
        except Exception:
            return False


class SimulatedWebcamAdapter(WebcamAdapter):
    """Adapter for a simulated webcam."""

    def __init__(self, resolution: Tuple[int, int] = (640, 480)):
        self.logger = logging.getLogger(__name__)
        self.resolution = resolution
        self._initialized = False

    def initialize(self) -> None:
        self.logger.info("Simulated webcam initialized.")
        self._initialized = True
        # No actual hardware to initialize

    def capture_image(self) -> np.ndarray:
        if not self._initialized:
            raise SensorCaptureError("Simulated webcam not initialized.")
        self.logger.debug("Simulating image capture.")
        # Create a dummy image
        img = np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
        # Add some text to identify it as a simulation
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
        cv2.putText(
            img,
            f"Simulated Image {timestamp_str}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        return img

    def release(self) -> None:
        self.logger.info("Simulated webcam released.")
        self._initialized = False

    def is_healthy(self) -> bool:
        return self._initialized


class WebcamSensor:
    """
    Webcam Sensor for capturing images.
    Supports both production (real hardware) and development (simulated) modes.
    """

    def __init__(self, config: Dict[str, Any], production: bool = False):
        self.config = config  # This will be the specific webcam config block
        self.production = production
        self.logger = logging.getLogger(__name__)

        # Configuration parameters
        self.camera_id = self.config.get("camera_id", 0)
        resolution_cfg = self.config.get("resolution")
        self.resolution: Optional[Tuple[int, int]] = None
        if isinstance(resolution_cfg, list) and len(resolution_cfg) == 2:
            self.resolution = (int(resolution_cfg[0]), int(resolution_cfg[1]))
        elif resolution_cfg is not None:
            self.logger.warning(
                f"Invalid resolution format: {resolution_cfg}. Expected [width, height]. Using default."
            )

        self.logger.debug(f"Using ROOT_DIR: {ROOT_DIR}")

        # Construct output directory path relative to ROOT_DIR
        output_dir = self.config.get("output_directory", "data/photos").lstrip("/")
        self.output_directory = os.path.join(ROOT_DIR, output_dir)
        self.logger.debug(f"Output directory: {self.output_directory}")
        self.file_format = self.config.get("file_format", "jpg")

        # Initialize sensor adapter
        self.adapter: WebcamAdapter
        self._last_capture: Optional[ImageReading] = None
        self._init_adapter()

        self.logger.debug(
            f"WebcamSensor initialized - Camera ID: {self.camera_id}, "
            f"Mode: {'Production' if production else 'Development'}, "
            f"Output: {self.output_directory}"
        )

    def _init_adapter(self) -> None:
        """Initialize the appropriate sensor adapter based on environment.
        In development mode, it attempts to use the hardware adapter first and falls back to simulation.
        """
        try:
            if self.production:
                self.logger.info(
                    "Production mode: Initializing hardware webcam adapter."
                )
                self.adapter = HardwareWebcamAdapter(self.camera_id, self.resolution)
                self.adapter.initialize()
                self.logger.info(
                    "Hardware webcam adapter initialized successfully in production mode."
                )
            else:  # Development mode
                self.logger.info(
                    "Development mode: Attempting to initialize hardware webcam adapter..."
                )
                try:
                    hw_adapter = HardwareWebcamAdapter(self.camera_id, self.resolution)
                    hw_adapter.initialize()
                    self.adapter = hw_adapter
                    self.logger.info(
                        "Hardware webcam adapter initialized successfully in development mode."
                    )
                except (SensorConfigError, SensorCaptureError) as hw_init_error:
                    self.logger.warning(
                        f"Development mode: Failed to initialize hardware webcam ({hw_init_error}). "
                        f"Falling back to simulated webcam adapter."
                    )
                    self.adapter = SimulatedWebcamAdapter(self.resolution or (640, 480))
                    self.adapter.initialize()
                    self.logger.info(
                        "Simulated webcam adapter initialized in development mode after hardware attempt failed."
                    )
                except (
                    Exception
                ) as e_hw:  # Catch any other unexpected error from hardware attempt
                    self.logger.error(
                        f"Development mode: Unexpected error initializing hardware webcam ({e_hw}). "
                        f"Falling back to simulated webcam adapter."
                    )
                    self.adapter = SimulatedWebcamAdapter(self.resolution or (640, 480))
                    self.adapter.initialize()
                    self.logger.info(
                        "Simulated webcam adapter initialized in development mode after hardware attempt failed due to unexpected error."
                    )

        except (
            SensorConfigError,
            SensorCaptureError,
        ) as e:  # Catches errors from the chosen adapter's initialize()
            self.logger.error(f"Failed to initialize chosen webcam adapter: {e}")
            # This could be an error from HardwareINA219Adapter in production,
            # or from SimulatedINA219Adapter if the fallback itself fails.
            raise
        except (
            Exception
        ) as e_main:  # Catch any other unexpected error during the process
            self.logger.error(
                f"An unexpected error occurred during webcam adapter selection/initialization: {e_main}"
            )
            raise SensorConfigError(
                f"Unexpected error during adapter setup: {e_main}"
            ) from e_main

    def capture_and_save_photo(self) -> ImageReading:
        """
        Capture a photo and save it to the configured directory.

        Returns:
            ImageReading object with image data and file path.
        Raises:
            SensorCaptureError if capturing or saving fails.
            SensorConfigError if output directory cannot be handled.
        """
        try:
            image_data = self.adapter.capture_image()
            timestamp = time.time()

            # Ensure output directory exists
            try:
                if not os.path.exists(self.output_directory):
                    os.makedirs(self.output_directory, exist_ok=True)
                    self.logger.info(
                        f"Created output directory: {self.output_directory}"
                    )
            except OSError as e:
                self.logger.error(
                    f"Failed to create output directory {self.output_directory}: {e}"
                )
                raise SensorConfigError(
                    f"Failed to create output directory {self.output_directory}: {e}"
                ) from e

            # Generate filename
            filename = f"webcam_{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(timestamp))}.{self.file_format}"
            file_path = os.path.join(self.output_directory, filename)

            # Save the image
            success = cv2.imwrite(file_path, image_data)
            if not success:
                raise SensorCaptureError(f"Failed to save image to {file_path}")

            self.logger.debug(f"Photo captured and saved to {file_path}")
            reading = ImageReading(
                image=image_data, timestamp=timestamp, file_path=file_path
            )
            self._last_capture = reading
            return reading

        except SensorCaptureError as e:
            self.logger.error(f"Failed to capture and save photo: {e}")
            raise
        except (
            Exception
        ) as e:  # Catch other unexpected errors like permission issues for cv2.imwrite
            self.logger.error(f"Unexpected error during photo capture/save: {e}")
            raise SensorCaptureError(
                f"Unexpected error during photo capture/save: {e}"
            ) from e

    def get_last_capture(self) -> Optional[ImageReading]:
        """Get the last captured image data."""
        return self._last_capture

    def is_healthy(self) -> bool:
        """Check if the webcam sensor is healthy."""
        if not hasattr(self, "adapter") or not self.adapter:
            return False
        return self.adapter.is_healthy()

    def release(self) -> None:
        """Release the webcam adapter."""
        if hasattr(self, "adapter") and self.adapter:
            self.adapter.release()
        self.logger.info("WebcamSensor resources released.")

    def get_status(self) -> Dict[str, Any]:
        """Get status information about the webcam sensor."""
        last_capture_info = None
        if self._last_capture:
            last_capture_info = {
                "timestamp": self._last_capture.timestamp,
                "file_path": self._last_capture.file_path,
                "image_shape": (
                    self._last_capture.image.shape
                    if self._last_capture.image is not None
                    else None
                ),
            }

        return {
            "sensor_type": "webcam_c270",  # Or a more generic "webcam"
            "camera_id": self.camera_id,
            "resolution": self.resolution,
            "output_directory": self.output_directory,
            "file_format": self.file_format,
            "mode": "production" if self.production else "development",
            "healthy": self.is_healthy(),
            "last_capture": last_capture_info,
        }
