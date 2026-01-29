# TreeTask

A Python package for hierarchical parallel task execution with live tree progress display.

## Features

- **Arbitrary nesting depth** - Support any level of task hierarchy
- **Granular parallelism control** - Configure parallel or sequential execution per node
- **Dynamic tree structure** - Add child nodes during execution
- **Live terminal display** - Real-time progress with ANSI cursor control
- **Progress tracking** - Accurate stats even with dynamically changing trees
- **Retry logic** - Configurable retries for failed tasks
- **Customizable display** - Configure icons, tree characters, and depth limits

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

        # Register with tree for indexing (optional but recommended)
        # Access tree via closure or node.data

    return {"children_count": len(items)}
```

For accurate progress tracking with dynamic trees, set the initial `progress` tuple when creating nodes:

```python
# Set expected total upfront for stable progress stats
child = TaskNode(
    id="task1",
    name="Task 1",
    progress=(0, 100),  # 0 of 100 complete
    task_fn=my_task,
)
```

### Error Handling and Retries

Tasks that raise exceptions are automatically retried based on `max_retries` in config:

```python
config = TreeTaskConfig(max_retries=3)  # Retry up to 3 times

async def flaky_task(node):
    if random.random() < 0.5:
        raise Exception("Random failure")
    node.progress = (1, 1)
    return {"status": "success"}
```

During retries, the node status becomes `"retrying"` and `node.retry_count` tracks attempts. If all retries fail, status becomes `"failed"` and `node.error` contains the error message.

### Execution Callbacks

Monitor execution with callbacks:

```python
def on_start(node):
    print(f"Starting: {node.name}")

def on_complete(node):
    print(f"Completed: {node.name} - {node.status}")

executor = AsyncExecutor(
    tree,
    on_update=lambda t: display.update(t),
    on_node_start=on_start,
    on_node_complete=on_complete,
)
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

### Using LiveDisplay

The `LiveDisplay` class handles terminal output with ANSI cursor control:

```python
display = LiveDisplay(TreeRenderer(config), config)

# As context manager (recommended - handles cursor visibility)
with display:
    executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
    await executor.run()

# Show final expanded tree
display.finalize(tree)

# Or manually control cursor
display.hide_cursor()
try:
    # ... run tasks with display.update(tree) ...
finally:
    display.show_cursor()
```

Additional display methods:
- `display.update(tree, max_depth=None, force=False)` - Update live display
- `display.finalize(tree, max_depth=None, show_stats=True)` - Show final tree
- `display.clear()` - Clear current display
- `display.print_message(msg)` - Print message below tree

## API Reference

### TaskNode

Represents a node in the task tree.

```python
@dataclass
class TaskNode:
    id: str                           # Unique identifier
    name: str                         # Display name
    status: str = "pending"           # pending, working, done, failed, retrying
    children: list[TaskNode]          # Child nodes
    parent: Optional[TaskNode]        # Parent reference
    data: dict[str, Any]              # User payload
    progress: Optional[tuple[int, int]]  # (current, total)
    retry_count: int = 0              # Current retry attempt
    error: Optional[str] = None       # Error message if failed
    parallel: bool = True             # Run children in parallel?
    task_fn: Optional[Callable]       # Async task function
```

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
- `get_progress_stats() -> dict` - Aggregate progress tuples (stable for dynamic trees)
- `register_node(node: TaskNode)` - Register dynamically added node in index

### TreeBuilder

Fluent API for building task trees.

```python
TreeBuilder(root_id: str, name: str = None, parallel: bool = True, data: dict = None)
```

Methods:
- `add_node(id, name, parallel, task, data)` - Add child and move into it
- `add_child(id, name, parallel, task, data)` - Add child, stay at current level
- `up()` - Move back to parent
- `build() -> TaskTree` - Return the completed tree

### AsyncExecutor

Executes task trees with configurable parallelism.

```python
AsyncExecutor(
    tree: TaskTree,
    on_update: Callable[[TaskTree], None] = None,
    on_node_start: Callable[[TaskNode], None] = None,
    on_node_complete: Callable[[TaskNode], None] = None,
)
```

Methods:
- `async run() -> TaskTree` - Execute all tasks and return the tree

### ExecutionResult

Result container for task tree execution.

```python
class ExecutionResult:
    tree: TaskTree           # The executed tree
    success: bool            # True if no failures
    failed_nodes: list       # Nodes that failed
    stats: dict              # Execution statistics
```

### TreeRenderer

Renders task trees to formatted strings.

```python
TreeRenderer(config: TreeTaskConfig = None)
```

Methods:
- `render(tree, max_depth=None, show_stats=False) -> str` - Render tree to string
- `render_node_line(node) -> str` - Render single node without tree structure

### LiveDisplay

Live updating terminal display using ANSI escape codes.

```python
LiveDisplay(
    renderer: TreeRenderer = None,
    config: TreeTaskConfig = None,
    output: TextIO = None,  # Defaults to sys.stderr
)
```

Methods:
- `update(tree, max_depth=None, force=False)` - Update display (rate-limited)
- `finalize(tree, max_depth=None, show_stats=True)` - Show final tree
- `clear()` - Clear current display
- `print_message(message: str)` - Print message below tree
- `hide_cursor()` / `show_cursor()` - Control cursor visibility

Context manager support:
```python
with display:  # Hides cursor on enter, shows on exit
    ...
```

### TreeTaskConfig

Configuration dataclass for execution and display.

```python
@dataclass
class TreeTaskConfig:
    # Display
    default_max_depth: int = 2      # Depth during live updates
    final_max_depth: int = 3        # Depth in final display
    refresh_interval: float = 0.1   # Min seconds between updates

    # Icons
    icons: dict[str, str]           # Status -> icon mapping
    tree_chars: dict[str, str]      # Tree structure characters

    # Execution
    default_parallel: bool = True   # Default parallel flag
    max_retries: int = 3            # Retry attempts for failures
```

## Requirements

- Python 3.10+
- anyio

## License

MIT
