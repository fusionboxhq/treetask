"""Dependency resolution for DAG-based task execution."""

from collections import deque
from dataclasses import dataclass, field
from typing import Iterator, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import TaskNode, TaskTree


class CyclicDependencyError(Exception):
    """Raised when a circular dependency is detected."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle)}")


@dataclass
class DependencyResolver:
    """Resolves DAG dependencies for task execution.

    Handles cross-branch dependencies where tasks can depend on other tasks
    that are not their direct parents. Provides topological ordering and
    cycle detection.

    Example:
        >>> tree = (
        ...     TreeBuilder("pipeline")
        ...     .add_node("fetch_a", task=fetch_a).up()
        ...     .add_node("fetch_b", task=fetch_b).up()
        ...     .add_node("process", task=process)
        ...     .depends_on("fetch_a", "fetch_b")  # Wait for both
        ...     .build()
        ... )
        >>>
        >>> resolver = DependencyResolver(tree)
        >>> for node in resolver.topological_order():
        ...     print(node.name)
        # Output: fetch_a, fetch_b, process (or fetch_b, fetch_a, process)
    """

    tree: "TaskTree"
    _graph: dict[str, set[str]] = field(default_factory=dict, init=False)
    _reverse_graph: dict[str, set[str]] = field(default_factory=dict, init=False)
    _built: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Build dependency graphs."""
        self._build_graphs()

    def _build_graphs(self) -> None:
        """Build forward and reverse dependency graphs from node.depends_on fields."""
        self._graph.clear()
        self._reverse_graph.clear()

        for node in self.tree.walk():
            node_id = node.id
            self._graph[node_id] = set()
            if node_id not in self._reverse_graph:
                self._reverse_graph[node_id] = set()

            # Add explicit dependencies
            for dep_id in node.depends_on:
                self._graph[node_id].add(dep_id)
                if dep_id not in self._reverse_graph:
                    self._reverse_graph[dep_id] = set()
                self._reverse_graph[dep_id].add(node_id)

            # Parent is an implicit dependency (except for root)
            if node.parent is not None:
                parent_id = node.parent.id
                self._graph[node_id].add(parent_id)
                if parent_id not in self._reverse_graph:
                    self._reverse_graph[parent_id] = set()
                self._reverse_graph[parent_id].add(node_id)

        self._built = True

    def get_dependencies(self, node_id: str) -> set[str]:
        """Get all dependencies for a node.

        Args:
            node_id: The node ID to get dependencies for.

        Returns:
            Set of node IDs that this node depends on.
        """
        return self._graph.get(node_id, set())

    def get_dependents(self, node_id: str) -> set[str]:
        """Get all nodes that depend on a given node.

        Args:
            node_id: The node ID to get dependents for.

        Returns:
            Set of node IDs that depend on this node.
        """
        return self._reverse_graph.get(node_id, set())

    def is_ready(self, node_id: str, completed_ids: Set[str]) -> bool:
        """Check if a node's dependencies are all satisfied.

        Args:
            node_id: The node to check.
            completed_ids: Set of completed node IDs.

        Returns:
            True if all dependencies are in completed_ids.
        """
        deps = self._graph.get(node_id, set())
        return deps.issubset(completed_ids)

    def get_ready_nodes(self, completed_ids: Set[str]) -> list["TaskNode"]:
        """Get all nodes whose dependencies are satisfied.

        Args:
            completed_ids: Set of completed node IDs.

        Returns:
            List of nodes ready to execute.
        """
        ready = []
        for node in self.tree.walk():
            # Skip already completed or non-pending
            if node.id in completed_ids:
                continue
            if node.status not in ("pending",):
                continue

            if self.is_ready(node.id, completed_ids):
                ready.append(node)

        return ready

    def topological_order(self) -> Iterator["TaskNode"]:
        """Yield nodes in topological order (respecting all dependencies).

        Raises:
            CyclicDependencyError: If a cycle is detected.

        Yields:
            Nodes in valid execution order.
        """
        # Calculate in-degrees
        in_degree: dict[str, int] = {}
        for node in self.tree.walk():
            in_degree[node.id] = len(self._graph.get(node.id, set()))

        # Start with nodes that have no dependencies
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node_id = queue.popleft()
            node = self.tree.find(node_id)
            if node is not None:
                visited_count += 1
                yield node

            # Reduce in-degree of dependents
            for dependent_id in self._reverse_graph.get(node_id, set()):
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        # Check for cycles
        total_nodes = sum(1 for _ in self.tree.walk())
        if visited_count < total_nodes:
            # Find the cycle
            cycle = self._find_cycle()
            raise CyclicDependencyError(cycle)

    def _find_cycle(self) -> list[str]:
        """Find a cycle in the dependency graph using DFS.

        Returns:
            List of node IDs forming a cycle.
        """
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str) -> Optional[list[str]]:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for dep_id in self._graph.get(node_id, set()):
                if dep_id not in visited:
                    result = dfs(dep_id)
                    if result:
                        return result
                elif dep_id in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep_id)
                    return path[cycle_start:] + [dep_id]

            path.pop()
            rec_stack.remove(node_id)
            return None

        for node_id in self._graph:
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle:
                    return cycle

        return []

    def detect_cycles(self) -> list[list[str]]:
        """Detect all cycles in the dependency graph.

        Returns:
            List of cycles, where each cycle is a list of node IDs.
        """
        try:
            # Consume the generator to check for cycles
            list(self.topological_order())
            return []
        except CyclicDependencyError as e:
            return [e.cycle]

    def validate(self) -> list[str]:
        """Validate the dependency graph.

        Returns:
            List of error messages (empty if valid).
        """
        errors = []

        # Check for missing dependencies
        for node_id, deps in self._graph.items():
            for dep_id in deps:
                if self.tree.find(dep_id) is None:
                    errors.append(
                        f"Node '{node_id}' depends on non-existent node '{dep_id}'"
                    )

        # Check for cycles
        cycles = self.detect_cycles()
        for cycle in cycles:
            errors.append(f"Circular dependency: {' -> '.join(cycle)}")

        return errors

    def get_execution_levels(self) -> list[list["TaskNode"]]:
        """Get nodes grouped by execution level.

        Nodes in the same level have no dependencies on each other
        and can be executed in parallel.

        Returns:
            List of levels, where each level is a list of nodes.
        """
        levels: list[list["TaskNode"]] = []
        completed: Set[str] = set()
        remaining = set(node.id for node in self.tree.walk())

        while remaining:
            # Find all nodes ready at this level
            level_nodes = []
            for node_id in list(remaining):
                if self.is_ready(node_id, completed):
                    node = self.tree.find(node_id)
                    if node:
                        level_nodes.append(node)
                        remaining.remove(node_id)

            if not level_nodes:
                # No progress - must be a cycle
                break

            levels.append(level_nodes)
            completed.update(n.id for n in level_nodes)

        return levels
