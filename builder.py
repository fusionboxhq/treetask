"""Fluent builder API for constructing task trees."""

from typing import Any, Callable, Optional, TYPE_CHECKING

from .config import TreeTaskConfig
from .core import ConditionFunction, TaskFunction, TaskNode, TaskTree

if TYPE_CHECKING:
    from .strategies import RetryStrategy


class TreeBuilder:
    """Fluent builder for constructing task trees.

    Example:
        >>> tree = (
        ...     TreeBuilder("pipeline")
        ...     .add_node("phase1", name="Phase 1", parallel=True)
        ...         .add_child("task1", name="Task 1", task=my_task)
        ...         .add_child("task2", name="Task 2", task=my_task)
        ...     .up()
        ...     .add_node("phase2", name="Phase 2", parallel=False)
        ...         .add_child("task3", name="Task 3", task=my_task)
        ...         .set_timeout(30.0)  # 30 second timeout
        ...         .set_max_retries(5)
        ...     .up()
        ...     .add_node("final", name="Final", task=final_task)
        ...         .depends_on("phase1", "phase2")  # Wait for both
        ...     .build()
        ... )
    """

    def __init__(
        self,
        root_id: str,
        name: Optional[str] = None,
        config: Optional[TreeTaskConfig] = None,
        parallel: Optional[bool] = None,
        data: Optional[dict[str, Any]] = None,
    ):
        """Initialize the builder with a root node.

        Args:
            root_id: ID for the root node.
            name: Display name for the root node. Defaults to root_id.
            config: Configuration settings for the tree.
            parallel: Whether root's children run in parallel. Defaults to config.
            data: Initial data for root node.
        """
        self._config = config or TreeTaskConfig()
        self._root = TaskNode(
            id=root_id,
            name=name or root_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            data=data or {},
        )
        self._current = self._root
        self._stack: list[TaskNode] = []
        self._last_added: Optional[TaskNode] = None  # Track last added child

    def add_node(
        self,
        node_id: str,
        name: Optional[str] = None,
        parallel: Optional[bool] = None,
        task: Optional[TaskFunction] = None,
        data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        depends_on: Optional[list[str]] = None,
    ) -> "TreeBuilder":
        """Add a child node to the current node and move into it.

        Args:
            node_id: Unique identifier for the node.
            name: Display name. Defaults to node_id.
            parallel: Whether children run in parallel. Defaults to config setting.
            task: Async function to execute for this node.
            data: User payload data.
            timeout: Per-node timeout in seconds.
            max_retries: Per-node retry limit.
            depends_on: List of node IDs this node depends on.

        Returns:
            Self for method chaining.
        """
        node = TaskNode(
            id=node_id,
            name=name or node_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            task_fn=task,
            data=data or {},
            timeout=timeout,
            max_retries=max_retries,
            depends_on=depends_on or [],
        )
        self._current.add_child(node)
        self._stack.append(self._current)
        self._current = node
        self._last_added = node
        return self

    def add_child(
        self,
        node_id: str,
        name: Optional[str] = None,
        parallel: Optional[bool] = None,
        task: Optional[TaskFunction] = None,
        data: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        depends_on: Optional[list[str]] = None,
        progress: Optional[tuple[int, int]] = None,
    ) -> "TreeBuilder":
        """Add a child node to the current node WITHOUT moving into it.

        Use this for adding leaf nodes or multiple siblings at the same level.
        Use add_node() when you want to add a node and then add children to it.

        Args:
            node_id: Unique identifier for the node.
            name: Display name. Defaults to node_id.
            parallel: Whether children run in parallel. Defaults to config setting.
            task: Async function to execute for this node.
            data: User payload data.
            timeout: Per-node timeout in seconds.
            max_retries: Per-node retry limit.
            depends_on: List of node IDs this node depends on.
            progress: Initial progress tuple (current, total).

        Returns:
            Self for method chaining.
        """
        node = TaskNode(
            id=node_id,
            name=name or node_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            task_fn=task,
            data=data or {},
            timeout=timeout,
            max_retries=max_retries,
            depends_on=depends_on or [],
            progress=progress,
        )
        self._current.add_child(node)
        self._last_added = node
        return self

    def add_sibling(
        self,
        node_id: str,
        name: Optional[str] = None,
        parallel: Optional[bool] = None,
        task: Optional[TaskFunction] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> "TreeBuilder":
        """Add a sibling node (same parent) and move into it.

        Args:
            node_id: Unique identifier for the node.
            name: Display name. Defaults to node_id.
            parallel: Whether children run in parallel.
            task: Async function to execute.
            data: User payload data.

        Returns:
            Self for method chaining.
        """
        if not self._stack:
            raise ValueError("Cannot add sibling to root node")

        parent = self._stack[-1]
        node = TaskNode(
            id=node_id,
            name=name or node_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            task_fn=task,
            data=data or {},
        )
        parent.add_child(node)
        self._current = node
        self._last_added = node
        return self

    def up(self) -> "TreeBuilder":
        """Move back up to the parent node.

        Returns:
            Self for method chaining.
        """
        if self._stack:
            self._current = self._stack.pop()
        return self

    def root(self) -> "TreeBuilder":
        """Move back to the root node.

        Returns:
            Self for method chaining.
        """
        self._current = self._root
        self._stack.clear()
        return self

    # Data and task setters

    def set_data(self, **kwargs: Any) -> "TreeBuilder":
        """Set data on the current node.

        Returns:
            Self for method chaining.
        """
        self._current.data.update(kwargs)
        return self

    def set_task(self, task: TaskFunction) -> "TreeBuilder":
        """Set the task function on the current node.

        Returns:
            Self for method chaining.
        """
        self._current.task_fn = task
        return self

    def set_progress(self, current: int, total: int) -> "TreeBuilder":
        """Set progress on the current node.

        Args:
            current: Current progress value.
            total: Total progress value.

        Returns:
            Self for method chaining.
        """
        self._current.progress = (current, total)
        return self

    # Timeout settings (Feature 1)

    def set_timeout(self, timeout: float) -> "TreeBuilder":
        """Set timeout for the current node.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Self for method chaining.
        """
        self._current.timeout = timeout
        return self

    # Retry settings (Feature 5, 6)

    def set_max_retries(self, max_retries: int) -> "TreeBuilder":
        """Set max retries for the current node.

        Args:
            max_retries: Maximum retry attempts.

        Returns:
            Self for method chaining.
        """
        self._current.max_retries = max_retries
        return self

    def set_retry_strategy(self, strategy: "RetryStrategy") -> "TreeBuilder":
        """Set retry strategy for the current node.

        Args:
            strategy: Retry strategy to use.

        Returns:
            Self for method chaining.
        """
        self._current.retry_strategy = strategy
        return self

    # Dependencies (Feature 11)

    def depends_on(self, *node_ids: str) -> "TreeBuilder":
        """Add dependencies to the current node.

        The current node will not start until all specified nodes are done.

        Args:
            *node_ids: IDs of nodes this node depends on.

        Returns:
            Self for method chaining.
        """
        self._current.depends_on.extend(node_ids)
        return self

    def clear_dependencies(self) -> "TreeBuilder":
        """Clear all dependencies from the current node.

        Returns:
            Self for method chaining.
        """
        self._current.depends_on.clear()
        return self

    # Conditional execution (Feature 12)

    def set_skip_condition(self, condition: ConditionFunction) -> "TreeBuilder":
        """Set a condition that skips this node if True.

        Args:
            condition: Function that takes the node and returns True to skip.

        Returns:
            Self for method chaining.
        """
        self._current.skip_condition = condition
        return self

    def set_run_condition(self, condition: ConditionFunction) -> "TreeBuilder":
        """Set a condition that must be True to run this node.

        Args:
            condition: Function that takes the node and returns True to run.

        Returns:
            Self for method chaining.
        """
        self._current.run_condition = condition
        return self

    def skip_if(self, condition: ConditionFunction) -> "TreeBuilder":
        """Alias for set_skip_condition.

        Args:
            condition: Function that takes the node and returns True to skip.

        Returns:
            Self for method chaining.
        """
        return self.set_skip_condition(condition)

    def run_if(self, condition: ConditionFunction) -> "TreeBuilder":
        """Alias for set_run_condition.

        Args:
            condition: Function that takes the node and returns True to run.

        Returns:
            Self for method chaining.
        """
        return self.set_run_condition(condition)

    # Operations on last added child

    def with_last(self) -> "TreeBuilder":
        """Move to the last added child node.

        Useful for configuring a child after add_child().

        Returns:
            Self for method chaining.
        """
        if self._last_added is not None and self._last_added != self._current:
            self._stack.append(self._current)
            self._current = self._last_added
        return self

    # Build

    def build(self) -> TaskTree:
        """Build and return the task tree.

        Returns:
            The constructed TaskTree.
        """
        return TaskTree(self._root, self._config)

    @property
    def current(self) -> TaskNode:
        """Get the current node."""
        return self._current

    @property
    def last_added(self) -> Optional[TaskNode]:
        """Get the last added node."""
        return self._last_added
