"""
Configuration Validation for SOLAR Robot

This module provides validation and schema checking for configuration files
to ensure all required settings are present and have valid values.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class LogLevel(str, Enum):
    """Valid log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RunnerType(str, Enum):
    """Valid runner types."""

    INA219 = "ina219"
    PIPOWER = "pipower"


@dataclass
class ValidationError:
    """Represents a validation error with context."""

    path: str  # Dot-separated path to the invalid field
    message: str
    value: Any = None
    expected: Any = None

    def __str__(self) -> str:
        msg = f"{self.path}: {self.message}"
        if self.value is not None:
            msg += f" (got: {self.value})"
        if self.expected is not None:
            msg += f" (expected: {self.expected})"
        return msg


class ConfigValidator:
    """Validates configuration dictionaries against expected schemas."""

    def __init__(self):
        """Initialize the configuration validator."""
        self.logger = logging.getLogger(__name__)
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def validate_config(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[ValidationError], List[ValidationError]]:
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
        self._validate_runners_config(config.get("runners", {}))
        self._validate_application_config(config.get("application", {}))
        self._validate_logging_config(config.get("logging", {}))

        # Validate cross-section relationships
        self._validate_cross_section_relationships(config)

        return len(self.errors) == 0, self.errors, self.warnings

    def validate_environment_config(
        self, env_config: Dict[str, Any]
    ) -> Tuple[bool, List[ValidationError], List[ValidationError]]:
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
            self.errors.append(
                ValidationError(
                    "production", "Missing required field", expected="boolean value"
                )
            )
        elif not isinstance(env_config["production"], bool):
            self.errors.append(
                ValidationError(
                    "production",
                    "Must be a boolean value",
                    value=env_config["production"],
                    expected="boolean",
                )
            )

        # Check for any unknown fields
        known_fields = {"production"}
        unknown_fields = set(env_config.keys()) - known_fields
        if unknown_fields:
            self.warnings.append(
                ValidationError(
                    "environment",
                    "Unknown fields found",
                    value=unknown_fields,
                    expected="only 'production'",
                )
            )

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_runners_config(self, runners_config: Dict[str, Any]) -> None:
        """
        Validate runners configuration section.

        Args:
            runners_config: Dictionary containing runners configuration
        """
        if not runners_config:
            self.errors.append(
                ValidationError(
                    "runners",
                    "Missing required section",
                    expected="dictionary with runner configurations",
                )
            )
            return

        # Validate each runner
        for runner_name, runner_config in runners_config.items():
            if not isinstance(runner_config, dict):
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}",
                        "Must be a dictionary",
                        value=type(runner_config).__name__,
                        expected="dictionary",
                    )
                )
                continue

            # Validate required fields
            required_fields = {"type", "label", "enabled"}
            missing_fields = required_fields - set(runner_config.keys())
            if missing_fields:
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}",
                        f"Missing required fields: {missing_fields}",
                        expected=f"fields: {required_fields}",
                    )
                )

            # Validate runner type
            if "type" in runner_config:
                try:
                    runner_type = RunnerType(runner_config["type"])
                except ValueError:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.type",
                            "Invalid runner type",
                            value=runner_config["type"],
                            expected=f"one of: {[t.value for t in RunnerType]}",
                        )
                    )
                else:
                    # Validate type-specific fields
                    if runner_type == RunnerType.INA219:
                        self._validate_ina219_runner(runner_name, runner_config)
                    elif runner_type == RunnerType.PIPOWER:
                        self._validate_pipower_runner(runner_name, runner_config)

    def _validate_ina219_runner(self, runner_name: str, config: Dict[str, Any]) -> None:
        """Validate INA219 runner configuration."""
        # Validate I2C address
        if "i2c_address" not in config:
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}.i2c_address",
                    "Missing required field",
                    expected="hexadecimal address (0x40, 0x41, 0x44, or 0x45)",
                )
            )
        else:
            valid_addresses = [0x40, 0x41, 0x44, 0x45]
            if config["i2c_address"] not in valid_addresses:
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.i2c_address",
                        "Invalid I2C address",
                        value=config["i2c_address"],
                        expected=f"one of: {valid_addresses}",
                    )
                )

        # Validate measurement interval
        if "measurement_interval" in config:
            interval = config["measurement_interval"]
            if not isinstance(interval, (int, float)):
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.measurement_interval",
                        "Must be a number",
                        value=type(interval).__name__,
                        expected="number",
                    )
                )
            elif interval <= 0:
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.measurement_interval",
                        "Must be positive",
                        value=interval,
                        expected="positive number",
                    )
                )
            elif interval < 0.1:
                self.warnings.append(
                    ValidationError(
                        f"runners.{runner_name}.measurement_interval",
                        "Value may cause high CPU usage",
                        value=interval,
                        expected=">= 0.1",
                    )
                )

        # Validate power thresholds
        for threshold in ["low_power_threshold", "high_power_threshold"]:
            if threshold in config:
                value = config[threshold]
                if not isinstance(value, (int, float)):
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{threshold}",
                            "Must be a number",
                            value=type(value).__name__,
                            expected="number",
                        )
                    )
                elif value < 0:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{threshold}",
                            "Must be non-negative",
                            value=value,
                            expected="non-negative number",
                        )
                    )

        # Check threshold relationship
        low = config.get("low_power_threshold", 0)
        high = config.get("high_power_threshold", 100)
        if low >= high:
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}",
                    "low_power_threshold must be less than high_power_threshold",
                    value=f"low={low}, high={high}",
                    expected="low < high",
                )
            )

    def _validate_pipower_runner(
        self, runner_name: str, config: Dict[str, Any]
    ) -> None:
        """Validate PiPower runner configuration."""
        # Validate required GPIO pins
        required_pins = {"bt_lv_pin", "in_dt_pin", "chg_pin", "lo_dt_pin"}
        missing_pins = required_pins - set(config.keys())
        if missing_pins:
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}",
                    f"Missing required GPIO pins: {missing_pins}",
                    expected=f"pins: {required_pins}",
                )
            )

        # Validate ADC channel
        if "adc_channel" not in config:
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}.adc_channel",
                    "Missing required field",
                    expected="ADC channel number (0-7)",
                )
            )
        elif not isinstance(config["adc_channel"], int):
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}.adc_channel",
                    "Must be an integer",
                    value=type(config["adc_channel"]).__name__,
                    expected="integer",
                )
            )
        elif not 0 <= config["adc_channel"] <= 7:
            self.errors.append(
                ValidationError(
                    f"runners.{runner_name}.adc_channel",
                    "Must be between 0 and 7",
                    value=config["adc_channel"],
                    expected="0-7",
                )
            )

        # Validate alert thresholds
        for threshold in ["low_battery_alert_threshold", "no_usb_alert_threshold"]:
            if threshold in config:
                value = config[threshold]
                if not isinstance(value, int):
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{threshold}",
                            "Must be an integer",
                            value=type(value).__name__,
                            expected="integer",
                        )
                    )
                elif value < 1:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{threshold}",
                            "Must be at least 1",
                            value=value,
                            expected=">= 1",
                        )
                    )

    def _validate_application_config(self, app_config: Dict[str, Any]) -> None:
        """
        Validate application configuration.

        Args:
            app_config: Dictionary containing application configuration
        """
        if not app_config:
            self.errors.append(
                ValidationError(
                    "application",
                    "Missing required section",
                    expected="dictionary with application settings",
                )
            )
            return

        # Validate threaded_runners
        if "threaded_runners" not in app_config:
            self.errors.append(
                ValidationError(
                    "application.threaded_runners",
                    "Missing required field",
                    expected="boolean value",
                )
            )
        elif not isinstance(app_config["threaded_runners"], bool):
            self.errors.append(
                ValidationError(
                    "application.threaded_runners",
                    "Must be a boolean",
                    value=type(app_config["threaded_runners"]).__name__,
                    expected="boolean",
                )
            )

        # Validate intervals
        for interval_key in ["main_loop_interval", "shutdown_timeout"]:
            if interval_key in app_config:
                value = app_config[interval_key]
                if not isinstance(value, (int, float)):
                    self.errors.append(
                        ValidationError(
                            f"application.{interval_key}",
                            "Must be a number",
                            value=type(value).__name__,
                            expected="number",
                        )
                    )
                elif value <= 0:
                    self.errors.append(
                        ValidationError(
                            f"application.{interval_key}",
                            "Must be positive",
                            value=value,
                            expected="positive number",
                        )
                    )

    def _validate_logging_config(self, logging_config: Dict[str, Any]) -> None:
        """
        Validate logging configuration.

        Args:
            logging_config: Dictionary containing logging configuration
        """
        if not logging_config:
            self.errors.append(
                ValidationError(
                    "logging",
                    "Missing required section",
                    expected="dictionary with logging settings",
                )
            )
            return

        # Validate log level
        if "level" not in logging_config:
            self.errors.append(
                ValidationError(
                    "logging.level",
                    "Missing required field",
                    expected=f"one of: {[level.value for level in LogLevel]}",
                )
            )
        else:
            try:
                LogLevel(logging_config["level"].upper())
            except ValueError:
                self.errors.append(
                    ValidationError(
                        "logging.level",
                        "Invalid log level",
                        value=logging_config["level"],
                        expected=f"one of: {[level.value for level in LogLevel]}",
                    )
                )

        # Validate colorized flag
        if "colorized" not in logging_config:
            self.errors.append(
                ValidationError(
                    "logging.colorized",
                    "Missing required field",
                    expected="boolean value",
                )
            )
        elif not isinstance(logging_config["colorized"], bool):
            self.errors.append(
                ValidationError(
                    "logging.colorized",
                    "Must be a boolean",
                    value=type(logging_config["colorized"]).__name__,
                    expected="boolean",
                )
            )

        # Validate colors if present
        if "colors" in logging_config:
            colors = logging_config["colors"]
            if not isinstance(colors, dict):
                self.errors.append(
                    ValidationError(
                        "logging.colors",
                        "Must be a dictionary",
                        value=type(colors).__name__,
                        expected="dictionary",
                    )
                )
            else:
                for level, color in colors.items():
                    if not isinstance(color, str):
                        self.errors.append(
                            ValidationError(
                                f"logging.colors.{level}",
                                "Must be a string",
                                value=type(color).__name__,
                                expected="string",
                            )
                        )

    def _validate_cross_section_relationships(self, config: Dict[str, Any]) -> None:
        """
        Validate relationships between different configuration sections.

        Args:
            config: Complete configuration dictionary
        """
        # Check if any runners are enabled
        runners = config.get("runners", {})
        enabled_runners = [
            name for name, runner in runners.items() if runner.get("enabled", False)
        ]
        if not enabled_runners:
            self.warnings.append(
                ValidationError(
                    "runners",
                    "No runners are enabled",
                    value=enabled_runners,
                    expected="at least one enabled runner",
                )
            )

        # Check if threaded_runners is enabled but no runners are configured
        if config.get("application", {}).get("threaded_runners", False) and not runners:
            self.warnings.append(
                ValidationError(
                    "application",
                    "threaded_runners is enabled but no runners are configured",
                    value="no runners",
                    expected="at least one runner configuration",
                )
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
