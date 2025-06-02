"""
Base Runner Module for SOLAR Robot

This module provides the abstract base class for all threaded runners.
All sensor and system runners should inherit from BaseRunner.
"""

import abc
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class RunnerState(Enum):
    """Enum for runner states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RunnerStatus:
    """Status information for a runner."""

    name: str
    state: RunnerState
    enabled: bool
    healthy: bool
    error_count: int
    last_error: Optional[str]
    uptime: float
    last_activity: Optional[float]


class BaseRunner(abc.ABC):
    """
    Abstract base class for all threaded runners.

    Provides common functionality for:
    - Thread management
    - State tracking
    - Error handling
    - Health monitoring
    - Graceful shutdown
    """

    def __init__(self, name: str, config: Dict[str, Any], production: bool = False):
        """
        Initialize the base runner.

        Args:
            name: Unique name for this runner
            config: Configuration dictionary
            production: Whether running in production mode
        """
        self.name = name
        self.config = config
        self.production = production
        self.logger = logging.getLogger(f"{__name__}.{name}")

        # Threading
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()

        # State tracking
        self._state = RunnerState.STOPPED
        self._enabled = self._get_config_value("enabled", True)
        self._error_count = 0
        self._last_error: Optional[str] = None
        self._start_time: Optional[float] = None
        self._last_activity: Optional[float] = None

        # Configuration
        self.interval = self._get_config_value("measurement_interval", 1.0)
        # NEW: Behavior and trigger configuration for runners
        self.run_behavior = self._get_config_value(
            "run_behavior", "continuous"
        )  # continuous, scheduled, triggered
        self.trigger_condition = self._get_config_value(
            "trigger_condition", None
        )  # e.g., {"blackboard_key": "value"}
        self.schedule_time = self._get_config_value(
            "schedule_time", None
        )  # e.g., "HH:MM" for daily schedule

        self.logger.debug(
            f"Runner '{name}' initialized - Enabled: {self._enabled}, Behavior: {self.run_behavior}"
        )

    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get a configuration value with a default fallback."""
        return self.config.get(key, default)

    @property
    def state(self) -> RunnerState:
        """Get the current runner state."""
        with self._state_lock:
            return self._state

    @property
    def enabled(self) -> bool:
        """Check if the runner is enabled."""
        return self._enabled

    @property
    def is_running(self) -> bool:
        """Check if the runner is currently running."""
        return self.state == RunnerState.RUNNING

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the runner."""
        self._enabled = enabled
        self.logger.debug(
            f"Runner '{self.name}' {'enabled' if enabled else 'disabled'}"
        )

    def start(self) -> bool:
        """
        Start the runner thread.

        Returns:
            True if started successfully, False otherwise
        """
        if not self._enabled:
            self.logger.warning(f"Runner '{self.name}' is disabled, not starting")
            return False

        with self._state_lock:
            if self._state != RunnerState.STOPPED:
                self.logger.warning(
                    f"Runner '{self.name}' is not stopped, cannot start"
                )
                return False

            self._state = RunnerState.STARTING

        try:
            # Initialize the runner-specific components
            if not self._initialize():
                with self._state_lock:
                    self._state = RunnerState.ERROR
                self.logger.error(f"Failed to initialize runner '{self.name}'")
                return False

            # Start the thread
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name=f"{self.name}_runner"
            )
            self._thread.daemon = True
            self._start_time = time.time()
            self._thread.start()

            with self._state_lock:
                self._state = RunnerState.RUNNING

            self.logger.debug(f"Runner '{self.name}' started successfully")
            return True

        except Exception as e:
            with self._state_lock:
                self._state = RunnerState.ERROR
            self._record_error(f"Failed to start runner: {e}")
            return False

    def stop(self, timeout: float = 5.0) -> bool:
        """
        Stop the runner thread gracefully.

        Args:
            timeout: Maximum time to wait for graceful shutdown

        Returns:
            True if stopped successfully, False if forced
        """
        with self._state_lock:
            if self._state in [RunnerState.STOPPED, RunnerState.STOPPING]:
                return True
            self._state = RunnerState.STOPPING

        self.logger.debug(f"Stopping runner '{self.name}'...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
            if self._thread.is_alive():
                self.logger.warning(f"Runner '{self.name}' did not stop gracefully")
                with self._state_lock:
                    self._state = RunnerState.ERROR
                return False

        # Note: cleanup is now called in the worker thread, not here

        with self._state_lock:
            self._state = RunnerState.STOPPED

        self.logger.debug(f"Runner '{self.name}' stopped")
        return True

    def get_status(self) -> RunnerStatus:
        """Get comprehensive status information."""
        uptime = 0.0
        if self._start_time:
            uptime = time.time() - self._start_time

        # Ensure last_activity is serializable (float or None)
        last_activity_ts = self._last_activity
        if isinstance(last_activity_ts, time.struct_time):
            last_activity_ts = time.mktime(
                last_activity_ts
            )  # Convert to float if it's struct_time

        return RunnerStatus(
            name=self.name,
            state=self.state,
            enabled=self._enabled,
            healthy=self.is_healthy(),
            error_count=self._error_count,
            last_error=self._last_error,
            uptime=uptime,
            last_activity=last_activity_ts,  # Use converted timestamp
        )

    def _run(self) -> None:
        """Main thread loop - runs the actual worker logic."""
        self.logger.debug(f"Runner '{self.name}' thread started")

        try:
            while not self._stop_event.is_set():
                # NEW: Check if runner should execute based on its behavior type
                if not self._should_execute_now():
                    if self._stop_event.wait(
                        self.interval
                    ):  # Still respect interval for checking stop event
                        break
                    continue  # Skip work cycle if conditions not met

                try:
                    # Update activity timestamp
                    self._last_activity = time.time()

                    # Run the main work cycle
                    self._work_cycle()

                    # Wait for next cycle or stop signal
                    if self._stop_event.wait(self.interval):
                        break  # Stop requested

                except Exception as e:
                    self._record_error(f"Error in work cycle: {e}")
                    # Continue running unless it's a critical error
                    if not self._handle_error(e):
                        break

        except Exception as e:
            self._record_error(f"Fatal error in runner thread: {e}")
        finally:
            self.logger.debug(f"Runner '{self.name}' thread ending")
            # Call cleanup in the worker thread before exiting
            try:
                self._cleanup()
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    def _record_error(self, error_msg: str) -> None:
        """Record an error for status tracking."""
        self._error_count += 1
        self._last_error = error_msg
        self.logger.error(f"Runner '{self.name}': {error_msg}")

    @abc.abstractmethod
    def _initialize(self) -> bool:
        """
        Initialize runner-specific components.

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abc.abstractmethod
    def _work_cycle(self) -> None:
        """
        Perform one cycle of work.

        This method is called repeatedly in the runner thread.
        """
        pass

    @abc.abstractmethod
    def is_healthy(self) -> bool:
        """
        Check if the runner is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    def _cleanup(self) -> None:
        """
        Cleanup runner-specific resources.

        Override this method to add custom cleanup logic.
        """
        pass

    def _handle_error(self, error: Exception) -> bool:
        """
        Handle errors during work cycle.

        Args:
            error: The exception that occurred

        Returns:
            True to continue running, False to stop runner
        """
        # Default behavior: log and continue for most errors
        # Override this method for custom error handling
        return True

    # NEW: Methods to control execution based on run_behavior
    def _should_execute_now(self, blackboard: Optional[Dict[str, Any]] = None) -> bool:
        """Determines if the runner should execute its work_cycle based on its run_behavior."""
        if not self._enabled:
            return False

        current_time_str = time.strftime("%H:%M")

        if self.run_behavior == "continuous":
            return True
        elif self.run_behavior == "scheduled":
            if self.schedule_time and current_time_str == self.schedule_time:
                # Basic check, could be made more robust (e.g., run once per scheduled time)
                return True
            return False
        elif self.run_behavior == "triggered":
            if self.trigger_condition and blackboard:
                for key, expected_value in self.trigger_condition.items():
                    if blackboard.get(key) != expected_value:
                        return False  # Condition not met
                return True  # All conditions met
            return False  # No trigger condition or blackboard

        # Default to not running if behavior is unknown or not properly configured
        return False
