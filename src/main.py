import yaml
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Import the specific error for better handling
from sensors.ina219_power_monitor import SensorReadError

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.parent  # Go up one level from src/ to project root


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure logging with colorized output based on configuration."""
    log_level = config.get("log_level", "INFO").upper()
    use_colors = config.get("colorized_logging", True)

    try:
        if use_colors:
            import colorlog

            # Create a colorized formatter
            formatter = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "purple",
                    "INFO": "blue",
                    "WARNING": "yellow",
                    "ERROR": "orange",
                    "CRITICAL": "red,bg_white",
                },
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
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        if use_colors:
            print(
                "Note: colorlog not installed - using standard logging. Install with: pip install colorlog"
            )

    return logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load main configuration from config.yaml."""
    config_path = SCRIPT_DIR / "config.yaml"
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. Please ensure it exists in the project root."
        )
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config.yaml: {e}")


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
    """Main application entry point with INA219 power monitoring."""
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

    # Initialize INA219 Power Monitor
    try:
        from sensors import INA219PowerMonitor

        power_monitor = INA219PowerMonitor(config, production)
        logger.info("INA219 Power Monitor initialized successfully")

        # Demonstrate power monitoring in a loop
        logger.info("Starting power monitoring demonstration...")

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
