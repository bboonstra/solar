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

import py_trees
import yaml

# NEW: Import Behavior Tree Engine
from bt_engine import BehaviorTreeEngine

# Import configuration validator
from config_validator import validate_configuration_files

# NEW: Import RunnerManager for threaded runners
from runners.runner_manager import RunnerManager

# Import the specific error for better handling


# Get the directory where this script is located
SCRIPT_DIR = (
    Path(__file__).parent.parent / "configuration"
)  # Go up one level from src/ to configuration directory


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
    Load configuration from solar.yaml and runners.yaml with validation.

    Returns:
        Validated configuration dictionary

    Raises:
        FileNotFoundError: If required config files are not found
        ValueError: If configuration is invalid
    """
    solar_path = SCRIPT_DIR / "solar.yaml"
    runners_path = SCRIPT_DIR / "runners.yaml"
    env_path = SCRIPT_DIR / "environment.yaml"

    # Validate configuration files first
    if not validate_configuration_files(solar_path, runners_path, env_path):
        raise ValueError(
            "Configuration validation failed. Please check the logs for details."
        )

    try:
        # Load solar config
        with open(solar_path, "r") as f:
            solar_config = yaml.safe_load(f)

        # Load runners config
        with open(runners_path, "r") as f:
            runners_config = yaml.safe_load(f)

        # Merge configurations
        config = {**solar_config}  # Start with solar config
        config.update(runners_config)  # Add runners config

        return config
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Required configuration files not found. Please ensure solar.yaml and runners.yaml exist in {SCRIPT_DIR}."
        ) from exc
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration files: {e}") from e


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
            # Ensure FakeRPi is available or provide guidance
            try:
                import FakeRPi.GPIO as GPIO  # type: ignore

                logger.info("Loaded FakeRPi.GPIO for development environment")
            except ImportError:
                logger.error(
                    "FakeRPi.GPIO not found. Please install it for development: pip install FakeRPi"
                )
                return None
        return GPIO
    except ImportError as e:
        logger.critical(f"Could not import GPIO module: {e}")
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
        # Optionally, decide if the application can continue without GPIO
        # For a robot, this might be critical, so we could exit or run in a limited mode.
        # For now, we'll let it continue and the BT can decide what to do.

    # NEW: Initialize and start the RunnerManager (threaded runners)
    runner_manager = RunnerManager(config, production)
    if not runner_manager.start():
        logger.critical("Failed to start RunnerManager. Exiting.")
        return
    logger.info("RunnerManager started successfully.")

    # Initialize and run the Behavior Tree Engine
    bt_engine = BehaviorTreeEngine(config, production)

    if not bt_engine.setup():
        logger.critical("Failed to set up Behavior Tree Engine. Exiting.")
        runner_manager.shutdown()
        return

    logger.info("Starting SOLAR robot with Behavior Tree system...")

    try:
        # Main application loop - tick the Behavior Tree
        while True:  # Loop indefinitely, BT controls flow
            bt_engine.tick()

            # Check if the main BT sequence has finished or failed
            if bt_engine.tree and bt_engine.tree.root.status in [
                py_trees.common.Status.SUCCESS,  # type: ignore
                py_trees.common.Status.FAILURE,  # type: ignore
            ]:
                logger.info(
                    f"Behavior tree execution finished with status: {bt_engine.tree.root.status}"
                )
                break  # Exit main loop if BT is done

            time.sleep(config.get("application", {}).get("bt_tick_interval", 0.1))

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Error in main application loop: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        logger.info("Initiating graceful shutdown...")
        if bt_engine:
            bt_engine.shutdown()
        # NEW: Shutdown the runner manager
        if runner_manager:
            runner_manager.shutdown()
        # Add any other cleanup if necessary (e.g., GPIO cleanup if managed here)
        if gpio and hasattr(gpio, "cleanup"):
            try:
                gpio.cleanup()  # type: ignore
                logger.info("GPIO cleanup successful.")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()
