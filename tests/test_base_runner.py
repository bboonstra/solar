"""
Unit Tests for BaseRunner

This module contains comprehensive unit tests for the BaseRunner abstract class
and its concrete implementations.
"""

import unittest
import time
from typing import Dict, Any

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from runners.base_runner import BaseRunner, RunnerState, RunnerStatus


class ConcreteRunner(BaseRunner):
    """Concrete implementation of BaseRunner for testing."""

    def __init__(self, name: str, config: Dict[str, Any], production: bool = False):
        super().__init__(name, config, production)
        self.initialize_called = False
        self.work_cycle_count = 0
        self.cleanup_called = False
        self.should_fail_init = False
        self.should_fail_work = False

    def _initialize(self) -> bool:
        self.initialize_called = True
        return not self.should_fail_init

    def _work_cycle(self) -> None:
        self.work_cycle_count += 1
        if self.should_fail_work:
            raise RuntimeError("Test work cycle error")

    def is_healthy(self) -> bool:
        return self.work_cycle_count > 0 and not self.should_fail_work

    def _cleanup(self) -> None:
        self.cleanup_called = True


class TestBaseRunner(unittest.TestCase):
    """Test cases for BaseRunner functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {"enabled": True, "measurement_interval": 0.1}
        self.runner = ConcreteRunner("test_runner", self.config)

    def tearDown(self):
        """Clean up after tests."""
        if self.runner.is_running:
            self.runner.stop()

    def test_initialization(self):
        """Test runner initialization."""
        self.assertEqual(self.runner.name, "test_runner")
        self.assertEqual(self.runner.state, RunnerState.STOPPED)
        self.assertTrue(self.runner.enabled)
        self.assertEqual(self.runner.interval, 0.1)
        self.assertFalse(self.runner.initialize_called)

    def test_enable_disable(self):
        """Test enabling and disabling the runner."""
        self.assertTrue(self.runner.enabled)

        self.runner.set_enabled(False)
        self.assertFalse(self.runner.enabled)

        self.runner.set_enabled(True)
        self.assertTrue(self.runner.enabled)

    def test_start_stop(self):
        """Test starting and stopping the runner."""
        # Start the runner
        self.assertTrue(self.runner.start())
        self.assertTrue(self.runner.initialize_called)
        self.assertEqual(self.runner.state, RunnerState.RUNNING)
        self.assertTrue(self.runner.is_running)

        # Wait for some work cycles
        time.sleep(0.3)
        self.assertGreater(self.runner.work_cycle_count, 0)

        # Stop the runner
        self.assertTrue(self.runner.stop())
        self.assertTrue(self.runner.cleanup_called)
        self.assertEqual(self.runner.state, RunnerState.STOPPED)
        self.assertFalse(self.runner.is_running)

    def test_start_when_disabled(self):
        """Test starting a disabled runner."""
        self.runner.set_enabled(False)
        self.assertFalse(self.runner.start())
        self.assertEqual(self.runner.state, RunnerState.STOPPED)

    def test_double_start(self):
        """Test starting an already running runner."""
        self.assertTrue(self.runner.start())
        self.assertFalse(self.runner.start())  # Should fail

    def test_initialization_failure(self):
        """Test handling of initialization failure."""
        self.runner.should_fail_init = True
        self.assertFalse(self.runner.start())
        self.assertEqual(self.runner.state, RunnerState.ERROR)

    def test_work_cycle_error_handling(self):
        """Test error handling in work cycle."""
        self.assertTrue(self.runner.start())
        time.sleep(0.2)  # Let it run normally

        # Introduce error
        self.runner.should_fail_work = True
        time.sleep(0.2)  # Let error occur

        # Runner should continue running (default error handling)
        self.assertTrue(self.runner.is_running)
        self.assertGreater(self.runner._error_count, 0)
        self.assertIsNotNone(self.runner._last_error)

    def test_get_status(self):
        """Test status reporting."""
        self.runner.start()
        time.sleep(0.2)

        status = self.runner.get_status()
        self.assertEqual(status.name, "test_runner")
        self.assertEqual(status.state, RunnerState.RUNNING)
        self.assertTrue(status.enabled)
        self.assertTrue(status.healthy)
        self.assertEqual(status.error_count, 0)
        self.assertIsNone(status.last_error)
        self.assertGreater(status.uptime, 0)
        self.assertIsNotNone(status.last_activity)

        self.runner.stop()

    def test_graceful_shutdown_timeout(self):
        """Test graceful shutdown with timeout."""

        # Create a runner that takes time to stop
        class SlowRunner(ConcreteRunner):
            def _cleanup(self):
                time.sleep(2)  # Simulate slow cleanup
                super()._cleanup()

        slow_runner = SlowRunner("slow", self.config)
        slow_runner.start()
        time.sleep(0.1)

        # Try to stop with short timeout
        start_time = time.time()
        result = slow_runner.stop(timeout=0.5)
        elapsed = time.time() - start_time

        # Should timeout and return False
        self.assertFalse(result)
        self.assertLess(elapsed, 1.0)  # Should not wait full 2 seconds
        self.assertEqual(slow_runner.state, RunnerState.ERROR)


class TestRunnerStateEnum(unittest.TestCase):
    """Test cases for RunnerState enum."""

    def test_state_values(self):
        """Test that all expected states exist."""
        self.assertEqual(RunnerState.STOPPED.value, "stopped")
        self.assertEqual(RunnerState.STARTING.value, "starting")
        self.assertEqual(RunnerState.RUNNING.value, "running")
        self.assertEqual(RunnerState.STOPPING.value, "stopping")
        self.assertEqual(RunnerState.ERROR.value, "error")


class TestRunnerStatus(unittest.TestCase):
    """Test cases for RunnerStatus dataclass."""

    def test_status_creation(self):
        """Test creating a RunnerStatus instance."""
        status = RunnerStatus(
            name="test",
            state=RunnerState.RUNNING,
            enabled=True,
            healthy=True,
            error_count=0,
            last_error=None,
            uptime=10.5,
            last_activity=time.time(),
        )

        self.assertEqual(status.name, "test")
        self.assertEqual(status.state, RunnerState.RUNNING)
        self.assertTrue(status.enabled)
        self.assertTrue(status.healthy)
        self.assertEqual(status.error_count, 0)
        self.assertIsNone(status.last_error)
        self.assertEqual(status.uptime, 10.5)
        self.assertIsNotNone(status.last_activity)


if __name__ == "__main__":
    unittest.main()
