"""
SOLAR Robot Main Application Entry Point

This module serves as the main entry point for the Semi-Autonomous Outdoor Life
Assisting Robot (SOLAR) system. It handles:

- Configuration loading and validation
- Logging setup with optional colorization
- Environment detection (production vs development)
- GPIO module loading based on environment
- Runner system initialization and management
- Graceful shutdown handling

The application supports two modes:
1. Threaded Runner Mode (default): Multi-threaded sensor monitoring
2. Legacy Mode (deprecated): Sequential single-threaded operation

Usage:
    python src/main.py

Configuration:
    - config.yaml: Main application configuration
    - environment.yaml: Environment-specific settings (production/development)

Requirements:
    - Python 3.8+
    - See requirements.txt for dependencies
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Import configuration validator
from config_validator import validate_configuration_files

# Import the specific error for better handling
from sensors.ina219_power_monitor import SensorReadError

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.parent  # Go up one level from src/ to project root


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure logging with colorized output based on configuration."""
    # Get logging configuration with defaults
    logging_config = config.get("logging", {})
    log_level = logging_config.get("level", "INFO").upper()
    use_colors = logging_config.get("colorized", True)

    # Get color and format settings
    colors = logging_config.get(
        "colors",
        {
            "DEBUG": "blue",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    format_config = logging_config.get("format", {})
    date_format = format_config.get("date_format", "%Y-%m-%d %H:%M:%S")
    color_format = format_config.get(
        "message_format",
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    simple_format = format_config.get(
        "simple_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        if use_colors:
            import colorlog

            # Create a colorized formatter with configurable colors
            formatter = colorlog.ColoredFormatter(
                color_format,
                datefmt=date_format,
                log_colors=colors,
                secondary_log_colors={},
                style="%",
            )

            # Get the root logger and clear any existing handlers
            root_logger = logging.getLogger()
            if root_logger.handlers:
                for handler in root_logger.handlers:
                    root_logger.removeHandler(handler)

            # Create console handler with the colorized formatter
            handler = colorlog.StreamHandler()
            handler.setFormatter(formatter)

            # Configure logging
            logging.basicConfig(level=getattr(logging, log_level), handlers=[handler])
        else:
            # Use standard logging when colors are disabled
            raise ImportError("Colorized logging disabled in configuration")

    except ImportError:
        # Fallback to standard logging if colorlog is not available or disabled
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=simple_format,
            datefmt=date_format,
        )
        if use_colors:
            print(
                "Note: colorlog not installed - using standard logging. Install with: pip install colorlog"
            )

    return logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """
    Load main configuration from config.yaml with validation.

    Returns:
        Validated configuration dictionary

    Raises:
        FileNotFoundError: If config.yaml is not found
        ValueError: If configuration is invalid
    """
    config_path = SCRIPT_DIR / "config.yaml"
    env_path = SCRIPT_DIR / "environment.yaml"

    # Validate configuration files first
    if not validate_configuration_files(config_path, env_path):
        raise ValueError(
            "Configuration validation failed. Please check the logs for details."
        )

    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. Please ensure it exists in the project root."
        ) from exc
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config.yaml: {e}") from e


def load_environment_config(logger: logging.Logger) -> bool:
    """Load environment configuration and return production flag."""
    env_config_path = SCRIPT_DIR / "environment.yaml"
    try:
        with open(env_config_path, "r") as f:
            env_config = yaml.safe_load(f)
        production = env_config.get("production", False)
        logger.info(f"Environment: {'production' if production else 'development'}")
        return production
    except FileNotFoundError:
        logger.warning(
            f"environment.yaml not found at {env_config_path}, defaulting to development mode"
        )
        return False
    except yaml.YAMLError as e:
        logger.warning(
            f"Invalid YAML in environment.yaml: {e}. Defaulting to development mode"
        )
        return False


def load_gpio_module(production: bool, logger: logging.Logger) -> Optional[Any]:
    """Load appropriate GPIO module based on environment."""
    try:
        if production:
            import RPi.GPIO as GPIO  # type: ignore

            logger.info("Loaded RPi.GPIO for production environment")
        else:
            import FakeRPi.GPIO as GPIO  # type: ignore

            logger.info("Loaded FakeRPi.GPIO for development environment")
        return GPIO
    except ImportError as e:
        logger.error(f"Could not import GPIO module: {e}")
        logger.info("Please install the appropriate GPIO library:")
        logger.info(f"  pip install {'RPi.GPIO' if production else 'FakeRPi'}")
        return None


def main() -> None:
    """Main application entry point with threaded runner system."""
    # Load configuration and setup logging
    config = load_config()
    logger = setup_logging(config)

    # Determine environment
    production = load_environment_config(logger)

    # Load GPIO module
    gpio = load_gpio_module(production, logger)

    if gpio is not None:
        logger.info("GPIO module loaded successfully - ready for hardware operations")
    else:
        logger.error("GPIO module not available - hardware operations will fail")

    # Initialize and run the threaded runner system
    try:
        from runners import RunnerManager

        # Create the runner manager
        runner_manager = RunnerManager(config, production)
        logger.info("Runner manager initialized successfully")

        # Check if threaded runners are enabled
        if not runner_manager.threaded_runners_enabled:
            logger.info("Threaded runners disabled in configuration")
            logger.info("Running in legacy mode - this is deprecated")
            _run_legacy_mode(config, production, logger)
            return

        # Run the main application loop with runners
        logger.info("Starting SOLAR robot with threaded runner system...")

        try:
            # Start the runner manager (this will auto-register and start runners)
            if runner_manager.start():
                logger.info("All runners started successfully")

                # Main application loop
                logger.info("Entering main application loop...")
                _run_main_loop(runner_manager, logger)

            else:
                logger.error("Failed to start runner manager")

        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Error in main application loop: {e}")
        finally:
            # Graceful shutdown
            logger.info("Initiating graceful shutdown...")
            runner_manager.shutdown()
            logger.info("Application shutdown complete")

    except ImportError as e:
        logger.error(f"Could not import RunnerManager: {e}")
        logger.info("Falling back to legacy mode")
        _run_legacy_mode(config, production, logger)
    except Exception as e:
        logger.error(f"Failed to initialize or run threaded system: {e}")


def _run_main_loop(runner_manager, logger: logging.Logger) -> None:
    """
    Run the main application loop with periodic status reports.

    Args:
        runner_manager: The RunnerManager instance
        logger: Logger instance
    """
    status_report_interval = 30.0  # Report status every 30 seconds
    last_status_report = time.time()

    while runner_manager.is_running:
        try:
            # Check if it's time for a status report
            current_time = time.time()
            if current_time - last_status_report >= status_report_interval:
                logger.info("Generating periodic status report...")
                runner_manager.print_status_report()
                last_status_report = current_time

                # Log power readings if INA219 runner is available
                ina219_runner = runner_manager.get_runner("ina219")
                if ina219_runner and hasattr(ina219_runner, "get_last_reading"):
                    last_reading = ina219_runner.get_last_reading()
                    if last_reading:
                        logger.info(
                            f"Latest Power Reading - V: {last_reading.voltage:.2f}V, "
                            f"I: {last_reading.current:.3f}A, P: {last_reading.power:.2f}W"
                        )

                    # Log power statistics
                    if hasattr(ina219_runner, "get_power_stats"):
                        stats = ina219_runner.get_power_stats()
                        if stats:
                            logger.info(
                                f"Power Statistics - Avg: {stats.avg_power:.2f}W, "
                                f"Min: {stats.min_power:.2f}W, Max: {stats.max_power:.2f}W "
                                f"({stats.sample_count} samples)"
                            )

            # Sleep for a short interval
            time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Main loop interrupted")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(1.0)  # Brief pause before continuing


def _run_legacy_mode(
    config: Dict[str, Any], production: bool, logger: logging.Logger
) -> None:
    """
    Run the legacy single-threaded mode (deprecated).

    This is kept for backwards compatibility but should be phased out.
    """
    logger.warning("Running in legacy mode - please enable threaded_runners in config")

    # Initialize INA219 Power Monitor directly (legacy approach)
    try:
        from sensors import INA219PowerMonitor

        power_monitor = INA219PowerMonitor(config, production)
        logger.info("INA219 Power Monitor initialized successfully")

        # Demonstrate power monitoring in a loop
        logger.info("Starting legacy power monitoring demonstration...")

        for i in range(10):  # Take 10 readings
            try:
                # Get a power reading
                reading = power_monitor.get_reading()

                # Log the reading
                logger.info(
                    f"Reading {i + 1}: V={reading.voltage:.2f}V, "
                    f"I={reading.current:.3f}A, P={reading.power:.2f}W"
                )

                # Check if we're in a healthy state
                if not power_monitor.is_healthy():
                    logger.warning("Power monitor reported as unhealthy!")

                # Wait before next reading
                time.sleep(power_monitor.measurement_interval)

            except SensorReadError as sre:
                logger.error(f"Sensor read error during monitoring loop: {sre}")
                logger.info(
                    "This might indicate a hardware issue or a problem with the sensor adapter."
                )
                # Depending on severity, we might want to break, retry, or enter a degraded mode.
                # For this example, we'll break the loop.
                logger.info(
                    "Stopping power monitoring demonstration due to sensor error."
                )
                break
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error during power monitoring: {e}")
                break

        # Show final status
        status = power_monitor.get_status()
        logger.info(f"Power monitoring complete. Final status: {status}")

    except ImportError as e:
        logger.error(f"Could not import INA219PowerMonitor: {e}")
        logger.info("Make sure the sensors module is properly installed")
    except SensorReadError as sre_init:  # Catch SensorReadError during initialization
        logger.critical(
            f"Failed to initialize INA219 Power Monitor due to sensor error: {sre_init}"
        )
        logger.info(
            "Please check hardware connections if in production, or simulation setup."
        )
    except Exception as e:
        logger.error(f"Failed to initialize or run power monitoring: {e}")


if __name__ == "__main__":
    main()
