import logging  # Added logging
import sched  # Added sched for time-based events
import time as time_module  # Renamed to avoid conflict
from datetime import datetime
from datetime import time as datetime_time
from pathlib import Path

import py_trees
import yaml

# Placeholder for actual behavior implementations
# These will be moved to separate files later


class TimeCondition(py_trees.behaviour.Behaviour):
    def __init__(self, time_str: str, name: str = "TimeCondition"):
        """
        Initialize a time condition that checks if current time has reached or passed the target time.

        Args:
            time_str: Target time in HH:MM format
            name: Name of the behavior node
        """
        super(TimeCondition, self).__init__(name)
        self.target_time_str = time_str
        self.target_time: datetime_time | None = None
        try:
            # Parse the time string to ensure it's valid
            parsed_time = datetime.strptime(time_str, "%H:%M")
            self.target_time = parsed_time.time()
            self.logger.debug(f"TimeCondition initialized for {time_str}")
        except ValueError as e:
            self.logger.error(f"Invalid time format {time_str}: {e}")

    def update(self) -> py_trees.common.Status:
        if self.target_time is None:
            self.logger.error("Invalid target time")
            return py_trees.common.Status.FAILURE

        current_time = datetime.now().time()

        # Compare times
        if current_time >= self.target_time:
            self.logger.debug(f"TimeCondition met: {self.target_time_str}")
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING


class TimeRangeCondition(py_trees.behaviour.Behaviour):
    def __init__(
        self, start_time: str, end_time: str, name: str = "TimeRangeCondition"
    ):
        """
        Initialize a time range condition that checks if current time is within a specified range.

        Args:
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format
            name: Name of the behavior node
        """
        super(TimeRangeCondition, self).__init__(name)
        self.start_time_str = start_time
        self.end_time_str = end_time
        self.start_time: datetime_time | None = None
        self.end_time: datetime_time | None = None
        try:
            # Parse the time strings to ensure they're valid
            start_parsed = datetime.strptime(start_time, "%H:%M")
            end_parsed = datetime.strptime(end_time, "%H:%M")
            self.start_time = start_parsed.time()
            self.end_time = end_parsed.time()
            self.logger.debug(
                f"TimeRangeCondition initialized for {start_time}-{end_time}"
            )
        except ValueError as e:
            self.logger.error(f"Invalid time format: {e}")

    def update(self) -> py_trees.common.Status:
        if self.start_time is None or self.end_time is None:
            self.logger.error("Invalid time range")
            return py_trees.common.Status.FAILURE

        current_time = datetime.now().time()

        # Handle case where range crosses midnight
        if self.start_time > self.end_time:
            # Range crosses midnight, so we check if current time is either:
            # 1. After start time OR
            # 2. Before end time
            if current_time >= self.start_time or current_time <= self.end_time:
                self.logger.debug(
                    f"TimeRangeCondition met: {self.start_time_str}-{self.end_time_str}"
                )
                return py_trees.common.Status.SUCCESS
        else:
            # Normal range within same day
            if self.start_time <= current_time <= self.end_time:
                self.logger.debug(
                    f"TimeRangeCondition met: {self.start_time_str}-{self.end_time_str}"
                )
                return py_trees.common.Status.SUCCESS

        return py_trees.common.Status.RUNNING


