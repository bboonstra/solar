"""
Audio Runner Module for SOLAR Robot

This module provides a threaded runner for audio notifications and TTS.
"""

import queue
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from devices.audio_device import AudioDevice

from .base_runner import BaseRunner


@dataclass
class AudioNotification:
    """Data class for audio notifications."""

    type: str  # "info", "warning", "error", "success", "tts"
    message: str  # Message for TTS or description
    priority: int = 0  # Higher numbers = higher priority


class AudioRunner(BaseRunner):
    """
    Threaded runner for audio notifications and TTS.

    Features:
    - Queued notifications with priority
    - Different notification sounds for different types
    - Optional TTS for critical messages
    - Configurable notification settings
    """

    def __init__(
        self, runner_id: str, config: Dict[str, Any], production: bool = False
    ):
        """
        Initialize the audio runner.

        Args:
            runner_id: Unique identifier for this runner instance
            config: Configuration dictionary for this runner instance
            production: Whether running in production mode
        """
        # Get runner-specific config
        self.label = config.get("label", runner_id)

        super().__init__(runner_id, config, production)

        # Audio-specific configuration
        self.enable_tts = self._get_config_value("enable_tts", False)
        self.notification_volume = self._get_config_value("notification_volume", 1.0)
        self.max_queue_size = self._get_config_value("max_queue_size", 100)

        # Initialize notification queue
        self._notification_queue: queue.PriorityQueue = queue.PriorityQueue(
            maxsize=self.max_queue_size
        )

        # Audio device instance
        self.audio_device: Optional[AudioDevice] = None

    def _initialize(self) -> bool:
        """Initialize the audio device."""
        try:
            # Create audio device with instance-specific config
            self.audio_device = AudioDevice(self.config, self.production)

            # Test the audio device
            if not self.audio_device.is_healthy():
                self.logger.error(f"Audio device health check failed for {self.label}")
                return False

            self.logger.debug(f"{self.label} initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize {self.label}: {e}")
            return False

    def _work_cycle(self) -> None:
        """Process the next notification in the queue."""
        if not self.audio_device:
            raise RuntimeError(f"{self.label} not initialized")

        try:
            # Non-blocking get with timeout
            try:
                # Queue items are tuples of (priority, timestamp, notification)
                _, _, notification = self._notification_queue.get(timeout=0.1)

                if notification.type == "tts" and self.enable_tts:
                    success = self.audio_device.speak_text(notification.message)
                else:
                    success = self.audio_device.play_notification(notification.type)

                if not success:
                    self.logger.warning(
                        f"Failed to play notification: {notification.type} - {notification.message}"
                    )

                self._notification_queue.task_done()

            except queue.Empty:
                # No notifications to process
                pass

        except Exception as e:
            self.logger.error(f"Error in audio runner work cycle: {e}")
            raise  # Re-raise so base class can handle it

    def queue_notification(
        self, notification_type: str, message: str = "", priority: int = 0
    ) -> bool:
        """
        Queue a notification to be played.

        Args:
            notification_type: Type of notification
            message: Optional message (for TTS)
            priority: Priority level (higher = more important)

        Returns:
            True if queued successfully, False if queue is full
        """
        try:
            notification = AudioNotification(
                type=notification_type, message=message, priority=priority
            )

            # Use negative priority for queue (so higher numbers have higher priority)
            # Add timestamp as secondary sort for FIFO within same priority
            queue_item = (-priority, time.time(), notification)

            self._notification_queue.put_nowait(queue_item)
            return True

        except queue.Full:
            self.logger.warning("Notification queue is full, dropping notification")
            return False

    def _cleanup(self) -> None:
        """Cleanup audio-specific resources."""
        if self.audio_device:
            self.logger.debug("Cleaning up audio device")
            self.audio_device.cleanup()
            self.audio_device = None

    def is_healthy(self) -> bool:
        """Check if the audio runner is healthy."""
        if not self.audio_device:
            return False

        return self.audio_device.is_healthy()

    def get_queue_size(self) -> int:
        """Get current size of notification queue."""
        return self._notification_queue.qsize()

    def clear_queue(self) -> None:
        """Clear all pending notifications."""
        while not self._notification_queue.empty():
            try:
                self._notification_queue.get_nowait()
                self._notification_queue.task_done()
            except queue.Empty:
                break
