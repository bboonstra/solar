import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.parent  # Go up one level from src/ to project root


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Configure logging based on configuration."""
    log_level = config.get("log_level", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
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
    """Main application entry point."""
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


if __name__ == "__main__":
    main()
