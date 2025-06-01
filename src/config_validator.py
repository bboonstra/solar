"""
Configuration Validation for SOLAR Robot

This module provides validation and schema checking for configuration files
to ensure all required settings are present and have valid values.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class ConfigValidator:
    """Validates configuration dictionaries against expected schemas."""

    def __init__(self):
        """Initialize the configuration validator."""
        self.logger = logging.getLogger(__name__)
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_config(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate the main configuration file.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate top-level sections
        self._validate_gpio_config(config.get("gpio", {}))
        self._validate_ina219_config(config.get("ina219", {}))
        self._validate_application_config(config.get("application", {}))
        self._validate_logging_config(config.get("logging", {}))

        return len(self.errors) == 0, self.errors, self.warnings

    def validate_environment_config(
        self, env_config: Dict[str, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate the environment configuration file.

        Args:
            env_config: Environment configuration dictionary

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Check for production flag
        if "production" not in env_config:
            self.errors.append("Missing 'production' field in environment.yaml")
        elif not isinstance(env_config["production"], bool):
            self.errors.append("'production' must be a boolean value")

        # Check for any unknown fields
        known_fields = {"production"}
        unknown_fields = set(env_config.keys()) - known_fields
        if unknown_fields:
            self.warnings.append(
                f"Unknown fields in environment.yaml: {unknown_fields}"
            )

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_gpio_config(self, gpio_config: Dict[str, Any]) -> None:
        """
        Validate GPIO configuration section.

        Args:
            gpio_config: Dictionary containing GPIO configuration
        """
        # Validate GPIO pins if specified
        for key, value in gpio_config.items():
            if "pin" in key.lower():
                if not isinstance(value, int):
                    self.errors.append(
                        f"GPIO {key} must be an integer, got {type(value).__name__}"
                    )
                elif not 0 <= value <= 27:  # Raspberry Pi GPIO range
                    self.warnings.append(
                        f"GPIO {key} value {value} may be out of range (0-27)"
                    )

    def _validate_ina219_config(self, ina219_config: Dict[str, Any]) -> None:
        """
        Validate INA219 sensor configuration.

        Args:
            ina219_config: Dictionary containing INA219 sensor configuration
        """
        # Check required fields
        if "enabled" not in ina219_config:
            self.warnings.append("INA219 'enabled' field missing, defaulting to True")
        elif not isinstance(ina219_config["enabled"], bool):
            self.errors.append("INA219 'enabled' must be a boolean")

        # Validate I2C address
        if "i2c_address" in ina219_config:
            addr = ina219_config["i2c_address"]
            valid_addresses = [0x40, 0x41, 0x44, 0x45]
            if addr not in valid_addresses:
                self.errors.append(
                    f"INA219 i2c_address must be one of {valid_addresses}, got {addr}"
                )

        # Validate measurement interval
        if "measurement_interval" in ina219_config:
            interval = ina219_config["measurement_interval"]
            if not isinstance(interval, (int, float)):
                self.errors.append("INA219 measurement_interval must be a number")
            elif interval <= 0:
                self.errors.append("INA219 measurement_interval must be positive")
            elif interval < 0.1:
                self.warnings.append(
                    "INA219 measurement_interval < 0.1s may cause high CPU usage"
                )

        # Validate power thresholds
        for threshold in ["low_power_threshold", "high_power_threshold"]:
            if threshold in ina219_config:
                value = ina219_config[threshold]
                if not isinstance(value, (int, float)):
                    self.errors.append(f"INA219 {threshold} must be a number")
                elif value < 0:
                    self.errors.append(f"INA219 {threshold} must be non-negative")

        # Check threshold relationship
        low = ina219_config.get("low_power_threshold", 0)
        high = ina219_config.get("high_power_threshold", 100)
        if low >= high:
            self.errors.append(
                "INA219 low_power_threshold must be less than high_power_threshold"
            )

    def _validate_application_config(self, app_config: Dict[str, Any]) -> None:
        """
        Validate application configuration.

        Args:
            app_config: Dictionary containing application configuration
        """
        # Check threaded_runners
        if "threaded_runners" in app_config:
            if not isinstance(app_config["threaded_runners"], bool):
                self.errors.append("Application 'threaded_runners' must be a boolean")

        # Validate intervals
        for interval_key in ["main_loop_interval", "shutdown_timeout"]:
            if interval_key in app_config:
                value = app_config[interval_key]
                if not isinstance(value, (int, float)):
                    self.errors.append(f"Application '{interval_key}' must be a number")
                elif value <= 0:
                    self.errors.append(f"Application '{interval_key}' must be positive")

    def _validate_logging_config(self, logging_config: Dict[str, Any]) -> None:
        """
        Validate logging configuration.

        Args:
            logging_config: Dictionary containing logging configuration
        """
        # Validate log level
        if "level" in logging_config:
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            level = logging_config["level"].upper()
            if level not in valid_levels:
                self.errors.append(
                    f"Logging level must be one of {valid_levels}, got '{level}'"
                )

        # Validate colorized flag
        if "colorized" in logging_config:
            if not isinstance(logging_config["colorized"], bool):
                self.errors.append("Logging 'colorized' must be a boolean")

        # Validate colors if present
        if "colors" in logging_config:
            colors = logging_config["colors"]
            if not isinstance(colors, dict):
                self.errors.append("Logging 'colors' must be a dictionary")
            else:
                for level, color in colors.items():
                    if not isinstance(color, str):
                        self.errors.append(
                            f"Logging color for '{level}' must be a string"
                        )


def validate_configuration_files(config_path: Path, env_path: Path) -> bool:
    """
    Validate both configuration files and report any issues.

    Args:
        config_path: Path to config.yaml
        env_path: Path to environment.yaml

    Returns:
        True if all validations pass, False otherwise
    """
    validator = ConfigValidator()
    logger = logging.getLogger(__name__)
    all_valid = True

    # Validate main config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        is_valid, errors, warnings = validator.validate_config(config)
        all_valid = all_valid and is_valid

        if errors:
            logger.error(f"Configuration validation errors in {config_path}:")
            for error in errors:
                logger.error(f"  - {error}")
            all_valid = False

        if warnings:
            logger.warning(f"Configuration warnings in {config_path}:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        all_valid = False
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {config_path}: {e}")
        all_valid = False

    # Validate environment config
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            env_config = yaml.safe_load(f)

        is_valid, errors, warnings = validator.validate_environment_config(env_config)
        all_valid = all_valid and is_valid

        if errors:
            logger.error(f"Environment configuration errors in {env_path}:")
            for error in errors:
                logger.error(f"  - {error}")
            all_valid = False

        if warnings:
            logger.warning(f"Environment configuration warnings in {env_path}:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    except FileNotFoundError:
        logger.warning(f"Environment file not found: {env_path} (using defaults)")
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {env_path}: {e}")
        all_valid = False

    return all_valid
