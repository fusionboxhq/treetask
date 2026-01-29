"""
TreeTask - Hierarchical parallel task execution with live tree progress display.

A reusable Python package for executing task trees with configurable parallelism
and live terminal progress visualization.

Example usage:
    >>> from treetask import TreeBuilder, AsyncExecutor, LiveDisplay, TreeTaskConfig
    >>>
    >>> async def my_task(node):
    ...     await anyio.sleep(1)
    ...     return {"result": "done"}
    >>>
    >>> tree = (
    ...     TreeBuilder("pipeline")
    ...     .add_node("phase1", name="Phase 1", parallel=True)
    ...         .add_child("task1", name="Task 1", task=my_task)
    ...         .add_child("task2", name="Task 2", task=my_task)
    ...     .build()
    ... )
    >>>
    >>> display = LiveDisplay(TreeRenderer(TreeTaskConfig()))
    >>> executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
    >>> anyio.run(executor.run)
"""

from .config import TreeTaskConfig
from .core import TaskNode, TaskTree
from .builder import TreeBuilder
from .executor import AsyncExecutor
from .renderer import TreeRenderer
from .display import LiveDisplay

__all__ = [
    "TreeTaskConfig",
    "TaskNode",
    "TaskTree",
    "TreeBuilder",
    "AsyncExecutor",
    "TreeRenderer",
    "LiveDisplay",
]

__version__ = "0.1.0"
