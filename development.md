# Development Guide

This guide provides detailed instructions for setting up and developing the SOLAR robot project.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Development Environment](#development-environment)
- [Running the Application](#running-the-application)
- [Development Workflow](#development-workflow)
- [Hardware Testing](#hardware-testing)
- [Debugging](#debugging)
- [Performance Profiling](#performance-profiling)

## 📦 Prerequisites

### Software Requirements

- **Python 3.8+** (3.10 recommended)
- **Git** for version control
- **pip** for package management
- **Virtual environment** support

### Hardware Requirements (Production Mode)

- **Raspberry Pi** (3B+ or newer recommended)
- **INA219** power monitoring sensor
- **I2C** enabled on Raspberry Pi
- **GPIO** access permissions

### Optional Tools

- **VS Code** or **PyCharm** for development
- **Docker** for containerized development
- **screen** or **tmux** for remote sessions

## 🚀 Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/bboonstra/solar.git
cd solar
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Verify activation
which python  # Should point to venv/bin/python
```

### 3. Install Dependencies

```bash
# Upgrade pip and setuptools
pip install --upgrade pip setuptools wheel

# Install project dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"
```

### 4. Configure the Application

```bash
# Copy example environment file
cp environment.example.yaml environment.yaml

# Edit environment settings
nano environment.yaml  # Set production: false for development

# Review main configuration
nano config.yaml  # Adjust settings as needed
```

## 💻 Development Environment

### IDE Setup

#### VS Code

1. Install Python extension
2. Select interpreter: `Ctrl+Shift+P` → "Python: Select Interpreter" → Choose venv
3. Configure settings:

   ```json
   {
     "python.linting.enabled": true,
     "python.linting.flake8Enabled": true,
     "python.formatting.provider": "black",
     "editor.formatOnSave": true,
     "python.testing.pytestEnabled": true
   }
   ```

#### PyCharm

1. Open project
2. Configure interpreter: Settings → Project → Python Interpreter → Add → Existing Environment
3. Enable inspections: Settings → Editor → Inspections → Python

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
EOF

# Install hooks
pre-commit install
```

## 🏃 Running the Application

### Development Mode (Simulated Hardware)

```bash
# Ensure environment.yaml has production: false
python src/main.py
```

### Production Mode (Real Hardware)

```bash
# Ensure environment.yaml has production: true
# Must be run on Raspberry Pi with hardware connected
sudo python src/main.py  # May need sudo for GPIO access
```

### Running Examples

```bash
# Threaded runner demo
python src/examples/threaded_runner_demo.py

# Power monitor demo
python src/examples/power_monitor_demo.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
# Open htmlcov/index.html to view coverage report

# Run specific test
pytest tests/test_base_runner.py -v

# Run tests matching pattern
pytest -k "test_runner"
```

## 🔄 Development Workflow

### 1. Code Style Checks

```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Check style with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/

# All checks at once
make lint  # If Makefile is available
```

### 2. Configuration Validation

```bash
# Validate configuration files
python -c "from src.config_validator import validate_configuration_files; from pathlib import Path; validate_configuration_files(Path('config.yaml'), Path('environment.yaml'))"
```

### 3. Running in Debug Mode

```bash
# Set debug logging in config.yaml
# logging:
#   level: "DEBUG"

# Or set via environment variable
export SOLAR_LOG_LEVEL=DEBUG
python src/main.py
```

## 🔧 Hardware Testing

### I2C Setup (Raspberry Pi)

```bash
# Enable I2C
sudo raspi-config
# Navigate to: Interfacing Options → I2C → Enable

# Install I2C tools
sudo apt-get update
sudo apt-get install -y i2c-tools

# Verify I2C devices
sudo i2cdetect -y 1
# Should show device at address 0x40 (INA219)
```

### GPIO Permissions

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Logout and login for changes to take effect
```

### Hardware Connections

```
INA219 → Raspberry Pi
VCC    → 3.3V (Pin 1)
GND    → GND (Pin 6)
SDA    → SDA (Pin 3)
SCL    → SCL (Pin 5)
```

## 🐛 Debugging

### Enable Verbose Logging

```python
# In your code
import logging
logging.getLogger("src.runners").setLevel(logging.DEBUG)
```

### Remote Debugging (VS Code)

1. Install debugpy:

   ```bash
   pip install debugpy
   ```

2. Add to your code:

   ```python
   import debugpy
   debugpy.listen(5678)
   debugpy.wait_for_client()
   ```

3. Configure VS Code launch.json:

   ```json
   {
     "name": "Attach to Remote",
     "type": "python",
     "request": "attach",
     "connect": {
       "host": "raspberrypi.local",
       "port": 5678
     }
   }
   ```

### Common Issues

#### ImportError in Tests

```bash
# Ensure src is in Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

#### GPIO Permission Denied

```bash
# Run with sudo or add user to gpio group
sudo python src/main.py
```

#### I2C Device Not Found

```bash
# Check connections and I2C is enabled
sudo i2cdetect -y 1
```

## 📊 Performance Profiling

### CPU Profiling

```python
# Add to main.py
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Run with memory profiling
mprof run python src/main.py
mprof plot  # Generate graph
```

### Thread Monitoring

```python
# Add to your code
import threading

def print_thread_info():
    for thread in threading.enumerate():
        print(f"Thread: {thread.name}, Alive: {thread.is_alive()}")

# Call periodically
print_thread_info()
```

## 🚀 Advanced Topics

### Running with Docker

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "src/main.py"]
```

```bash
# Build and run
docker build -t solar-robot .
docker run -it solar-robot
```

### Continuous Integration

The project uses GitHub Actions for CI/CD. See `.github/workflows/python-ci.yml` for configuration.

### Performance Tips

1. **Adjust measurement intervals** in config.yaml to reduce CPU usage
2. **Use production mode** only when hardware is available
3. **Disable unnecessary runners** to save resources
4. **Monitor thread count** to ensure no thread leaks

## 📚 Additional Resources

- [Raspberry Pi GPIO Documentation](https://www.raspberrypi.org/documentation/usage/gpio/)
- [I2C Tutorial](https://learn.sparkfun.com/tutorials/i2c)
- [Python Threading Guide](https://realpython.com/intro-to-python-threading/)
- [INA219 Datasheet](https://www.ti.com/product/INA219)

---

For more information, see the [main README](README.md) or check the [contributing guidelines](CONTRIBUTING.md).
