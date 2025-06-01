#!/usr/bin/env python3
"""
Power Monitor Demonstration Script for SOLAR Robot

This script demonstrates how to use the INA219 power monitor in a main loop
to continuously monitor voltage, current, and power consumption.

Usage:
    python src/examples/power_monitor_demo.py
"""

import signal
import sys
import time
from pathlib import Path

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import load_config, load_environment_config, setup_logging
from sensors import INA219PowerMonitor


class PowerMonitorDemo:
    """Demonstration class for the INA219 power monitor."""

    def __init__(self):
        """Initialize the power monitor demo."""
        self.running = False
        self.power_monitor = None

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False

    def initialize(self):
        """Initialize the power monitoring system."""
        try:
            # Load configuration and setup logging
            config = load_config()
            logger = setup_logging(config)

            # Determine environment
            production = load_environment_config(logger)

            # Initialize power monitor
            self.power_monitor = INA219PowerMonitor(config, production)

            logger.info("Power monitor demo initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize power monitor demo: {e}")
            return False

    def run_single_reading(self):
        """Take a single power reading and display the results."""
        if not self.power_monitor:
            print("Power monitor not initialized!")
            return

        try:
            # Get a power reading
            reading = self.power_monitor.get_reading()

            # Display the results
            print("\n--- Power Reading ---")
            print(f"Voltage: {reading.voltage:.2f} V")
            print(f"Current: {reading.current:.3f} A")
            print(f"Power:   {reading.power:.2f} W")
            print(
                f"Time:    {time.strftime('%H:%M:%S', time.localtime(reading.timestamp))}"
            )

            # Check sensor health
            if self.power_monitor.is_healthy():
                print("Status:  ✓ Healthy")
            else:
                print("Status:  ⚠ Warning - Check sensor")

        except Exception as e:
            print(f"Error taking reading: {e}")

    def run_continuous_monitoring(self):
        """Run continuous power monitoring loop."""
        if not self.power_monitor:
            print("Power monitor not initialized!")
            return

        print("Starting continuous power monitoring...")
        print("Press Ctrl+C to stop\n")

        self.running = True
        reading_count = 0

        while self.running:
            try:
                # Get a power reading
                reading = self.power_monitor.get_reading()
                reading_count += 1

                # Display compact reading
                print(
                    f"[{reading_count:04d}] "
                    f"{time.strftime('%H:%M:%S')} | "
                    f"V: {reading.voltage:5.2f}V | "
                    f"I: {reading.current:6.3f}A | "
                    f"P: {reading.power:5.2f}W"
                )

                # Sleep for the configured interval
                time.sleep(self.power_monitor.measurement_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(1)  # Brief pause before retrying

        print(f"\nMonitoring stopped after {reading_count} readings")

    def show_status(self):
        """Display comprehensive sensor status."""
        if not self.power_monitor:
            print("Power monitor not initialized!")
            return

        try:
            status = self.power_monitor.get_status()

            print("\n--- INA219 Power Monitor Status ---")
            print(f"Sensor Type:    {status['sensor_type']}")
            print(f"I2C Address:    {status['i2c_address']}")
            print(f"Mode:           {status['mode']}")
            print(
                f"Health Status:  {'✓ Healthy' if status['healthy'] else '⚠ Warning'}"
            )

            print("\nThresholds:")
            print(f"  Low Power:    {status['thresholds']['low_power']} W")
            print(f"  High Power:   {status['thresholds']['high_power']} W")

            if status["last_reading"]:
                reading = status["last_reading"]
                print("\nLast Reading:")
                print(f"  Voltage:      {reading.voltage:.2f} V")
                print(f"  Current:      {reading.current:.3f} A")
                print(f"  Power:        {reading.power:.2f} W")
                print(
                    f"  Timestamp:    {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reading.timestamp))}"
                )
            else:
                print("\nNo readings taken yet")

        except Exception as e:
            print(f"Error getting status: {e}")


def main():
    """Main function for the power monitor demo."""
    demo = PowerMonitorDemo()

    # Initialize the system
    if not demo.initialize():
        print("Failed to initialize. Exiting.")
        sys.exit(1)

    # Show menu options
    while True:
        print("\n" + "=" * 50)
        print("SOLAR Robot - INA219 Power Monitor Demo")
        print("=" * 50)
        print("1. Take single reading")
        print("2. Start continuous monitoring")
        print("3. Show sensor status")
        print("4. Exit")

        try:
            choice = input("\nSelect option (1-4): ").strip()

            if choice == "1":
                demo.run_single_reading()
            elif choice == "2":
                demo.run_continuous_monitoring()
            elif choice == "3":
                demo.show_status()
            elif choice == "4":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please select 1-4.")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


if __name__ == "__main__":
    main()
