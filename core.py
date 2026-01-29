"""Core data structures for TreeTask."""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Iterator, Optional, TYPE_CHECKING

from .config import TreeTaskConfig

if TYPE_CHECKING:
    from .strategies import RetryStrategy


# Type alias for task functions
TaskFunction = Callable[["TaskNode"], Coroutine[Any, Any, Any]]

# Type alias for condition functions
ConditionFunction = Callable[["TaskNode"], bool]


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
        start_time: Timestamp when execution started.
        end_time: Timestamp when execution ended.
        timeout: Per-node timeout in seconds.
        max_retries: Per-node retry limit (overrides global).
        retry_strategy: Per-node retry strategy (overrides global).
        depends_on: List of node IDs this node depends on.
        skip_condition: Function that returns True to skip this node.
        run_condition: Function that returns True to run this node.
        result: Return value from task function.
    """

    id: str
    name: str
    status: str = "pending"  # pending, working, done, failed, retrying, cancelled, skipped, timed_out
    children: list["TaskNode"] = field(default_factory=list)
    parent: Optional["TaskNode"] = None
    data: dict[str, Any] = field(default_factory=dict)
    progress: Optional[tuple[int, int]] = None  # (current, total)
    retry_count: int = 0
    error: Optional[str] = None

    # Execution config
    parallel: bool = True
    task_fn: Optional[TaskFunction] = None

    # Timing (Feature 7)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    # Per-node retry config (Feature 5, 6)
    max_retries: Optional[int] = None
    retry_strategy: Optional["RetryStrategy"] = None

    # Timeout (Feature 1)
    timeout: Optional[float] = None

    # Dependencies (Feature 11)
    depends_on: list[str] = field(default_factory=list)

    # Conditional execution (Feature 12)
    skip_condition: Optional[ConditionFunction] = None
    run_condition: Optional[ConditionFunction] = None

    # Result storage (Feature 13)
    result: Any = None

    @property
    def elapsed(self) -> Optional[float]:
        """Get elapsed time in seconds.

        Returns:
            Elapsed time if started, None otherwise.
        """
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    def add_child(self, child: "TaskNode") -> "TaskNode":
        """Add a child node and set its parent reference."""
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: "TaskNode") -> bool:
        """Remove a child node.

        Args:
            child: The child node to remove.

        Returns:
            True if child was found and removed.
        """
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False

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

    def is_done(self) -> bool:
        """Check if this node has completed execution."""
        return self.status in ("done", "failed", "cancelled", "skipped", "timed_out")

    def is_successful(self) -> bool:
        """Check if this node completed successfully."""
        return self.status == "done"

    def get_ancestors(self) -> list["TaskNode"]:
        """Get all ancestor nodes from parent to root."""
        ancestors = []
        node = self.parent
        while node is not None:
            ancestors.append(node)
            node = node.parent
        return ancestors

    def get_root(self) -> "TaskNode":
        """Get the root node of this tree."""
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    def find_child(self, child_id: str) -> Optional["TaskNode"]:
        """Find a direct child by ID.

        Args:
            child_id: The ID of the child to find.

        Returns:
            The child node or None.
        """
        for child in self.children:
            if child.id == child_id:
                return child
        return None

    def walk(self) -> Iterator["TaskNode"]:
        """Iterate over this node and all descendants."""
        yield self
        for child in self.children:
            yield from child.walk()

    def reset(self) -> None:
        """Reset this node to pending state."""
        self.status = "pending"
        self.start_time = None
        self.end_time = None
        self.retry_count = 0
        self.error = None
        self.result = None

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
            "cancelled": 0,
            "skipped": 0,
            "timed_out": 0,
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
            "cancelled": 0,
            "skipped": 0,
            "timed_out": 0,
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
            "cancelled": 0,
            "skipped": 0,
            "timed_out": 0,
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

    def unregister_node(self, node_id: str) -> None:
        """Remove a node from the index."""
        self._node_index.pop(node_id, None)

    # Result aggregation (Feature 13)

    def collect_results(self) -> dict[str, Any]:
        """Collect results from all nodes.

        Returns:
            Dictionary mapping node IDs to their results.
        """
        results = {}
        for node in self.walk():
            if node.result is not None:
                results[node.id] = node.result
        return results

    def aggregate_results(
        self, reducer: Callable[[list[Any]], Any]
    ) -> Any:
        """Aggregate all results using a reducer function.

        Args:
            reducer: Function that takes list of results and returns aggregated value.

        Returns:
            Aggregated result.
        """
        results = [node.result for node in self.walk() if node.result is not None]
        return reducer(results)

    def get_failed_nodes(self) -> list[TaskNode]:
        """Get all nodes that failed.

        Returns:
            List of failed nodes.
        """
        return [node for node in self.walk() if node.status == "failed"]

    def get_completed_ids(self) -> set[str]:
        """Get IDs of all completed nodes.

        Returns:
            Set of node IDs that are done, skipped, cancelled, or timed_out.
        """
        return {
            node.id
            for node in self.walk()
            if node.status in ("done", "skipped", "cancelled", "timed_out")
        }

    def reset(self) -> None:
        """Reset all nodes to pending state."""
        for node in self.walk():
            node.reset()

    def get_timing_stats(self) -> dict[str, Any]:
        """Get timing statistics for the tree.

        Returns:
            Dictionary with timing statistics.
        """
        durations = []
        for node in self.walk():
            if node.elapsed is not None and node.status == "done":
                durations.append(node.elapsed)

        if not durations:
            return {
                "count": 0,
                "total": 0,
                "average": None,
                "min": None,
                "max": None,
            }

        return {
            "count": len(durations),
            "total": sum(durations),
            "average": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return f"TaskTree(root={self.root.id!r}, nodes={stats['total']})"
