"""Tree rendering for terminal display."""

from typing import Optional

from .config import TreeTaskConfig
from .core import TaskNode, TaskTree


class TreeRenderer:
    """Renders task trees to formatted strings.

    Example:
        >>> renderer = TreeRenderer(TreeTaskConfig())
        >>> print(renderer.render(tree))
        ✅ Pipeline
        ├── ✅ Phase 1
        │   ├── ✅ Task 1
        │   └── ✅ Task 2
        └── 🔄 Phase 2
            ├── 🔄 Task 3
            └── ⏳ Task 4
    """

    def __init__(self, config: Optional[TreeTaskConfig] = None):
        """Initialize the renderer.

        Args:
            config: Configuration for icons and tree characters.
        """
        self.config = config or TreeTaskConfig()

    def render(
        self,
        tree: TaskTree,
        max_depth: Optional[int] = None,
        show_stats: bool = False,
    ) -> str:
        """Render the tree to a string.

        Args:
            tree: The task tree to render.
            max_depth: Maximum depth to render. None for unlimited.
            show_stats: Whether to show statistics at the end.

        Returns:
            Formatted tree string.
        """
        lines = []
        self._render_node(tree.root, lines, "", True, 0, max_depth)

        if show_stats:
            # Use progress-based stats if available (more accurate for dynamic trees)
            progress_stats = tree.get_progress_stats()
            if progress_stats["nodes_with_progress"] > 0:
                lines.append("")
                lines.append(self._format_progress_stats(progress_stats))
            else:
                # Fall back to leaf stats if no progress tracking
                stats = tree.get_leaf_stats()
                lines.append("")
                lines.append(self._format_stats(stats))

        return "\n".join(lines)

    def _render_node(
        self,
        node: TaskNode,
        lines: list[str],
        prefix: str,
        is_last: bool,
        depth: int,
        max_depth: Optional[int],
    ) -> None:
        """Recursively render a node and its children.

        Args:
            node: The node to render.
            lines: List to append lines to.
            prefix: Current line prefix for tree structure.
            is_last: Whether this is the last child of its parent.
            depth: Current depth in the tree.
            max_depth: Maximum depth to render.
        """
        # Get status icon
        icon = self._get_status_icon(node)

        # Format progress if present
        progress_str = ""
        if node.progress is not None:
            current, total = node.progress
            progress_str = f" ({current}/{total})"

        # Build the line
        if depth == 0:
            # Root node - no prefix
            lines.append(f"{icon} {node.name}{progress_str}")
        else:
            chars = self.config.tree_chars
            branch = chars["last_branch"] if is_last else chars["branch"]
            lines.append(f"{prefix}{branch}{icon} {node.name}{progress_str}")

        # Render children if within depth limit
        if max_depth is None or depth < max_depth:
            children = node.children
            for i, child in enumerate(children):
                is_child_last = i == len(children) - 1

                # Calculate new prefix for children
                if depth == 0:
                    new_prefix = ""
                else:
                    chars = self.config.tree_chars
                    if is_last:
                        new_prefix = prefix + chars["empty"]
                    else:
                        new_prefix = prefix + chars["vertical"]

                self._render_node(
                    child, lines, new_prefix, is_child_last, depth + 1, max_depth
                )
        elif node.children:
            # Show collapsed indicator
            chars = self.config.tree_chars
            if depth == 0:
                new_prefix = ""
            else:
                new_prefix = prefix + (chars["empty"] if is_last else chars["vertical"])

            child_count = len(node.children)
            lines.append(f"{new_prefix}{chars['last_branch']}... ({child_count} items)")

    def _get_status_icon(self, node: TaskNode) -> str:
        """Get the status icon for a node.

        Args:
            node: The node to get the icon for.

        Returns:
            The status icon string.
        """
        icons = self.config.icons

        if node.status == "retrying":
            return f"{icons['retrying']} {node.retry_count}/{self.config.max_retries}"

        return icons.get(node.status, "❓")

    def _format_stats(self, stats: dict[str, int]) -> str:
        """Format statistics line.

        Args:
            stats: Statistics dictionary.

        Returns:
            Formatted statistics string.
        """
        icons = self.config.icons
        parts = []

        if stats.get("done", 0):
            parts.append(f"{icons['done']} {stats['done']}")
        if stats.get("working", 0):
            parts.append(f"{icons['working']} {stats['working']}")
        if stats.get("pending", 0):
            parts.append(f"{icons['pending']} {stats['pending']}")
        if stats.get("failed", 0):
            parts.append(f"{icons['failed']} {stats['failed']}")

        total = stats.get("total", 0)
        return f"[{' | '.join(parts)}] Total: {total}"

    def _format_progress_stats(self, stats: dict[str, int]) -> str:
        """Format progress-based statistics line.

        Shows aggregated progress (current/total) from nodes with progress tuples.
        This provides stable stats even when tree structure changes dynamically.

        Args:
            stats: Progress statistics from tree.get_progress_stats().

        Returns:
            Formatted progress string.
        """
        current = stats.get("current", 0)
        total = stats.get("total", 0)

        if total > 0:
            percentage = int((current / total) * 100)
            return f"Progress: {current}/{total} ({percentage}%)"
        else:
            return "Progress: 0/0 (0%)"

    def render_node_line(self, node: TaskNode) -> str:
        """Render a single node without tree structure.

        Args:
            node: The node to render.

        Returns:
            Single line representation.
        """
        icon = self._get_status_icon(node)
        progress_str = ""
        if node.progress is not None:
            current, total = node.progress
            progress_str = f" ({current}/{total})"
        return f"{icon} {node.name}{progress_str}"
