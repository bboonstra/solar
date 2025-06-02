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

    def validate_application_config(
        self, app_config: Dict[str, Any]
    ) -> Tuple[bool, List[ValidationError], List[ValidationError]]:
        """
        Validate the application configuration section.

        Args:
            app_config: Application configuration dictionary to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate application section
        self._validate_application_config(app_config)
        self._validate_logging_config(app_config.get("logging", {}))

        return len(self.errors) == 0, self.errors, self.warnings

    def validate_runners_config(
        self, runners_config: Dict[str, Any]
    ) -> Tuple[bool, List[ValidationError], List[ValidationError]]:
        """
        Validate the runners configuration section.

        Args:
            runners_config: Runners configuration dictionary to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate runners section
        self._validate_runners_config(runners_config)

        return len(self.errors) == 0, self.errors, self.warnings

    def validate_environment_config(
        self, env_config: Dict[str, Any]
    ) -> Tuple[bool, List[ValidationError], List[ValidationError]]:
        """
        Validate the environment configuration.

        Args:
            env_config: Environment configuration dictionary to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        if not isinstance(env_config, dict):
            self.errors.append(
                ValidationError(
                    "environment",
                    "Must be a dictionary",
                    value=type(env_config).__name__,
                    expected="dictionary",
                )
            )
            return False, self.errors, self.warnings

        if "production" not in env_config:
            self.errors.append(
                ValidationError(
                    "environment.production",
                    "Missing required field",
                    expected="boolean value",
                )
            )
        elif not isinstance(env_config["production"], bool):
            self.errors.append(
                ValidationError(
                    "environment.production",
                    "Must be a boolean",
                    value=type(env_config["production"]).__name__,
                    expected="boolean",
                )
            )

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_runners_config(self, runners_config: Dict[str, Any]) -> None:
        """
        Validate runners configuration.

        Args:
            runners_config: Dictionary containing runners configuration
        """
        if not runners_config:
            self.errors.append(
                ValidationError(
                    "runners",
                    "Missing required section",
                    expected="dictionary with runner settings",
                )
            )
            return

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
            required_fields = ["type", "label", "enabled"]
            for field in required_fields:
                if field not in runner_config:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{field}",
                            "Missing required field",
                            expected=f"string value for {field}",
                        )
                    )

            # Validate field types
            if "enabled" in runner_config and not isinstance(
                runner_config["enabled"], bool
            ):
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.enabled",
                        "Must be a boolean",
                        value=type(runner_config["enabled"]).__name__,
                        expected="boolean",
                    )
                )

            if "measurement_interval" in runner_config:
                interval = runner_config["measurement_interval"]
                if not isinstance(interval, (int, float)) or interval <= 0:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.measurement_interval",
                            "Must be a positive number",
                            value=str(interval),
                            expected="positive number",
                        )
                    )

            # Validate type-specific fields
            runner_type = runner_config.get("type")
            if runner_type == "ina219":
                self._validate_ina219_config(runner_name, runner_config)
            elif runner_type == "pipower":
                self._validate_pipower_config(runner_name, runner_config)

    def _validate_ina219_config(self, runner_name: str, config: Dict[str, Any]) -> None:
        """Validate INA219 specific configuration."""
        required_fields = ["i2c_address", "low_power_threshold", "high_power_threshold"]
        for field in required_fields:
            if field not in config:
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.{field}",
                        "Missing required field",
                        expected=f"value for {field}",
                    )
                )

        if "i2c_address" in config:
            addr = config["i2c_address"]
            if not isinstance(addr, str) or not addr.startswith("0x"):
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.i2c_address",
                        "Must be a hex string",
                        value=str(addr),
                        expected="hex string (e.g., '0x40')",
                    )
                )

    def _validate_pipower_config(
        self, runner_name: str, config: Dict[str, Any]
    ) -> None:
        """Validate PiPower specific configuration."""
        required_fields = [
            "bt_lv_pin",
            "adc_channel",
            "in_dt_pin",
            "chg_pin",
            "lo_dt_pin",
        ]
        for field in required_fields:
            if field not in config:
                self.errors.append(
                    ValidationError(
                        f"runners.{runner_name}.{field}",
                        "Missing required field",
                        expected=f"value for {field}",
                    )
                )

        # Validate GPIO pin numbers
        gpio_fields = ["bt_lv_pin", "in_dt_pin", "chg_pin", "lo_dt_pin"]
        for field in gpio_fields:
            if field in config:
                pin = config[field]
                if not isinstance(pin, int) or not 0 <= pin <= 27:
                    self.errors.append(
                        ValidationError(
                            f"runners.{runner_name}.{field}",
                            "Must be a valid GPIO pin number",
                            value=str(pin),
                            expected="integer between 0 and 27",
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


def validate_configuration_files(
    solar_path: Path, runners_path: Path, env_path: Path
) -> bool:
    """
    Validate configuration files and report any issues.

    Args:
        solar_path: Path to solar.yaml
        runners_path: Path to runners.yaml
        env_path: Path to environment.yaml

    Returns:
        True if all validations pass, False otherwise
    """
    validator = ConfigValidator()
    logger = logging.getLogger(__name__)
    all_valid = True

    # Validate solar config
    try:
        with open(solar_path, "r", encoding="utf-8") as f:
            solar_config = yaml.safe_load(f)

        # Validate application and logging sections
        is_valid, errors, warnings = validator.validate_application_config(
            solar_config.get("application", {})
        )
        all_valid = all_valid and is_valid

        if errors:
            logger.error(f"Configuration validation errors in {solar_path}:")
            for error in errors:
                logger.error(f"  - {error}")
            all_valid = False

        if warnings:
            logger.warning(f"Configuration warnings in {solar_path}:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {solar_path}")
        all_valid = False
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {solar_path}: {e}")
        all_valid = False

    # Validate runners config
    try:
        with open(runners_path, "r", encoding="utf-8") as f:
            runners_config = yaml.safe_load(f)

        # Validate runners section
        is_valid, errors, warnings = validator.validate_runners_config(
            runners_config.get("runners", {})
        )
        all_valid = all_valid and is_valid

        if errors:
            logger.error(f"Configuration validation errors in {runners_path}:")
            for error in errors:
                logger.error(f"  - {error}")
            all_valid = False

        if warnings:
            logger.warning(f"Configuration warnings in {runners_path}:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {runners_path}")
        all_valid = False
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in {runners_path}: {e}")
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