class BatterySafetyCondition(py_trees.behaviour.Behaviour):
    def __init__(
        self,
        min_battery_threshold: float = 20.0,
        max_distance_factor: float = 0.5,
        name: str = "BatterySafetyCondition",
    ):
        """
        Initialize the battery safety condition.

        Args:
            min_battery_threshold: Minimum battery percentage before considering charging
            max_distance_factor: Maximum allowed distance from dock as a factor of remaining battery
                               (e.g. 0.5 means at 50% battery, max distance is 25% of total range)
            name: Name of the behavior node
        """
        super(BatterySafetyCondition, self).__init__(name)
        self.min_battery_threshold = min_battery_threshold
        self.max_distance_factor = max_distance_factor
        self.blackboard = self.attach_blackboard_client(name="SOLAR_BT_Engine")
        self.blackboard.register_key(
            "battery_level", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key("position", access=py_trees.common.Access.READ)
        self.blackboard.register_key("locations", access=py_trees.common.Access.READ)
        self.logger.debug(
            f"BatterySafetyCondition initialized with threshold {min_battery_threshold}% and distance factor {max_distance_factor}"
        )

    def _calculate_distance(self, pos1: dict, pos2: dict) -> float:
        """Calculate Euclidean distance between two positions."""
        return ((pos1["x"] - pos2["x"]) ** 2 + (pos1["y"] - pos2["y"]) ** 2) ** 0.5

    def update(self) -> py_trees.common.Status:
        try:
            # Get current battery level and position
            battery_level = self.blackboard.battery_level
            current_pos = self.blackboard.position
            locations = self.blackboard.locations

            if not all([battery_level is not None, current_pos, locations]):
                self.logger.warning(
                    "Missing required blackboard data for battery safety check"
                )
                return py_trees.common.Status.FAILURE

            # If battery is below minimum threshold, need to charge
            if battery_level <= self.min_battery_threshold:
                self.logger.warning(
                    f"Battery level {battery_level}% below minimum threshold {self.min_battery_threshold}%"
                )
                return py_trees.common.Status.SUCCESS

            # Calculate distance to dock
            if "Dock" not in locations:
                self.logger.error("Dock location not found in locations")
                return py_trees.common.Status.FAILURE

            dock_pos = locations["Dock"]
            distance_to_dock = self._calculate_distance(current_pos, dock_pos)

            # Calculate maximum allowed distance based on battery level
            # As battery decreases, max allowed distance decreases proportionally
            max_allowed_distance = (battery_level / 100.0) * self.max_distance_factor

            if distance_to_dock > max_allowed_distance:
                self.logger.warning(
                    f"Distance to dock ({distance_to_dock:.2f}) exceeds maximum allowed "
                    f"({max_allowed_distance:.2f}) for current battery level {battery_level}%"
                )
                return py_trees.common.Status.SUCCESS

            return py_trees.common.Status.FAILURE

        except Exception as e:
            self.logger.error(f"Error in battery safety check: {e}")
            return py_trees.common.Status.FAILURE


class NavigateToTarget(py_trees.behaviour.Behaviour):
    def __init__(self, target_name: str, name: str = "NavigateToTarget"):
        super(NavigateToTarget, self).__init__(name)
        self.target_name = target_name
        self.blackboard = self.attach_blackboard_client(name="SOLAR_BT_Engine")
        self.blackboard.register_key("position", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(
            key="locations", access=py_trees.common.Access.READ
        )
        self.logger.debug(f"[{self.name}] initialized for target: {target_name}")
        self._target_coords = None

    def setup(self, **kwargs) -> None:
        self.logger.debug(f"[{self.name}] - setup() called.")
        try:
            # Ensure blackboard client is valid and has data
            if not self.blackboard.exists("locations"):
                self.logger.error(
                    f"[{self.name}] - 'locations' key does not exist on blackboard during setup."
                )
                self._target_coords = None
                return

            locations = self.blackboard.locations
            self.logger.debug(
                f"[{self.name}] - Accessed blackboard.locations: {locations}"
            )
            if self.target_name in locations:
                self._target_coords = locations[self.target_name]
                self.logger.debug(
                    f"[{self.name}] - Target '{self.target_name}' coordinates set to: {self._target_coords}"
                )
            else:
                self.logger.error(
                    f"[{self.name}] - Target '{self.target_name}' not found in locations: {list(locations.keys())}"
                )
                self._target_coords = None
        except AttributeError as ae:
            self.logger.error(
                f"[{self.name}] - AttributeError: 'locations' not found on blackboard or blackboard issue during setup: {ae}"
            )
            self._target_coords = None
        except Exception as e:
            self.logger.error(f"[{self.name}] - Unexpected error during setup: {e}")
            self._target_coords = None
        self.logger.debug(
            f"[{self.name}] - setup() finished. Target coords: {self._target_coords}"
        )

    def update(self) -> py_trees.common.Status:
        self.logger.debug(
            f"[{self.name}] - update() called. Current target_coords: {self._target_coords}"
        )
        if self._target_coords is None:
            self.logger.warning(
                f"[{self.name}] - Target coordinates are None. Returning FAILURE."
            )
            return py_trees.common.Status.FAILURE

        self.logger.info(
            f"[{self.name}] - Navigating to {self.target_name} at {self._target_coords}..."
        )
        # In a real robot, this would involve motion commands and path planning
        # For now, assume it takes some time and then succeeds
        # Update robot's current position on blackboard (simulated)
        self.blackboard.position = self._target_coords
        self.logger.info(f"[{self.name}] - Arrived at {self.target_name}")
        return py_trees.common.Status.SUCCESS


def create_action_node(action_name: str) -> py_trees.behaviour.Behaviour:
    # Placeholder for creating action nodes
    # These would be specific behaviors like "water", "soil_check"
    class GenericAction(py_trees.behaviour.Behaviour):
        def __init__(self, name: str):
            super(GenericAction, self).__init__(name)
            self.logger.debug(f"GenericAction {name} initialized")

        def update(self) -> py_trees.common.Status:
            self.logger.info(f"Executing action: {self.name}")
            # Simulate action execution
            return py_trees.common.Status.SUCCESS

    return GenericAction(name=action_name)


class BehaviorTreeEngine:
    def __init__(self, config: dict, production: bool):
        self.config = config
        self.production = production
        self.logger = logging.getLogger(__name__)
        self.tree: py_trees.trees.BehaviourTree | None = None

        # Get battery safety configuration
        battery_safety_config = config.get("application", {}).get("battery_safety", {})
        self.min_battery_threshold = battery_safety_config.get(
            "min_battery_threshold", 20.0
        )
        self.max_distance_factor = battery_safety_config.get("max_distance_factor", 0.5)

        self.logger.debug(
            f"Battery safety configured with min_threshold={self.min_battery_threshold}% "
            f"and max_distance_factor={self.max_distance_factor}"
        )

        # Blackboard for sharing data between behaviors
        self.blackboard = py_trees.blackboard.Client(name="SOLAR_BT_Engine")
        self.blackboard.register_key(
            key="position", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="battery_level", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="current_time", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="locations", access=py_trees.common.Access.WRITE
        )

        # Initialize some blackboard values
        self.blackboard.position = {"x": 0, "y": 0}  # Initial position (Dock)
        self.blackboard.battery_level = 100.0

        # Scheduler for time-based events (not fully integrated with BT yet)
        self.scheduler = sched.scheduler(time_module.time, time_module.sleep)

        self.logger.debug("BehaviorTreeEngine initialized")

    def _load_yaml_config(self, file_name: str) -> dict:
        config_path = (
            Path(SCRIPT_DIR) / "bt_config" / file_name
        )  # Assuming SCRIPT_DIR is defined in main
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"Configuration file {config_path} not found.")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML file {config_path}: {e}")
            return {}

    def setup(self):
        """Load configurations and build the behavior tree."""
        self.logger.info("Setting up Behavior Tree Engine...")

        # Load locations and store on blackboard
        locations = self._load_yaml_config("locations.yaml")
        if not locations:
            self.logger.error(
                "Failed to load locations.yaml. Cannot proceed with BT setup."
            )
            return False  # Indicate failure
        self.blackboard.locations = locations
        self.logger.debug(f"Loaded locations: {locations}")

        schedule_config = self._load_yaml_config("daily_schedule.yaml")
        if not schedule_config or "tasks" not in schedule_config:
            self.logger.error("Failed to load daily_schedule.yaml or no tasks defined.")
            return False  # Indicate failure

        self.tree = self._build_tree_from_schedule(schedule_config["tasks"])
        if self.tree:
            self.logger.info("Behavior tree built successfully.")
            # Call setup() on the tree to initialize all behaviors
            self.tree.setup()
            self.logger.info(
                "\n" + py_trees.display.ascii_tree(self.tree.root, show_status=True)
            )
            return True
        else:
            self.logger.error("Failed to build behavior tree.")
            return False

    def _build_tree_from_schedule(
        self, tasks_config: list
    ) -> py_trees.trees.BehaviourTree | None:
        if not tasks_config:
            self.logger.warning("No tasks provided to build the tree.")
            return None

        # Create a selector as the root to handle high-priority safety checks
        root = py_trees.composites.Selector("Root", memory=True)

        # Create a high-priority sequence for battery safety
        battery_safety = py_trees.composites.Sequence("BatterySafety", memory=True)
        battery_safety.add_child(
            BatterySafetyCondition(
                min_battery_threshold=self.min_battery_threshold,
                max_distance_factor=self.max_distance_factor,
            )
        )
        battery_safety.add_child(
            NavigateToTarget(target_name="Dock", name="EmergencyCharge")
        )
        battery_safety.add_child(create_action_node("charge"))

        # Add battery safety as first child of root selector
        root.add_child(battery_safety)

        # Create the main schedule sequence
        schedule = py_trees.composites.Sequence("DailySchedule", memory=True)
        self.logger.debug(f"Building BT for {len(tasks_config)} tasks.")

        for i, task_config in enumerate(tasks_config):
            task_name = task_config.get("type", f"Task_{i}")
            task_time = task_config.get("time")
            task_time_range = task_config.get("time_range")

            task_sequence = py_trees.composites.Sequence(
                name=f"{task_name}@{task_time or task_time_range or i}", memory=True
            )

            # Handle time-based conditions
            if task_time_range:
                # If task has a time range, use TimeRangeCondition
                start_time, end_time = task_time_range.split("-")
                task_sequence.add_child(
                    TimeRangeCondition(
                        start_time=start_time.strip(),
                        end_time=end_time.strip(),
                        name=f"WaitFor_{start_time}-{end_time}",
                    )
                )
            elif task_time:
                # If task has a specific time, use TimeCondition
                task_sequence.add_child(
                    TimeCondition(time_str=task_time, name=f"WaitFor_{task_time}")
                )

            # Handle navigation tasks
            if task_config.get("type") == "navigation":
                target = task_config.get("target")
                if target:
                    task_sequence.add_child(
                        NavigateToTarget(target_name=target, name=f"GoTo_{target}")
                    )
                else:
                    self.logger.warning(f"Navigation task {task_name} has no target.")

            # Add action nodes
            for action_str in task_config.get("actions", []):
                task_sequence.add_child(create_action_node(action_str))

            if task_sequence.children:  # Only add if it has children
                schedule.add_child(task_sequence)
            else:
                self.logger.warning(
                    f"Task {task_name} resulted in an empty sequence, not adding to tree."
                )

        # Add the main schedule as second child of root selector
        if schedule.children:
            root.add_child(schedule)
        else:
            self.logger.error(
                "Schedule sequence has no children after processing tasks."
            )
            return None

        tree = py_trees.trees.BehaviourTree(root=root)
        return tree

    def tick(self) -> None:
        """Tick the behavior tree and update blackboard."""
        if not self.tree or not self.tree.root:
            self.logger.warning(
                "Behavior tree not initialized or empty, skipping tick."
            )
            return

        # Update current time on blackboard
        self.blackboard.current_time = time_module.time()

        try:
            self.tree.tick()
        except Exception as e:
            self.logger.error(f"Exception during tree tick: {e}", exc_info=True)

    def shutdown(self):
        """Clean up behavior tree resources and scheduler."""
        self.logger.info("Shutting down Behavior Tree Engine...")
        if self.tree and self.tree.root:
            # Potentially add cleanup for behaviors if needed
            # self.tree.interrupt() # if any behavior needs explicit interruption
            pass
        self.scheduler.empty()  # Clear any pending scheduled events
        self.logger.info("Behavior Tree Engine shutdown complete.")


# This SCRIPT_DIR needs to be accessible for _load_yaml_config
# It's usually defined in main.py. We'll assume it's passed or globally available.
# For now, let's define it here for standalone testing, but this should be fixed.
# SCRIPT_DIR = Path(__file__).resolve().parent.parent

# Attempt to use SCRIPT_DIR from main.py, fallback for standalone execution
try:
    from main import SCRIPT_DIR
except ImportError:
    # Fallback for standalone execution or if main.py's SCRIPT_DIR is not available at import time
    SCRIPT_DIR = Path(__file__).resolve().parent.parent
    # print("Warning: Using fallback SCRIPT_DIR in bt_engine.py") # Optional: for debugging

if __name__ == "__main__":
    # Basic test setup for bt_engine.py
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    mock_config: dict = {"application": {}}  # Mock main config

    engine = BehaviorTreeEngine(config=mock_config, production=False)

    if engine.setup():
        logger.info("Engine setup successful. Starting test ticks.")
        try:
            for i in range(20):  # Simulate a few ticks
                logger.info(f"--- Tick {i+1} ---")
                engine.tick()
                if engine.tree is not None and engine.tree.root is not None:
                    print(
                        py_trees.display.ascii_tree(engine.tree.root, show_status=True)
                    )
                    time_module.sleep(1)  # Simulate time passing
                    if engine.tree.root.status == py_trees.common.Status.SUCCESS:
                        logger.info("Behavior tree completed successfully.")
                        break
                    if engine.tree.root.status == py_trees.common.Status.FAILURE:
                        logger.info("Behavior tree failed.")
                        break
        except KeyboardInterrupt:
            logger.info("Test interrupted.")
        finally:
            engine.shutdown()
    else:
        logger.error("Engine setup failed.")
