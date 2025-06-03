"""
Path Configuration for SOLAR Robot

This module provides centralized path configuration for the SOLAR robot system.
It defines important directory paths used throughout the application.
"""

from pathlib import Path

# Get the root directory of the project (parent of src directory)
ROOT_DIR = Path(__file__).parent.parent.parent

# Get the configuration directory
CONFIG_DIR = ROOT_DIR / "configuration"

# Get the data directory
DATA_DIR = ROOT_DIR / "data"
