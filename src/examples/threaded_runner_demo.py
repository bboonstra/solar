#!/usr/bin/env python3
"""
Threaded Runner System Demonstration Script for SOLAR Robot

This script demonstrates how to use the new threaded runner system
to continuously monitor multiple sensors concurrently.

Usage:
    python src/examples/threaded_runner_demo.py
"""

import signal
import sys
import time
from pathlib import Path

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import load_config, load_environment_config, setup_logging
from runners import RunnerManager


class ThreadedRunnerDemo:
    """Demonstration class for the threaded runner system."""

    def __init__(self):
        """Initialize the threaded runner demo."""
        self.running = False
        self.runner_manager = None

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
        if self.runner_manager:
            self.runner_manager.shutdown()

    def initialize(self):
        """Initialize the threaded runner system."""
        try:
            # Load configuration and setup logging
            config = load_config()
            logger = setup_logging(config)

            # Determine environment
            production = load_environment_config(logger)

            # Initialize runner manager
            self.runner_manager = RunnerManager(config, production)

            logger.info("Threaded runner demo initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize threaded runner demo: {e}")
            return False

    def run_demo(self, duration_minutes: float = 5.0):
        """
        Run the demonstration for a specified duration.

        Args:
            duration_minutes: How long to run the demo (in minutes)
        """
        if not self.runner_manager:
            print("Runner manager not initialized!")
            return

        try:
            print(
                f"\n--- Starting Threaded Runner Demo ({duration_minutes} minutes) ---"
            )

            # Start the runner manager
            if not self.runner_manager.start():
                print("Failed to start runner manager")
                return

            print("✓ Runner manager started successfully")

            # Initial status report
            print("\nInitial System Status:")
            self.runner_manager.print_status_report()

            # Run for the specified duration
            end_time = time.time() + (duration_minutes * 60)
            status_interval = 15.0  # Status report every 15 seconds
            last_status = time.time()

            self.running = True

            while self.running and time.time() < end_time:
                # Periodic status reports
                if time.time() - last_status >= status_interval:
                    print(
                        f"\n--- Status Update (Running for {(time.time() - (end_time - duration_minutes * 60)):.1f}s) ---"
                    )
                    self.runner_manager.print_status_report()

                    # Show specific runner information
                    self._show_runner_details()

                    last_status = time.time()

                # Sleep briefly
                time.sleep(1.0)

            print("\n--- Demo Complete ---")

        except KeyboardInterrupt:
            print("\nDemo interrupted by user")
        except Exception as e:
            print(f"Error during demo: {e}")
        finally:
            if self.runner_manager:
                print("Shutting down runner manager...")
                self.runner_manager.shutdown()
                print("✓ Shutdown complete")

    def _show_runner_details(self):
        """Show detailed information for specific runners."""
        # Show INA219 runner details if available
        ina219_runner = self.runner_manager.get_runner("ina219")
        if ina219_runner and hasattr(ina219_runner, "get_enhanced_status"):
            status = ina219_runner.get_enhanced_status()

            print("\nINA219 Runner Details:")
            print("-" * 40)

            if status.get("last_reading"):
                reading = status["last_reading"]
                print(
                    f"  Latest Reading: {reading['voltage']:.2f}V, "
                    f"{reading['current']:.3f}A, {reading['power']:.2f}W"
                )

            if status.get("power_stats"):
                stats = status["power_stats"]
                print(
                    f"  Power Stats: Avg={stats['avg_power']:.2f}W, "
                    f"Min={stats['min_power']:.2f}W, Max={stats['max_power']:.2f}W"
                )
                print(f"  Sample Count: {stats['sample_count']}")

            if status.get("alert_counts"):
                alerts = status["alert_counts"]
                if (
                    alerts["consecutive_low_power"] > 0
                    or alerts["consecutive_high_power"] > 0
                ):
                    print(
                        f"  Active Alerts: Low Power={alerts['consecutive_low_power']}, "
                        f"High Power={alerts['consecutive_high_power']}"
                    )

    def interactive_mode(self):
        """Run in interactive mode with user commands."""
        if not self.runner_manager:
            print("Runner manager not initialized!")
            return

        print("\n--- Interactive Threaded Runner Demo ---")
        print("Commands:")
        print("  start   - Start all runners")
        print("  stop    - Stop all runners")
        print("  status  - Show system status")
        print("  runners - List all runners")
        print("  power   - Show power statistics (if available)")
        print("  quit    - Exit interactive mode")
        print()

        try:
            while True:
                try:
                    command = input("Runner Demo> ").strip().lower()

                    if command == "quit" or command == "q":
                        break
                    elif command == "start":
                        if self.runner_manager.start():
                            print("✓ Runners started successfully")
                        else:
                            print("✗ Failed to start runners")
                    elif command == "stop":
                        if self.runner_manager.stop_all_runners():
                            print("✓ Runners stopped successfully")
                        else:
                            print("✗ Some runners did not stop gracefully")
                    elif command == "status":
                        self.runner_manager.print_status_report()
                    elif command == "runners":
                        runners = self.runner_manager.get_all_runners()
                        print(f"\nRegistered Runners ({len(runners)}):")
                        for name, runner in runners.items():
                            print(
                                f"  - {name}: {runner.state.value} "
                                f"({'healthy' if runner.is_healthy() else 'unhealthy'})"
                            )
                    elif command == "power":
                        ina219_runner = self.runner_manager.get_runner("ina219")
                        if ina219_runner and hasattr(ina219_runner, "get_power_stats"):
                            stats = ina219_runner.get_power_stats()
                            if stats:
                                print("\nPower Statistics:")
                                print(f"  Average Power: {stats.avg_power:.2f}W")
                                print(f"  Voltage Range: {stats.avg_voltage:.2f}V")
                                print(f"  Current Range: {stats.avg_current:.3f}A")
                                print(
                                    f"  Power Range: {stats.min_power:.2f}W - {stats.max_power:.2f}W"
                                )
                                print(f"  Sample Count: {stats.sample_count}")
                            else:
                                print("No power statistics available yet")
                        else:
                            print("INA219 runner not available or not running")
                    elif command == "help" or command == "?":
                        print(
                            "Available commands: start, stop, status, runners, power, quit"
                        )
                    elif command:
                        print(
                            f"Unknown command: {command}. Type 'help' for available commands."
                        )

                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\nUse 'quit' to exit interactive mode")

        finally:
            print("Exiting interactive mode...")
            if self.runner_manager.is_running:
                self.runner_manager.shutdown()


def main():
    """Main function for the threaded runner demo."""
    demo = ThreadedRunnerDemo()

    if not demo.initialize():
        print("Failed to initialize demo")
        return 1

    try:
        print("Threaded Runner System Demo")
        print("=" * 40)
        print("1. Run 2-minute automatic demo")
        print("2. Run 5-minute automatic demo")
        print("3. Interactive mode")
        print("4. Exit")

        choice = input("\nSelect an option (1-4): ").strip()

        if choice == "1":
            demo.run_demo(2.0)
        elif choice == "2":
            demo.run_demo(5.0)
        elif choice == "3":
            demo.interactive_mode()
        elif choice == "4":
            print("Exiting...")
        else:
            print("Invalid choice. Running default 2-minute demo...")
            demo.run_demo(2.0)

    except KeyboardInterrupt:
        print("\nDemo interrupted")
    except Exception as e:
        print(f"Demo error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
