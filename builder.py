"""Fluent builder API for constructing task trees."""

from typing import Any, Optional

from .config import TreeTaskConfig
from .core import TaskFunction, TaskNode, TaskTree


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
        ...     .build()
        ... )
    """

    def __init__(
        self,
        root_id: str,
        name: Optional[str] = None,
        config: Optional[TreeTaskConfig] = None,
    ):
        """Initialize the builder with a root node.

        Args:
            root_id: ID for the root node.
            name: Display name for the root node. Defaults to root_id.
            config: Configuration settings for the tree.
        """
        self._config = config or TreeTaskConfig()
        self._root = TaskNode(
            id=root_id,
            name=name or root_id,
            parallel=self._config.default_parallel,
        )
        self._current = self._root
        self._stack: list[TaskNode] = []

    def add_node(
        self,
        node_id: str,
        name: Optional[str] = None,
        parallel: Optional[bool] = None,
        task: Optional[TaskFunction] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> "TreeBuilder":
        """Add a child node to the current node and move into it.

        Args:
            node_id: Unique identifier for the node.
            name: Display name. Defaults to node_id.
            parallel: Whether children run in parallel. Defaults to config setting.
            task: Async function to execute for this node.
            data: User payload data.

        Returns:
            Self for method chaining.
        """
        node = TaskNode(
            id=node_id,
            name=name or node_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            task_fn=task,
            data=data or {},
        )
        self._current.add_child(node)
        self._stack.append(self._current)
        self._current = node
        return self

    def add_child(
        self,
        node_id: str,
        name: Optional[str] = None,
        parallel: Optional[bool] = None,
        task: Optional[TaskFunction] = None,
        data: Optional[dict[str, Any]] = None,
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

        Returns:
            Self for method chaining.
        """
        node = TaskNode(
            id=node_id,
            name=name or node_id,
            parallel=parallel if parallel is not None else self._config.default_parallel,
            task_fn=task,
            data=data or {},
        )
        self._current.add_child(node)
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
