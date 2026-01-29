# TreeTask

A Python package for hierarchical parallel task execution with live tree progress display.

## Features

- **Arbitrary nesting depth** - Support any level of task hierarchy
- **Granular parallelism control** - Configure which levels run in parallel
- **Dynamic tree structure** - Add child nodes during execution
- **Live terminal display** - Real-time progress with ANSI cursor control
- **Progress tracking** - Accurate stats even with dynamic trees
- **Retry logic** - Configurable retries for failed tasks

## Installation

```bash
pip install git+https://github.com/fusionboxhq/treetask.git
```

## Quick Start

```python
import anyio
from treetask import TreeBuilder, AsyncExecutor, TreeRenderer, LiveDisplay, TreeTaskConfig

async def my_task(node):
    """Example task function."""
    await anyio.sleep(1)
    node.progress = (1, 1)  # (current, total)
    return {"result": "done"}

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

## Output

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

## Dynamic Tree Structure

TreeTask supports adding child nodes during execution, useful when the full tree structure isn't known upfront:

```python
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

    return {"children": len(items)}
```

## API Reference

### TreeBuilder

Fluent API for building task trees:

- `add_node(id, name, parallel, task, data)` - Add child and move into it
- `add_child(id, name, parallel, task, data)` - Add child, stay at current level
- `up()` - Move back to parent
- `build()` - Return the TaskTree

### TaskNode

Represents a node in the task tree:

- `id` - Unique identifier
- `name` - Display name
- `status` - pending, working, done, failed, retrying
- `parallel` - Whether children run in parallel
- `task_fn` - Async function to execute
- `progress` - Tuple of (current, total)
- `data` - User payload dict
- `children` - Child nodes

### AsyncExecutor

Executes the task tree:

- `run()` - Execute all tasks
- `on_update` - Callback when tree state changes

### TreeTaskConfig

Configuration options:

- `default_max_depth` - Depth shown during live updates (default: 2)
- `final_max_depth` - Depth shown in final display (default: 3)
- `refresh_interval` - Min seconds between display updates (default: 0.1)
- `max_retries` - Retry attempts for failed tasks (default: 3)
- `icons` - Status icons dict

## Requirements

- Python 3.10+
- anyio

## License

MIT
