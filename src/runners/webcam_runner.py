"""
Webcam Runner Module for SOLAR Robot

This module provides a threaded runner for the WebcamSensor.
It periodically captures images and saves them to disk.
"""

from typing import Any, Dict, Optional

from sensors.webcam_sensor import (
    ImageReading,
    SensorCaptureError,
    SensorConfigError,
    WebcamSensor,
)

from .base_runner import BaseRunner, RunnerState


class WebcamRunner(BaseRunner):
    """
    Threaded runner for Webcam image capturing.
    """

    def __init__(
        self, runner_id: str, config: Dict[str, Any], production: bool = False
    ):
        """
        Initialize the WebcamRunner.

        Args:
            runner_id: Unique identifier for this runner instance.
            config: Configuration dictionary for this runner instance.
            production: Whether running in production mode.
        """
        self.label = config.get("label", runner_id)

        # Specific config for WebcamSensor
        # The runner's config section itself is passed to WebcamSensor
        self.webcam_config = config

        super().__init__(runner_id, config, production)

        self.sensor: Optional[WebcamSensor] = None
        self._last_capture_details: Optional[ImageReading] = None

    def _initialize(self) -> bool:
        """Initialize the WebcamSensor."""
        try:
            # Pass the runner's specific config section to the sensor
            self.sensor = WebcamSensor(self.webcam_config, self.production)
            self.logger.info(
                f"{self.label} initialized successfully. Capturing images every {self.interval}s."
            )
            # Perform a test capture
            test_capture = self.sensor.capture_and_save_photo()
            self.logger.debug(
                f"{self.label} test capture successful: {test_capture.file_path}"
            )
            self._last_capture_details = test_capture
            return True
        except (SensorConfigError, SensorCaptureError) as e:
            self.logger.error(f"Failed to initialize {self.label}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error initializing {self.label}: {e}")
            return False

    def _work_cycle(self) -> None:
        """Perform one image capture cycle."""
        if not self.sensor:
            raise RuntimeError(f"{self.label} not initialized.")

        try:
            capture_details = self.sensor.capture_and_save_photo()
            self._last_capture_details = capture_details
            self.logger.debug(
                f"{self.label} captured photo: {capture_details.file_path}"
            )
        except (SensorCaptureError, SensorConfigError) as e:
            self.logger.error(f"Error in {self.label} work cycle: {e}")
            # Decide if this should re-raise to stop the runner or just log
            # For now, re-raise to allow BaseRunner to handle error counting/stopping
            raise

    def _cleanup(self) -> None:
        """Cleanup WebcamSensor resources."""
        if self.sensor:
            self.sensor.release()
            self.logger.info(f"{self.label} sensor released.")
        self.sensor = None

    def is_healthy(self) -> bool:
        """Check if the WebcamRunner is healthy."""
        # Check basic runner state
        if not self.is_running or self.state != RunnerState.RUNNING:
            return False

        # Check error count
        if self._error_count >= self._get_config_value("max_errors", 3):
            return False

        # Check sensor
        if not self.sensor:
            return False

        sensor_healthy = self.sensor.is_healthy()
        if not sensor_healthy:
            self.logger.warning(f"{self.label} sensor reported as unhealthy.")
        return sensor_healthy
        """
        Get enhanced status information including last capture details.
        """
        base_status = self.get_status()
        sensor_status = self.sensor.get_status() if self.sensor else None

        enhanced = {
            "base_status": base_status,
            "label": self.label,
            "sensor_status": sensor_status,
            "output_directory": self.webcam_config.get(
                "output_directory", "data/photos"
            ),
            "capture_interval": self.interval,
        }

        if self._last_capture_details:
            enhanced["last_capture"] = {
                "file_path": self._last_capture_details.file_path,
                "timestamp": self._last_capture_details.timestamp,
                "image_shape": (
                    self._last_capture_details.image.shape
                    if self._last_capture_details.image is not None
                    else None
                ),
            }
        else:
            enhanced["last_capture"] = None

        return enhanced

    def _handle_error(self, error: Exception) -> bool:
        """
        Handle errors specific to Webcam operations.
        """
        if isinstance(error, (SensorCaptureError, SensorConfigError)):
            self.logger.warning(
                f"Webcam specific error in {self.label} (continuing): {error}"
            )
            return True  # Continue running for these types of errors

        # For other errors, use default handling from BaseRunner
        return super()._handle_error(error)
