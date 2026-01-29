"""
TreeTask - Hierarchical parallel task execution with live tree progress display.

A reusable Python package for executing task trees with configurable parallelism
and live terminal progress visualization.

Features:
- Arbitrary nesting depth
- Granular parallelism control (parallel or sequential per node)
- Timeout support (global and per-task)
- Cancellation and pause/resume
- Max concurrency limits
- Retry strategies (fixed delay, exponential backoff, custom)
- Conditional execution (skip/run conditions)
- DAG dependencies (cross-branch dependencies)
- Serialization (save/restore tree state)
- Resume from checkpoint
- Result aggregation
- Execution timing and ETA
- Hooks for observability
- Structured logging

Example usage:
    >>> from treetask import TreeBuilder, AsyncExecutor, LiveDisplay, TreeTaskConfig
    >>>
    >>> async def my_task(node):
    ...     await anyio.sleep(1)
    ...     node.progress = (1, 1)
    ...     return {"result": "done"}
    >>>
    >>> tree = (
    ...     TreeBuilder("pipeline")
    ...     .add_node("phase1", name="Phase 1", parallel=True)
    ...         .add_child("task1", name="Task 1", task=my_task)
    ...         .add_child("task2", name="Task 2", task=my_task)
    ...     .up()
    ...     .add_node("phase2", name="Phase 2", parallel=False)
    ...         .add_child("task3", name="Task 3", task=my_task)
    ...         .set_timeout(30.0)
    ...     .build()
    ... )
    >>>
    >>> config = TreeTaskConfig(max_concurrency=5)
    >>> display = LiveDisplay(TreeRenderer(config), config)
    >>> executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
    >>> anyio.run(executor.run)
"""

# Core classes
from .config import TreeTaskConfig
from .core import TaskNode, TaskTree, TaskFunction, ConditionFunction
from .builder import TreeBuilder
from .executor import AsyncExecutor, ExecutionResult
from .renderer import TreeRenderer
from .display import LiveDisplay

# Execution context
from .context import ExecutionContext

# Retry strategies
from .strategies import (
    RetryStrategy,
    NoRetry,
    FixedDelayRetry,
    ExponentialBackoffRetry,
    LinearBackoffRetry,
    CustomRetry,
    RetryOnExceptionTypes,
)

# Hooks and events
from .hooks import HookDispatcher, TaskHooks, create_logging_hooks

# Serialization
from .serialization import TreeSerializer, create_task_registry

# Dependencies
from .dependencies import DependencyResolver, CyclicDependencyError

# Logging
from .logging_integration import (
    TreeTaskLogger,
    StructuredFormatter,
    configure_treetask_logging,
)

# Timing utilities
from .timing import (
    TimingStats,
    format_duration,
    format_eta,
    format_progress_with_eta,
)

__all__ = [
    # Core
    "TreeTaskConfig",
    "TaskNode",
    "TaskTree",
    "TaskFunction",
    "ConditionFunction",
    "TreeBuilder",
    "AsyncExecutor",
    "ExecutionResult",
    "TreeRenderer",
    "LiveDisplay",
    # Context
    "ExecutionContext",
    # Strategies
    "RetryStrategy",
    "NoRetry",
    "FixedDelayRetry",
    "ExponentialBackoffRetry",
    "LinearBackoffRetry",
    "CustomRetry",
    "RetryOnExceptionTypes",
    # Hooks
    "HookDispatcher",
    "TaskHooks",
    "create_logging_hooks",
    # Serialization
    "TreeSerializer",
    "create_task_registry",
    # Dependencies
    "DependencyResolver",
    "CyclicDependencyError",
    # Logging
    "TreeTaskLogger",
    "StructuredFormatter",
    "configure_treetask_logging",
    # Timing
    "TimingStats",
    "format_duration",
    "format_eta",
    "format_progress_with_eta",
]

__version__ = "0.2.0"
