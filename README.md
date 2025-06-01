# SOLAR — Semi-Autonomous Outdoor Life Assisting Robot

[![Python CI](https://github.com/bboonstra/solar/actions/workflows/python-ci.yml/badge.svg)](https://github.com/bboonstra/solar/actions/workflows/python-ci.yml)
[![License: Polyform Noncommercial](https://img.shields.io/badge/License-Polyform%20Noncommercial-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

SOLAR is a research-driven robotics project aimed at exploring sustainable, autonomous plant care through sensor data collection and environmental interaction. Designed for outdoor environments, SOLAR monitors conditions such as soil moisture, temperature, humidity, and light levels, and takes physical actions to support vegetation growth.

## 🌱 Project Goal

Investigate how robotics can enhance environmental sustainability by automating basic plant care tasks like watering, soil monitoring, and sample collection.

## ✨ Key Features

- **Modular Sensor Integration**: Extensible architecture for adding new sensors
- **Real-time Environmental Monitoring**: Continuous data collection with configurable intervals
- **Autonomous Decision-making**: Scheduling and control logic for plant care
- **Threaded Runner System**: Concurrent sensor monitoring for optimal performance
- **Development Mode**: Full simulation support for testing without hardware
- **Comprehensive Logging**: Colorized output with configurable log levels
- **Health Monitoring**: Automatic error detection and recovery
- **Custom Hardware Support**: GPIO, pneumatic actuation, custom servos

## 🏗️ Architecture

### Core Components

1. **Runner System** (`src/runners/`)
   - `BaseRunner`: Abstract base class for all sensor/actuator modules
   - `RunnerManager`: Central coordinator for concurrent operations
   - `INA219Runner`: Power monitoring implementation

2. **Sensor Modules** (`src/sensors/`)
   - Hardware abstraction layer with production/development modes
   - Standardized interfaces for all sensor types
   - Built-in error handling and recovery

3. **Main Application** (`src/main.py`)
   - Configuration loading and validation
   - Environment detection
   - Graceful startup/shutdown

### System Design

```
┌─────────────────┐
│  Main Process   │
│   (main.py)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Runner  │
    │ Manager │
    └────┬────┘
         │
    ┌────┴────────────────┬─────────────┬─────────────┐
    │                     │             │             │
┌───┴────┐         ┌─────┴────┐  ┌────┴────┐  ┌─────┴────┐
│INA219  │         │  Sensor  │  │ Actuator│  │  Future  │
│Runner  │         │  Runner  │  │ Runner  │  │  Runner  │
└────────┘         └──────────┘  └─────────┘  └──────────┘
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Raspberry Pi (for production mode)
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/bboonstra/solar.git
   cd solar
   ```

2. **Set up virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip setuptools
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the application**

   ```bash
   cp environment.example.yaml environment.yaml
   # Edit environment.yaml to set production: true/false
   # Edit config.yaml to configure sensors and behavior
   ```

5. **Run the application**

   ```bash
   python src/main.py
   ```

## 📋 Configuration

### Environment Configuration (`environment.yaml`)

```yaml
# Set to true when running on actual Raspberry Pi hardware
production: false
```

### Main Configuration (`config.yaml`)

```yaml
# GPIO pin assignments
gpio:
  led_pin: 18
  sensor_pin: 24

# Power monitoring configuration
ina219:
  enabled: true
  i2c_address: 0x40
  measurement_interval: 1.0
  log_measurements: true
  low_power_threshold: 0.5
  high_power_threshold: 10.0

# Application settings
application:
  threaded_runners: true
  main_loop_interval: 2
  shutdown_timeout: 5.0

# Logging configuration
logging:
  level: "INFO"
  colorized: true
```

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_base_runner.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
pylint src/
```

### Adding New Sensors

1. Create a new runner class:

   ```python
   # src/runners/my_sensor_runner.py
   from .base_runner import BaseRunner
   
   class MySensorRunner(BaseRunner):
       def _initialize(self) -> bool:
           # Initialize hardware/simulation
           return True
       
       def _work_cycle(self) -> None:
           # Perform measurement
           pass
       
       def is_healthy(self) -> bool:
           # Check sensor health
           return True
   ```

2. Register in `RunnerManager`:

   ```python
   self._runner_classes = {
       "ina219": INA219Runner,
       "my_sensor": MySensorRunner,  # Add here
   }
   ```

3. Add configuration section:

   ```yaml
   my_sensor:
     enabled: true
     measurement_interval: 2.0
   ```

## 📚 Documentation

- [Threaded Runner System](THREADED_RUNNERS.md) - Detailed architecture documentation
- [Development Guide](development.md) - Setup and development workflow
- [API Reference](docs/api/) - Coming soon

## 🤝 Contributing

This project is open for **non-commercial tinkering and experimentation**. We welcome contributions that:

- Add new sensor support
- Improve error handling and recovery
- Enhance documentation
- Fix bugs
- Add tests

Please ensure all contributions:

- Include appropriate documentation
- Have test coverage
- Follow the existing code style
- Are submitted via pull request

## 📄 License

Licensed under the [Polyform Noncommercial License](https://polyformproject.org/licenses/noncommercial/1.0.0/). You may use, modify, and share this work **for noncommercial purposes only**.

## 💰 Funding

If you find this project useful, please consider [sponsoring the team](https://solar.bboonstra.dev/).

## 🏆 Credits

- **Conner Israel** - Hardware Design & Integration
- **Ben Boonstra** - Software Architecture & Development
- **SOLAR Research Team** - Testing & Documentation

---

*Semi-Autonomous Outdoor Life Assisting Robot · 2025*
