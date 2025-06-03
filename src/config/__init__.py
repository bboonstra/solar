"""
Configuration Package for SOLAR Robot

This package provides centralized configuration management for the SOLAR robot system.
It includes path configurations and other shared settings.
"""

from .paths import CONFIG_DIR, DATA_DIR, ROOT_DIR

__all__ = ["CONFIG_DIR", "DATA_DIR", "ROOT_DIR"]
