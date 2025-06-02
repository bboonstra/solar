"""
Runner Manager Module for SOLAR Robot

This module provides central management for all threaded runners.
It handles startup, shutdown, monitoring, and status reporting for all runners.
"""

import logging
import signal
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from .base_runner import BaseRunner, RunnerStatus
from .ina219_runner import INA219Runner
from .pipower_runner import PiPowerRunner


@dataclass
class SystemStatus:
    """Overall system status for all runners."""

    total_runners: int
    running_runners: int
    stopped_runners: int
    error_runners: int
    healthy_runners: int
    uptime: float
    last_status_check: float


class RunnerManager:
    """
    Central manager for all threaded runners.

    Provides:
    - Dynamic runner registration based on configuration
    - Runner lifecycle management
    - Graceful startup and shutdown
    - Health monitoring
    - Status reporting
    - Signal handling
    """

    def __init__(self, config: Dict[str, Any], production: bool = False):
        """
        Initialize the runner manager.

        Args:
            config: Configuration dictionary
            production: Whether running in production mode
        """
        self.config = config
        self.production = production
        self.logger = logging.getLogger(__name__)

        # Runner registry
        self._runners: Dict[str, BaseRunner] = {}

        # Runner type registry - maps runner types to their classes
        self._runner_classes: Dict[str, Type[BaseRunner]] = {
            "ina219": INA219Runner,
            "pipower": PiPowerRunner,
            # Add more runner classes here as they are developed
        }

        # Manager state
        self._running = False
        self._shutdown_requested = False
        self._start_time: Optional[float] = None

        # Configuration
        app_config = config.get("application", {})
        self.threaded_runners_enabled = app_config.get("threaded_runners", True)
        self.main_loop_interval = app_config.get("main_loop_interval", 0.1)
        self.shutdown_timeout = app_config.get("shutdown_timeout", 5.0)

        # Setup signal handling
        self._setup_signal_handlers()

        self.logger.info("Runner manager initialized")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def register_runner(self, runner_id: str, runner_config: Dict[str, Any]) -> bool:
        """
        Register and initialize a runner from configuration.

        Args:
            runner_id: Unique identifier for this runner instance
            runner_config: Configuration dictionary for this runner

        Returns:
            True if registered successfully, False otherwise
        """
        success = False

        # Early validation checks
        if not self.threaded_runners_enabled:
            self.logger.info(f"Threaded runners disabled, skipping {runner_id}")
        elif runner_id in self._runners:
            self.logger.warning(f"Runner '{runner_id}' already registered")
        else:
            # Get runner type from config
            runner_type = runner_config.get("type")
            if not runner_type:
                self.logger.error(f"Runner type not specified for '{runner_id}'")
            elif runner_type not in self._runner_classes:
                self.logger.error(
                    f"Unknown runner type '{runner_type}' for '{runner_id}'"
                )
            else:
                try:
                    runner_class = self._runner_classes[runner_type]
                    runner = runner_class(runner_id, runner_config, self.production)

                    if not runner.enabled:
                        self.logger.warning(
                            f"Runner '{runner_id}' is disabled in configuration"
                        )
                    else:
                        self._runners[runner_id] = runner
                        self.logger.debug(
                            f"Registered runner: {runner_id} ({runner_type})"
                        )
                        success = True

                except Exception as e:
                    self.logger.error(f"Failed to register runner '{runner_id}': {e}")

        return success

    def _auto_register_runners(self) -> None:
        """Automatically register runners based on configuration."""
        runners_config = self.config.get("runners", {})

        for runner_id, runner_config in runners_config.items():
            if not isinstance(runner_config, dict):
                self.logger.warning(f"Invalid configuration for runner '{runner_id}'")
                continue

            self.register_runner(runner_id, runner_config)

    def start_all_runners(self) -> bool:
        """
        Start all registered runners.

        Returns:
            True if all enabled runners started successfully, False otherwise
        """
        if not self._runners:
            self.logger.warning("No runners registered")
            return True

        self.logger.debug(f"Starting {len(self._runners)} registered runners...")

        success_count = 0
        for name, runner in self._runners.items():
            if runner.start():
                success_count += 1
                self.logger.info(f"Started runner: {name}")
            else:
                self.logger.error(f"Failed to start runner: {name}")

        success = success_count == len(self._runners)

        if success:
            self.logger.info(f"All {success_count} runners started successfully")
        else:
            self.logger.warning(
                f"Only {success_count}/{len(self._runners)} runners started"
            )

        return success

    def stop_all_runners(self) -> bool:
        """
        Stop all runners gracefully.

        Returns:
            True if all runners stopped successfully, False otherwise
        """
        if not self._runners:
            return True

        self.logger.debug(f"Stopping {len(self._runners)} runners...")

        success_count = 0
        for name, runner in self._runners.items():
            if runner.stop(self.shutdown_timeout):
                success_count += 1
                self.logger.debug(f"Stopped runner: {name}")
            else:
                self.logger.warning(f"Runner '{name}' did not stop gracefully")

        success = success_count == len(self._runners)

        if success:
            self.logger.info(f"All {success_count} runners stopped successfully")
        else:
            self.logger.warning(
                f"Only {success_count}/{len(self._runners)} runners stopped gracefully"
            )

        return success

    def start(self) -> bool:
        """
        Start the runner manager and all registered runners.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            self.logger.warning("Runner manager is already running")
            return False

        self.logger.info("Starting runner manager...")

        # Auto-register known runners based on configuration
        self._auto_register_runners()

        # Start all runners
        if not self.start_all_runners():
            self.logger.error("Failed to start all runners")
            return False

        self._running = True
        self._start_time = time.time()
        self.logger.info("Runner manager started successfully")
        return True

    def shutdown(self) -> None:
        """Initiate graceful shutdown of the runner manager."""
        if self._shutdown_requested:
            return

        self._shutdown_requested = True
        self.logger.info("Shutting down runner manager...")

        # Stop all runners
        self.stop_all_runners()

        self._running = False
        self.logger.info("Runner manager shutdown complete")

    def run(self) -> None:
        """
        Run the main manager loop.

        This method blocks until shutdown is requested.
        """
        if not self.start():
            self.logger.error("Failed to start runner manager")
            return

        try:
            self.logger.info("Runner manager main loop started")

            while self._running and not self._shutdown_requested:
                # Perform periodic health checks and maintenance
                self._health_check_cycle()

                # Sleep until next cycle
                time.sleep(self.main_loop_interval)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Error in runner manager main loop: {e}")
        finally:
            if not self._shutdown_requested:
                self.shutdown()

    def _health_check_cycle(self) -> None:
        """Perform periodic health checks on all runners."""
        unhealthy_runners = []

        for name, runner in self._runners.items():
            if runner.is_running and not runner.is_healthy():
                unhealthy_runners.append(name)

        if unhealthy_runners:
            self.logger.warning(f"Unhealthy runners detected: {unhealthy_runners}")

    def get_runner(self, name: str) -> Optional[BaseRunner]:
        """
        Get a specific runner by name.

        Args:
            name: Name of the runner

        Returns:
            Runner instance or None if not found
        """
        return self._runners.get(name)

    def get_all_runners(self) -> Dict[str, BaseRunner]:
        """Get all registered runners."""
        return self._runners.copy()

    def get_runner_status(self, name: str) -> Optional[RunnerStatus]:
        """
        Get status for a specific runner.

        Args:
            name: Name of the runner

        Returns:
            RunnerStatus or None if runner not found
        """
        runner = self._runners.get(name)
        return runner.get_status() if runner else None

    def get_all_runner_statuses(self) -> Dict[str, RunnerStatus]:
        """Get status for all runners."""
        statuses = {}
        for name, runner in self._runners.items():
            statuses[name] = runner.get_status()
        return statuses

    def get_system_status(self) -> SystemStatus:
        """Get overall system status."""
        statuses = self.get_all_runner_statuses()

        total_runners = len(statuses)
        running_runners = sum(
            1 for s in statuses.values() if s.state.value == "running"
        )
        stopped_runners = sum(
            1 for s in statuses.values() if s.state.value == "stopped"
        )
        error_runners = sum(1 for s in statuses.values() if s.state.value == "error")
        healthy_runners = sum(1 for s in statuses.values() if s.healthy)

        uptime = 0.0
        if self._start_time:
            uptime = time.time() - self._start_time

        return SystemStatus(
            total_runners=total_runners,
            running_runners=running_runners,
            stopped_runners=stopped_runners,
            error_runners=error_runners,
            healthy_runners=healthy_runners,
            uptime=uptime,
            last_status_check=time.time(),
        )

    def print_status_report(self) -> None:
        """Print a comprehensive status report."""
        system_status = self.get_system_status()
        runner_statuses = self.get_all_runner_statuses()

        print("\n" + "=" * 60)
        print("SOLAR Robot Runner Manager Status Report")
        print("=" * 60)

        print(f"System Uptime: {system_status.uptime:.1f}s")
        print(f"Total Runners: {system_status.total_runners}")
        print(
            f"Running: {system_status.running_runners}, "
            f"Stopped: {system_status.stopped_runners}, "
            f"Error: {system_status.error_runners}"
        )
        print(f"Healthy: {system_status.healthy_runners}/{system_status.total_runners}")

        print("\nRunner Details:")
        print("-" * 60)

        for name, status in runner_statuses.items():
            health_indicator = "✓" if status.healthy else "⚠"
            state_indicator = "●" if status.state.value == "running" else "○"

            print(
                f"{state_indicator} {health_indicator} {name:<15} "
                f"State: {status.state.value:<8} "
                f"Uptime: {status.uptime:.1f}s "
                f"Errors: {status.error_count}"
            )

            if status.last_error:
                print(f"    Last Error: {status.last_error}")

        print("=" * 60)

    @property
    def is_running(self) -> bool:
        """Check if the runner manager is running."""
        return self._running

    @property
    def is_healthy(self) -> bool:
        """Check if all runners are healthy."""
        return all(
            runner.is_healthy()
            for runner in self._runners.values()
            if runner.is_running
        )
