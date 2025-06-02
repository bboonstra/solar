# Threaded Runner System for SOLAR Robot

## Overview

The SOLAR robot now uses a sophisticated threaded runner system that allows multiple sensor modules to operate concurrently. This system replaces the simple sequential polling approach with a more robust, scalable architecture.

## Architecture

### Core Components

1. **BaseRunner** (`src/runners/base_runner.py`)
   - Abstract base class for all runners
   - Provides thread management, state tracking, error handling
   - Handles graceful startup/shutdown

2. **RunnerManager** (`src/runners/runner_manager.py`)
   - Central coordinator for all runners
   - Handles auto-registration, lifecycle management
   - Provides system-wide monitoring and status reporting

3. **INA219Runner** (`src/runners/ina219_runner.py`)
   - Concrete implementation for INA219 power monitoring
   - Continuous threaded power readings with statistics
   - Smart alerting for power threshold violations

## Configuration

### Main Configuration (`config.yaml`)

```yaml
# Enable/disable threaded runner system
application:
  threaded_runners: true          # Enable threaded runners
  main_loop_interval: 0.1         # Main loop sleep interval (seconds)
  shutdown_timeout: 5.0           # Graceful shutdown timeout

# Individual sensor configuration
ina219:
  enabled: true                   # Enable/disable this specific sensor
  measurement_interval: 1.0       # Reading interval (seconds)
  # ... other sensor-specific settings
```

### Device Enable/Disable

Each module can be individually enabled or disabled:

```yaml
ina219:
  enabled: true    # Set to false to disable this module
```

When disabled, the module:

- Won't be registered or started
- Consumes no resources
- System continues normally without it

## Key Features

### 1. **Concurrent Operation**

- Multiple sensors run simultaneously in separate threads
- Non-blocking operation - one slow sensor doesn't affect others
- Efficient resource utilization

### 2. **Robust Error Handling**

- Individual runner failures don't crash the system
- Automatic error counting and reporting
- Configurable error recovery strategies

### 3. **Health Monitoring**

- Continuous health checks for all runners
- System-wide health status reporting
- Early detection of sensor issues

### 4. **Graceful Shutdown**

- Signal handling (SIGINT, SIGTERM)
- Coordinated shutdown of all runners
- Configurable timeout for cleanup

### 5. **Comprehensive Status Reporting**

- Real-time status for all runners
- Performance statistics and metrics
- Detailed error information

## Usage Examples

### Basic Usage

```python
from runners import RunnerManager

# Load configuration
config = load_config()

# Create and start runner manager
runner_manager = RunnerManager(config, production=False)

# Start all configured runners
if runner_manager.start():
    # Main application loop
    while runner_manager.is_running:
        # Your application logic here
        time.sleep(1.0)
finally:
    runner_manager.shutdown()
```

### Accessing Specific Runners

```python
# Get the INA219 runner
ina219_runner = runner_manager.get_runner("ina219")

if ina219_runner:
    # Get latest power reading
    reading = ina219_runner.get_last_reading()
    print(f"Power: {reading.power:.2f}W")
    
    # Get power statistics
    stats = ina219_runner.get_power_stats()
    print(f"Average Power: {stats.avg_power:.2f}W")
```

### Status Monitoring

```python
# Get system status
system_status = runner_manager.get_system_status()
print(f"Running: {system_status.running_runners}/{system_status.total_runners}")

# Print detailed status report
runner_manager.print_status_report()

# Check overall system health
if runner_manager.is_healthy:
    print("All systems operational")
```

## Running the System

### Standard Operation

```bash
# Run the main application
python src/main.py
```

### Demo Scripts

```bash
# Interactive threaded runner demo
python src/examples/threaded_runner_demo.py

# Original power monitor demo (legacy)
python src/examples/power_monitor_demo.py
```

## Adding New Runners

To add a new sensor or module runner:

### 1. Create Runner Class

```python
# src/runners/my_sensor_runner.py
from .base_runner import BaseRunner

class MySensorRunner(BaseRunner):
    def __init__(self, config, production=False):
        sensor_config = config.get("my_sensor", {})
        super().__init__("MySensor", sensor_config, production)
        # Initialize sensor-specific settings
    
    def _initialize(self) -> bool:
        # Initialize your sensor hardware/simulation
        return True
    
    def _work_cycle(self) -> None:
        # Perform one measurement cycle
        pass
    
    def is_healthy(self) -> bool:
        # Check if sensor is responding correctly
        return True
```

### 2. Register in RunnerManager

```python
# In src/runners/runner_manager.py
self._runner_classes = {
    "ina219": INA219Runner,
    "my_sensor": MySensorRunner,  # Add your runner here
}
```

### 3. Add Configuration

```yaml
# In config.yaml
my_sensor:
  enabled: true
  measurement_interval: 2.0
  # Add sensor-specific configuration
```

### 4. Update Exports

```python
# In src/runners/__init__.py
from .my_sensor_runner import MySensorRunner

__all__ = ["BaseRunner", "INA219Runner", "MySensorRunner", "RunnerManager"]
```

## Performance Considerations

### Thread Safety

- All runners operate in separate threads
- Use thread-safe operations for shared data
- BaseRunner provides thread-safe state management

### Resource Usage

- Each runner consumes minimal resources when idle
- Configurable measurement intervals prevent excessive CPU usage
- Automatic cleanup on shutdown

### Scalability

- System easily scales to support many concurrent sensors
- Modular architecture allows independent development
- Configuration-driven runner registration

## Migration from Legacy Mode

The system maintains backward compatibility:

1. **Enable threaded runners**:

   ```yaml
   application:
     threaded_runners: true
   ```

2. **Disable for legacy mode**:

   ```yaml
   application:
     threaded_runners: false
   ```

3. **Legacy mode** runs the old sequential approach for compatibility

## Troubleshooting

### Common Issues

1. **Runner fails to start**
   - Check sensor hardware connections (production mode)
   - Verify configuration settings
   - Check logs for initialization errors

2. **High error counts**
   - Sensor hardware issues
   - Incorrect I2C addresses or pins
   - Network connectivity problems

3. **Performance issues**
   - Reduce measurement intervals
   - Check system resource usage
   - Review error logs for bottlenecks

### Debug Mode

Enable debug logging:

```yaml
logging:
  level: "DEBUG"
```

This provides detailed information about:

- Runner state transitions
- Thread lifecycle events
- Sensor communication details
- Error context and stack traces

## Future Enhancements

The threaded runner system is designed for extensibility:

- **Web API**: REST/WebSocket interfaces for remote monitoring
- **Data Persistence**: Automatic logging to databases
- **Alert System**: Email/SMS notifications for critical events
- **Load Balancing**: Dynamic runner distribution
- **Hot-swapping**: Runtime configuration updates without restart
