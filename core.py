"""Core data structures for TreeTask."""

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Iterator, Optional

from .config import TreeTaskConfig


# Type alias for task functions
TaskFunction = Callable[["TaskNode"], Coroutine[Any, Any, Any]]


@dataclass
class TaskNode:
    """A node in the task tree.

    Attributes:
        id: Unique identifier for this node.
        name: Human-readable display name.
        status: Current execution status.
        children: Child nodes.
        parent: Parent node reference.
        data: User payload data.
        progress: Optional (current, total) progress tuple.
        retry_count: Number of retries attempted.
        error: Error message if failed.
        parallel: Whether children can run in parallel.
        task_fn: Async function to execute for this node.
    """

    id: str
    name: str
    status: str = "pending"  # pending, working, done, failed, retrying
    children: list["TaskNode"] = field(default_factory=list)
    parent: Optional["TaskNode"] = None
    data: dict[str, Any] = field(default_factory=dict)
    progress: Optional[tuple[int, int]] = None  # (current, total)
    retry_count: int = 0
    error: Optional[str] = None

    # Execution config
    parallel: bool = True
    task_fn: Optional[TaskFunction] = None

    def add_child(self, child: "TaskNode") -> "TaskNode":
        """Add a child node and set its parent reference."""
        child.parent = self
        self.children.append(child)
        return child

    def get_depth(self) -> int:
        """Get the depth of this node in the tree (root = 0)."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def is_leaf(self) -> bool:
        """Check if this node has no children."""
        return len(self.children) == 0

    def get_ancestors(self) -> list["TaskNode"]:
        """Get all ancestor nodes from parent to root."""
        ancestors = []
        node = self.parent
        while node is not None:
            ancestors.append(node)
            node = node.parent
        return ancestors

    def __repr__(self) -> str:
        return f"TaskNode(id={self.id!r}, name={self.name!r}, status={self.status!r})"


class TaskTree:
    """A tree of tasks with execution and display capabilities.

    Attributes:
        root: The root node of the tree.
        config: Configuration settings.
    """

    def __init__(self, root: TaskNode, config: Optional[TreeTaskConfig] = None):
        self.root = root
        self.config = config or TreeTaskConfig()
        self._node_index: dict[str, TaskNode] = {}
        self._build_index(root)

    def _build_index(self, node: TaskNode) -> None:
        """Build the node ID index."""
        self._node_index[node.id] = node
        for child in node.children:
            self._build_index(child)

    def find(self, node_id: str) -> Optional[TaskNode]:
        """Find a node by its ID."""
        return self._node_index.get(node_id)

    def walk(self, depth_first: bool = True) -> Iterator[TaskNode]:
        """Iterate over all nodes in the tree.

        Args:
            depth_first: If True, use depth-first traversal. Otherwise breadth-first.
        """
        if depth_first:
            yield from self._walk_depth_first(self.root)
        else:
            yield from self._walk_breadth_first(self.root)

    def _walk_depth_first(self, node: TaskNode) -> Iterator[TaskNode]:
        """Depth-first traversal."""
        yield node
        for child in node.children:
            yield from self._walk_depth_first(child)

    def _walk_breadth_first(self, node: TaskNode) -> Iterator[TaskNode]:
        """Breadth-first traversal."""
        queue = [node]
        while queue:
            current = queue.pop(0)
            yield current
            queue.extend(current.children)

    def get_stats(self) -> dict[str, int]:
        """Get counts of nodes by status."""
        stats: dict[str, int] = {
            "pending": 0,
            "working": 0,
            "done": 0,
            "failed": 0,
            "retrying": 0,
            "total": 0,
        }
        for node in self.walk():
            stats["total"] += 1
            if node.status in stats:
                stats[node.status] += 1
        return stats

    def get_leaf_stats(self) -> dict[str, int]:
        """Get counts of leaf nodes by status."""
        stats: dict[str, int] = {
            "pending": 0,
            "working": 0,
            "done": 0,
            "failed": 0,
            "retrying": 0,
            "total": 0,
        }
        for node in self.walk():
            if node.is_leaf():
                stats["total"] += 1
                if node.status in stats:
                    stats[node.status] += 1
        return stats

    def get_work_node_stats(self) -> dict[str, int]:
        """Get counts of work nodes (nodes with task_fn) by status.

        This provides stable stats for trees where nodes are added dynamically,
        as it only counts nodes that represent actual work (have task_fn set).
        """
        stats: dict[str, int] = {
            "pending": 0,
            "working": 0,
            "done": 0,
            "failed": 0,
            "retrying": 0,
            "total": 0,
        }
        for node in self.walk():
            if node.task_fn is not None:
                stats["total"] += 1
                if node.status in stats:
                    stats[node.status] += 1
        return stats

    def get_progress_stats(self) -> dict[str, int]:
        """Get aggregated progress stats from all nodes with progress tuples.

        This aggregates (current, total) progress tuples from all nodes,
        providing accurate progress tracking even when tree structure changes.

        Returns:
            Dict with 'current', 'total', and status counts for nodes with progress.
        """
        stats: dict[str, int] = {
            "current": 0,
            "total": 0,
            "done": 0,
            "working": 0,
            "pending": 0,
            "failed": 0,
            "nodes_with_progress": 0,
        }
        for node in self.walk():
            if node.progress is not None:
                current, total = node.progress
                stats["current"] += current
                stats["total"] += total
                stats["nodes_with_progress"] += 1
                if node.status in stats:
                    stats[node.status] += 1
        return stats

    def register_node(self, node: TaskNode) -> None:
        """Register a node in the index (called when adding nodes after construction)."""
        self._node_index[node.id] = node

    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"TaskTree(root={self.root.id!r}, nodes={stats['total']})"
