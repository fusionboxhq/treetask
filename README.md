# TreeTask

[![Tests](https://github.com/fusionboxhq/treetask/actions/workflows/tests.yml/badge.svg)](https://github.com/fusionboxhq/treetask/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/fusionboxhq/treetask/branch/main/graph/badge.svg)](https://codecov.io/gh/fusionboxhq/treetask)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python package for hierarchical parallel task execution with live tree progress display.

## Features

### Core Features
- **Arbitrary nesting depth** - Support any level of task hierarchy
- **Granular parallelism control** - Configure parallel or sequential execution per node
- **Dynamic tree structure** - Add child nodes during execution
- **Live terminal display** - Real-time progress with ANSI cursor control
- **Progress tracking** - Accurate stats even with dynamically changing trees

### Execution Control
- **Timeout support** - Global and per-task timeouts
- **Cancellation** - Cancel running tasks with optional reason
- **Pause/Resume** - Pause execution and resume later
- **Max concurrency limit** - Control parallel task execution with semaphores

### Retry & Recovery
- **Retry strategies** - Built-in exponential backoff, fixed delay, linear backoff, or custom
- **Per-node retry config** - Override global retry settings per task
- **Resume from checkpoint** - Skip completed nodes when resuming

### Advanced Patterns
- **Dependencies/DAG** - Define task dependencies with cycle detection
- **Conditional execution** - Skip or run tasks based on conditions
- **Result aggregation** - Collect and aggregate task results

### Observability
- **Execution timing** - Track start/end times and elapsed duration
- **ETA estimation** - Calculate remaining time based on completed tasks
- **Extended hooks** - Events for retry, timeout, cancel, skip, dependencies
- **Logging integration** - Structured logging with TreeTaskLogger
- **Serialization** - Save/restore tree state to JSON

## Installation

```bash
pip install git+https://github.com/fusionboxhq/treetask.git
```

## Quick Start

```python
import anyio
from treetask import TreeBuilder, AsyncExecutor, TreeRenderer, LiveDisplay, TreeTaskConfig

async def my_task(node):
    """Task functions receive the node and can update progress."""
    await anyio.sleep(1)
    node.progress = (1, 1)  # (current, total)
    return {"result": "done"}  # Optional: merged into node.data

# Build a task tree
tree = (
    TreeBuilder("pipeline", name="My Pipeline")
    .add_node("phase1", name="Phase 1", parallel=True)
        .add_child("task1", name="Task 1", task=my_task)
        .add_child("task2", name="Task 2", task=my_task)
    .up()
    .add_node("phase2", name="Phase 2", parallel=False)  # Sequential
        .add_child("task3", name="Task 3", task=my_task)
        .add_child("task4", name="Task 4", task=my_task)
    .build()
)

# Execute with live display
config = TreeTaskConfig(default_max_depth=2)
display = LiveDisplay(TreeRenderer(config), config)

async def run():
    executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
    with display:
        await executor.run()
    display.finalize(tree)

anyio.run(run)
```

### Output

During execution:
```
🔄 My Pipeline
├── 🔄 Phase 1
│   ├── ✅ Task 1
│   └── 🔄 Task 2
└── ⏳ Phase 2

Progress: 1/4 (25%)
```

After completion:
```
✅ My Pipeline
├── ✅ Phase 1
│   ├── ✅ Task 1
│   └── ✅ Task 2
└── ✅ Phase 2
    ├── ✅ Task 3
    └── ✅ Task 4

Progress: 4/4 (100%)
```

## Usage Guide

### Building Trees with TreeBuilder

The `TreeBuilder` provides a fluent API for constructing task trees:

```python
from treetask import TreeBuilder

tree = (
    TreeBuilder("root", name="Root Node")
    # add_node: adds a child AND moves into it
    .add_node("level1", name="Level 1", parallel=True)
        # add_child: adds a child but stays at current level
        .add_child("task_a", name="Task A", task=some_task)
        .add_child("task_b", name="Task B", task=some_task)
        # Nested level
        .add_node("sublevel", name="Sub Level")
            .add_child("task_c", name="Task C", task=some_task)
        .up()  # Back to level1
    .up()  # Back to root
    .add_node("level2", name="Level 2", parallel=False)
        .add_child("task_d", name="Task D", task=some_task)
    .build()
)
```

Key methods:
- `add_node(id, name, parallel, task, data)` - Add child and move into it
- `add_child(id, name, parallel, task, data)` - Add child, stay at current level
- `up()` - Move back to parent
- `build()` - Return the completed TaskTree

### Task Functions

Task functions are async functions that receive the node as their argument:

```python
async def my_task(node):
    """
    Args:
        node: TaskNode instance with access to:
            - node.id: Unique identifier
            - node.name: Display name
            - node.data: User payload dict
            - node.progress: Tuple (current, total)
            - node.children: Child nodes list
            - node.add_child(): Method to add children dynamically

    Returns:
        Optional dict that gets merged into node.data
    """
    # Access input data
    item = node.data.get("item")

    # Do work...
    result = await process(item)

    # Update progress
    node.progress = (1, 1)

    # Return data (optional, merged into node.data)
    return {"output": result}
```

### Parallel vs Sequential Execution

Control execution order with the `parallel` flag:

```python
# Parallel: all children run concurrently
.add_node("parallel_phase", name="Parallel Phase", parallel=True)
    .add_child("task1", task=my_task)  # These run
    .add_child("task2", task=my_task)  # at the
    .add_child("task3", task=my_task)  # same time
.up()

# Sequential: children run one after another
.add_node("sequential_phase", name="Sequential Phase", parallel=False)
    .add_child("step1", task=my_task)  # Runs first
    .add_child("step2", task=my_task)  # Then this
    .add_child("step3", task=my_task)  # Then this
.up()
```

### Timeouts

Set timeouts at global or per-task level:

```python
from treetask import TreeTaskConfig, TreeBuilder

# Global timeout for entire tree execution
config = TreeTaskConfig(global_timeout=300.0)  # 5 minutes

# Default timeout for each task
config = TreeTaskConfig(default_task_timeout=30.0)  # 30 seconds per task

# Per-task timeout (overrides global)
tree = (
    TreeBuilder("root", name="Root")
    .add_child("fast_task", task=fast_fn)
        .set_timeout(5.0)  # 5 second timeout
    .add_child("slow_task", task=slow_fn)
        .set_timeout(120.0)  # 2 minute timeout
    .build()
)
```

When a task times out, its status becomes `"timed_out"` and the `on_timeout` hook is called.

### Cancellation

Cancel running tasks programmatically:

```python
import anyio

async def run_with_cancel():
    executor = AsyncExecutor(tree)

    async def cancel_after_delay():
        await anyio.sleep(5)
        executor.cancel(reason="User requested cancellation")

    async with anyio.create_task_group() as tg:
        tg.start_soon(cancel_after_delay)
        try:
            await executor.run()
        except anyio.get_cancelled_exc_class():
            print("Execution was cancelled")

    # Check cancellation status
    print(f"Cancelled: {executor.is_cancelled}")
```

Cancelled tasks have status `"cancelled"` and the `on_cancel` hook is called with the reason.

### Pause and Resume

Pause execution and resume later:

```python
async def run_with_pause():
    executor = AsyncExecutor(tree)

    async def pause_controller():
        await anyio.sleep(2)
        executor.pause()
        print("Paused - no new tasks will start")
        await anyio.sleep(5)
        executor.resume()
        print("Resumed")

    async with anyio.create_task_group() as tg:
        tg.start_soon(pause_controller)
        await executor.run()
```

Note: Pause only affects new tasks; already running tasks will complete.

### Concurrency Limits

Limit how many tasks run in parallel:

```python
config = TreeTaskConfig(max_concurrency=5)  # Max 5 concurrent tasks
tree = TaskTree(root, config)
executor = AsyncExecutor(tree)
```

### Retry Strategies

Choose from built-in retry strategies or create custom ones:

```python
from treetask import (
    TreeTaskConfig,
    FixedDelayRetry,
    ExponentialBackoffRetry,
    LinearBackoffRetry,
    CustomRetry,
    RetryOnExceptionTypes,
)

# Fixed delay between retries
strategy = FixedDelayRetry(delay=1.0, max_retries=3)

# Exponential backoff (1s, 2s, 4s, 8s... capped at 60s)
strategy = ExponentialBackoffRetry(
    base_delay=1.0,
    max_delay=60.0,
    multiplier=2.0,
    max_retries=5,
    jitter=True,  # Add randomness to avoid thundering herd
)

# Linear backoff (1s, 2s, 3s, 4s...)
strategy = LinearBackoffRetry(
    initial_delay=1.0,
    increment=1.0,
    max_delay=30.0,
    max_retries=5,
)

# Custom retry logic
strategy = CustomRetry(
    func=lambda attempt, error: 2.0 if attempt < 3 else None
)

# Only retry specific exceptions
strategy = RetryOnExceptionTypes(
    base_strategy=ExponentialBackoffRetry(),
    retry_types=(ConnectionError, TimeoutError),
    never_retry_types=(ValueError, KeyError),
)

# Apply globally
config = TreeTaskConfig(default_retry_strategy=strategy)
```

### Per-Node Retry Configuration

Override retry settings for specific tasks:

```python
tree = (
    TreeBuilder("root", name="Root")
    # Use global retry strategy
    .add_child("task1", task=normal_task)

    # Custom max retries for this task
    .add_child("task2", task=flaky_task)
        .set_max_retries(10)

    # Custom strategy for this task
    .add_child("task3", task=critical_task)
        .set_retry_strategy(ExponentialBackoffRetry(max_retries=5))

    .build()
)
```

### Dependencies (DAG Support)

Define task dependencies for complex workflows:

```python
tree = (
    TreeBuilder("pipeline", name="Data Pipeline")
    .add_child("fetch", name="Fetch Data", task=fetch_data)
    .add_child("validate", name="Validate", task=validate)
        .depends_on("fetch")  # Must wait for fetch
    .add_child("transform", name="Transform", task=transform)
        .depends_on("fetch")  # Can run parallel with validate
    .add_child("load", name="Load", task=load)
        .depends_on("validate", "transform")  # Waits for both
    .build()
)
```

The executor automatically resolves dependencies and detects cycles:

```python
from treetask import DependencyResolver, CyclicDependencyError

resolver = DependencyResolver(tree)

# Check for cycles before execution
cycles = resolver.detect_cycles()
if cycles:
    print(f"Circular dependencies detected: {cycles}")

# Get execution order
for node in resolver.topological_order():
    print(f"Execute: {node.name}")

# Get parallelizable levels
levels = resolver.get_execution_levels()
for i, level in enumerate(levels):
    print(f"Level {i}: {[n.name for n in level]}")
```

### Conditional Execution

Skip tasks based on conditions:

```python
tree = (
    TreeBuilder("pipeline", name="Pipeline")

    # Skip if condition returns True
    .add_child("optional", task=optional_task)
        .set_skip_condition(lambda node: node.data.get("skip_optional", False))

    # Only run if condition returns True
    .add_child("conditional", task=conditional_task)
        .set_run_condition(lambda node: node.data.get("should_run", True))

    .build()
)
```

Skipped tasks have status `"skipped"` and the `on_skip` hook is called.

### Result Aggregation

Collect results from all tasks:

```python
async def task_with_result(node):
    return {"value": node.data.get("input", 0) * 2}

# After execution
results = tree.collect_results()
# {"task1": {"value": 2}, "task2": {"value": 4}, ...}

# Aggregate with custom reducer
total = tree.aggregate_results(
    reducer=lambda acc, result: acc + result.get("value", 0),
    initial=0,
)
```

### Serialization and Checkpointing

Save tree state to JSON and restore later:

```python
from treetask import TreeSerializer, create_task_registry

# Save current state
json_str = TreeSerializer.tree_to_json(tree)

# ... later, restore state
# Create registry mapping node IDs to task functions
registry = create_task_registry(
    ("fetch", fetch_data),
    ("validate", validate),
    ("transform", transform),
    ("load", load),
)

restored_tree = TreeSerializer.tree_from_json(json_str, task_registry=registry)

# Resume execution, skipping completed nodes
executor = AsyncExecutor(restored_tree, skip_completed=True)
await executor.run()
```

### Execution Timing

Track timing for each task:

```python
async def run():
    executor = AsyncExecutor(tree)
    await executor.run()

    for node in tree.walk():
        if node.task_fn:
            print(f"{node.name}: {node.elapsed:.2f}s")

    # Get timing statistics
    stats = tree.get_timing_stats()
    print(f"Total duration: {stats['total_duration']:.2f}s")
    print(f"Average task time: {stats['average_duration']:.2f}s")
```

### ETA Estimation

Get estimated time remaining:

```python
from treetask import ExecutionContext
from treetask.timing import format_eta, format_progress_with_eta

context = ExecutionContext()

async def on_node_complete(node):
    if node.elapsed:
        context.record_completion(node.elapsed)

    pending = sum(1 for n in tree.walk() if n.status == "pending")
    eta = context.estimate_remaining_time(pending)
    print(f"ETA: {format_duration(eta)}")

# Or use the formatting helpers
stats = tree.get_progress_stats()
print(format_progress_with_eta(
    stats["current"],
    stats["total"],
    elapsed=context.elapsed,
    show_eta=True,
))
# Output: "15/100 (15%) - ETA: 2m 30s"
```

For more advanced ETA calculations, use `TimingStats`:

```python
from treetask import TimingStats

stats = TimingStats()
stats.start()

# Record task durations as they complete
stats.record(1.5)  # Task took 1.5s
stats.record(2.0)  # Task took 2.0s
stats.record(1.8)

# Get ETA using different methods
eta_avg = stats.estimate_remaining(pending_count=10, method="average")
eta_moving = stats.estimate_remaining(pending_count=10, method="moving_average")
eta_median = stats.estimate_remaining(pending_count=10, method="median")

# Get all stats
all_stats = stats.get_stats()
# {"count": 3, "average": 1.77, "median": 1.8, "min": 1.5, "max": 2.0, ...}
```

### Hooks System

Subscribe to execution events:

```python
from treetask import HookDispatcher, AsyncExecutor

hooks = HookDispatcher()

# Register callbacks for events
hooks.on("on_tree_start", lambda tree: print("Starting execution"))
hooks.on("on_tree_complete", lambda tree: print("Execution complete"))
hooks.on("on_node_start", lambda node: print(f"Starting: {node.name}"))
hooks.on("on_node_complete", lambda node: print(f"Complete: {node.name}"))
hooks.on("on_retry", lambda node, attempt, error: print(f"Retry {attempt}: {error}"))
hooks.on("on_timeout", lambda node: print(f"Timeout: {node.name}"))
hooks.on("on_cancel", lambda node, reason: print(f"Cancelled: {reason}"))
hooks.on("on_skip", lambda node, reason: print(f"Skipped: {reason}"))
hooks.on("on_error", lambda node, error: print(f"Error: {error}"))
hooks.on("on_dependency_ready", lambda node: print(f"Dependencies ready: {node.name}"))

executor = AsyncExecutor(tree, hooks=hooks)
await executor.run()
```

You can also implement the `TaskHooks` protocol for type-safe hooks:

```python
from treetask.hooks import TaskHooks

class MyHooks(TaskHooks):
    def on_node_start(self, node):
        print(f"Starting: {node.name}")

    def on_node_complete(self, node):
        print(f"Complete: {node.name}")

    def on_retry(self, node, attempt, error):
        print(f"Retry {attempt}")

hooks = HookDispatcher()
hooks.register(MyHooks())
```

### Logging Integration

Use structured logging:

```python
from treetask import TreeTaskLogger, HookDispatcher, AsyncExecutor
import logging

# Configure Python logging
logging.basicConfig(level=logging.INFO)

# Create logger that emits structured logs
logger = TreeTaskLogger(
    logger_name="myapp.tasks",
    level="INFO",
    include_data=True,  # Include node.data in logs
)

# Register with hooks
hooks = HookDispatcher()
hooks.register(logger)

executor = AsyncExecutor(tree, hooks=hooks)
await executor.run()
```

Or enable logging via config:

```python
config = TreeTaskConfig(
    enable_logging=True,
    log_level="DEBUG",
)
```

For quick debugging, use `create_logging_hooks`:

```python
import logging
from treetask import create_logging_hooks, AsyncExecutor

logger = logging.getLogger("debug")
hooks = create_logging_hooks(logger)

executor = AsyncExecutor(tree, hooks=hooks)
```

For structured log output with extra fields, use `StructuredFormatter`:

```python
from treetask import StructuredFormatter, configure_treetask_logging

# Quick setup
logger = configure_treetask_logging(level="DEBUG", structured=True)

# Or manual setup
handler = logging.StreamHandler()
handler.setFormatter(StructuredFormatter("%(asctime)s %(levelname)s: %(message)s"))
logging.getLogger("treetask").addHandler(handler)

# Output: 2024-01-15 10:30:45 INFO: Node started [node_id=task1 node_name=Fetch depth=1]
```

### Dynamic Tree Structure

Add child nodes during execution when the tree structure isn't known upfront:

```python
from treetask import TaskNode

async def parent_task(node):
    # Fetch data to determine children
    items = await fetch_items()

    # Dynamically add child nodes
    for item in items:
        child = TaskNode(
            id=f"child_{item.id}",
            name=item.name,
            task_fn=process_item,
            progress=(0, item.size),  # Set expected total upfront
            data={"item": item},
        )
        node.add_child(child)

    return {"children_count": len(items)}
```

### Display Configuration

Customize the live display:

```python
config = TreeTaskConfig(
    # Depth control
    default_max_depth=2,   # Show during live updates
    final_max_depth=3,     # Show in final display

    # Update throttling
    refresh_interval=0.1,  # Min seconds between updates

    # Custom icons
    icons={
        "pending": "⏳",
        "working": "🔄",
        "done": "✅",
        "failed": "❌",
        "retrying": "🔁",
        "cancelled": "🚫",
        "skipped": "⏭️",
        "timed_out": "⏱️",
    },

    # Custom tree characters
    tree_chars={
        "branch": "├── ",
        "last_branch": "└── ",
        "vertical": "│   ",
        "empty": "    ",
    },
)
```

## API Reference

### TaskNode

Represents a node in the task tree.

```python
@dataclass
class TaskNode:
    id: str                           # Unique identifier
    name: str                         # Display name
    status: str = "pending"           # pending, working, done, failed, retrying,
                                      # cancelled, skipped, timed_out
    children: list[TaskNode]          # Child nodes
    parent: Optional[TaskNode]        # Parent reference
    data: dict[str, Any]              # User payload
    progress: Optional[tuple[int, int]]  # (current, total)
    retry_count: int = 0              # Current retry attempt
    error: Optional[str] = None       # Error message if failed
    parallel: bool = True             # Run children in parallel?
    task_fn: Optional[Callable]       # Async task function

    # Timing
    start_time: Optional[float]       # Unix timestamp when started
    end_time: Optional[float]         # Unix timestamp when finished
    timeout: Optional[float]          # Per-task timeout in seconds

    # Retry
    max_retries: Optional[int]        # Override global max_retries
    retry_strategy: Optional[RetryStrategy]  # Override global strategy

    # Dependencies & Conditions
    depends_on: list[str]             # IDs of tasks this depends on
    skip_condition: Optional[Callable[[TaskNode], bool]]
    run_condition: Optional[Callable[[TaskNode], bool]]

    # Result
    result: Any                       # Return value from task_fn
```

Properties:
- `elapsed: Optional[float]` - Duration in seconds (end_time - start_time)

Methods:
- `add_child(child: TaskNode)` - Add a child node
- `get_depth() -> int` - Get depth in tree (root = 0)
- `is_leaf() -> bool` - Check if node has no children
- `get_ancestors() -> list[TaskNode]` - Get ancestors from parent to root

### TaskTree

Container for the task tree with traversal and statistics.

```python
class TaskTree:
    root: TaskNode
    config: TreeTaskConfig
```

Methods:
- `find(node_id: str) -> Optional[TaskNode]` - Find node by ID
- `walk(depth_first=True) -> Iterator[TaskNode]` - Iterate all nodes
- `get_stats() -> dict` - Count all nodes by status
- `get_leaf_stats() -> dict` - Count leaf nodes by status
- `get_work_node_stats() -> dict` - Count nodes with task_fn by status
- `get_progress_stats() -> dict` - Aggregate progress tuples
- `register_node(node: TaskNode)` - Register dynamically added node
- `collect_results() -> dict[str, Any]` - Get all node results
- `aggregate_results(reducer, initial) -> Any` - Aggregate results
- `get_failed_nodes() -> list[TaskNode]` - Get nodes with failed/timed_out status
- `get_completed_ids() -> set[str]` - Get IDs of completed nodes
- `get_timing_stats() -> dict` - Get timing statistics
- `reset()` - Reset all nodes to pending status

### TreeBuilder

Fluent API for building task trees.

```python
TreeBuilder(root_id: str, name: str = None, parallel: bool = True, data: dict = None)
```

Methods:
- `add_node(id, name, parallel, task, data)` - Add child and move into it
- `add_child(id, name, parallel, task, data)` - Add child, stay at current level
- `up()` - Move back to parent
- `set_timeout(timeout: float)` - Set timeout for current node
- `set_max_retries(max_retries: int)` - Set max retries for current node
- `set_retry_strategy(strategy: RetryStrategy)` - Set retry strategy
- `depends_on(*node_ids: str)` - Add dependencies for current node
- `set_skip_condition(condition)` - Set skip condition
- `set_run_condition(condition)` - Set run condition
- `build() -> TaskTree` - Return the completed tree

### AsyncExecutor

Executes task trees with configurable parallelism.

```python
AsyncExecutor(
    tree: TaskTree,
    on_update: Callable[[TaskTree], None] = None,
    on_node_start: Callable[[TaskNode], None] = None,
    on_node_complete: Callable[[TaskNode], None] = None,
    hooks: HookDispatcher = None,
    context: ExecutionContext = None,
    skip_completed: bool = False,
)
```

Methods:
- `async run() -> TaskTree` - Execute all tasks and return the tree
- `cancel(reason: str = None)` - Request cancellation
- `pause()` - Pause execution
- `resume()` - Resume execution

Properties:
- `is_cancelled: bool` - Whether execution was cancelled
- `is_paused: bool` - Whether execution is paused

### ExecutionResult

Result container for task tree execution.

```python
class ExecutionResult:
    tree: TaskTree           # The executed tree
    success: bool            # True if no failures or timeouts
    failed_nodes: list       # Nodes that failed
    stats: dict              # Execution statistics

    @property
    def results(self) -> dict[str, Any]  # All node results

    @property
    def timing_stats(self) -> dict       # Timing statistics
```

### ExecutionContext

Shared state for execution control.

```python
ExecutionContext(max_concurrency: int = None)
```

Methods:
- `cancel(reason: str = None)` - Request cancellation
- `pause()` - Pause execution
- `resume()` - Resume execution
- `record_completion(duration: float)` - Record task completion
- `estimate_remaining_time(pending_count: int) -> Optional[float]` - Get ETA
- `get_stats() -> dict` - Get context statistics

Properties:
- `is_cancelled: bool`
- `is_paused: bool`
- `cancel_reason: Optional[str]`
- `active_count: int` - Currently running tasks
- `completed_count: int` - Completed tasks
- `elapsed: Optional[float]` - Total elapsed time

### Retry Strategies

```python
# No retries
NoRetry()

# Fixed delay between retries
FixedDelayRetry(delay: float = 1.0, max_retries: int = 3)

# Exponential backoff
ExponentialBackoffRetry(
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    max_retries: int = 5,
    jitter: bool = True,
)

# Linear backoff
LinearBackoffRetry(
    initial_delay: float = 1.0,
    increment: float = 1.0,
    max_delay: float = 60.0,
    max_retries: int = 5,
)

# Custom logic
CustomRetry(func: Callable[[int, Exception], Optional[float]])

# Filter by exception type
RetryOnExceptionTypes(
    base_strategy: RetryStrategy,
    retry_types: tuple[type[Exception], ...] = (),
    never_retry_types: tuple[type[Exception], ...] = (),
)
```

### HookDispatcher

Event system for execution hooks.

```python
hooks = HookDispatcher()

# Register callbacks
hooks.on(event: str, callback: Callable) -> HookDispatcher

# Register protocol handler
hooks.register(handler: TaskHooks) -> HookDispatcher

# Unregister
hooks.off(event: str, callback: Callable = None)
hooks.unregister(handler: TaskHooks)

# Check handlers
hooks.has_handlers(event: str) -> bool

# Clear all
hooks.clear()
```

Available events:
- `on_tree_start(tree)` - Tree execution starting
- `on_tree_complete(tree)` - Tree execution complete
- `on_node_start(node)` - Node starting
- `on_node_complete(node)` - Node complete
- `on_retry(node, attempt, error)` - Retry attempt
- `on_timeout(node)` - Task timed out
- `on_cancel(node, reason)` - Task cancelled
- `on_skip(node, reason)` - Task skipped
- `on_error(node, error)` - Task error (before retry decision)
- `on_dependency_ready(node)` - All dependencies satisfied
- `on_update()` - Any tree update

### TreeSerializer

Save and restore tree state.

```python
# Serialize
json_str = TreeSerializer.tree_to_json(tree, indent=2)
tree_dict = TreeSerializer.tree_to_dict(tree)

# Deserialize
tree = TreeSerializer.tree_from_json(json_str, task_registry=None)
tree = TreeSerializer.tree_from_dict(data, task_registry=None)

# Node level
node_dict = TreeSerializer.node_to_dict(node)
node = TreeSerializer.dict_to_node(data, task_registry=None)

# Create task registry
registry = create_task_registry(
    ("node_id", task_function),
    ...
)
```

### DependencyResolver

Resolve task dependencies.

```python
resolver = DependencyResolver(tree)

# Get dependencies
deps = resolver.get_dependencies(node_id)  # Set of IDs this depends on
dependents = resolver.get_dependents(node_id)  # Set of IDs that depend on this

# Check if ready to run
is_ready = resolver.is_ready(node_id, completed_ids)

# Get nodes ready to run
ready_nodes = resolver.get_ready_nodes(completed_ids)

# Get execution order
for node in resolver.topological_order():
    ...

# Get parallelizable levels
levels = resolver.get_execution_levels()

# Detect cycles
cycles = resolver.detect_cycles()  # Returns list of cycles

# Validate dependencies
errors = resolver.validate()  # Returns list of error messages
```

### TreeTaskConfig

Configuration dataclass.

```python
@dataclass
class TreeTaskConfig:
    # Display
    default_max_depth: int = 2
    final_max_depth: int = 3
    refresh_interval: float = 0.1
    icons: dict[str, str]
    tree_chars: dict[str, str]

    # Execution
    default_parallel: bool = True
    max_retries: int = 3
    global_timeout: Optional[float] = None
    default_task_timeout: Optional[float] = None
    max_concurrency: Optional[int] = None
    default_retry_strategy: Optional[RetryStrategy] = None

    # Logging
    enable_logging: bool = False
    log_level: str = "INFO"
```

### TimingStats

Track task durations for ETA estimation.

```python
stats = TimingStats()
stats.start()                    # Mark execution start
stats.record(duration)           # Record task duration

# Properties
stats.count                      # Number of recordings
stats.total_duration             # Sum of all durations
stats.elapsed                    # Time since start()
stats.average                    # Average duration
stats.moving_average             # Moving average (last 50)
stats.median                     # Median duration
stats.min_duration               # Minimum duration
stats.max_duration               # Maximum duration

# Methods
stats.estimate_remaining(pending_count, method="moving_average")
stats.get_stats()                # Get all stats as dict
```

### Logging Utilities

```python
# Quick logging setup
from treetask import configure_treetask_logging, StructuredFormatter, create_logging_hooks

# Configure treetask logging
logger = configure_treetask_logging(
    level="INFO",                # Log level
    format_string=None,          # Custom format (optional)
    structured=True,             # Include extra fields
)

# StructuredFormatter - includes extra fields in log output
formatter = StructuredFormatter("%(asctime)s %(levelname)s: %(message)s")
# Output: "2024-01-15 10:30:45 INFO: Node started [node_id=task1 depth=1]"

# create_logging_hooks - quick debug logging
hooks = create_logging_hooks(logger)  # Logs all events
```

## Requirements

- Python 3.10+
- anyio

## License

MIT
