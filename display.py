"""Live terminal display for task trees."""

import sys
import threading
import time
from typing import Optional, TextIO

from .config import TreeTaskConfig
from .core import TaskTree
from .renderer import TreeRenderer


class LiveDisplay:
    """Live updating terminal display for task trees.

    Uses ANSI escape codes to update the display in place without scrolling.

    Example:
        >>> display = LiveDisplay(TreeRenderer(config))
        >>> display.update(tree)  # Call repeatedly as tree changes
        >>> display.finalize(tree)  # Show final expanded tree
    """

    # ANSI escape codes
    CURSOR_UP = "\033[A"
    CLEAR_LINE = "\033[2K"
    CURSOR_TO_START = "\033[G"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"

    def __init__(
        self,
        renderer: Optional[TreeRenderer] = None,
        config: Optional[TreeTaskConfig] = None,
        output: Optional[TextIO] = None,
    ):
        """Initialize the live display.

        Args:
            renderer: TreeRenderer instance. Created if not provided.
            config: Configuration. Used if renderer not provided.
            output: Output stream. Defaults to sys.stderr.
        """
        self.config = config or TreeTaskConfig()
        self.renderer = renderer or TreeRenderer(self.config)
        self.output = output or sys.stderr

        self._lock = threading.Lock()
        self._last_line_count = 0
        self._last_update_time = 0.0
        self._started = False
        self._finalized = False

    def update(
        self,
        tree: TaskTree,
        max_depth: Optional[int] = None,
        force: bool = False,
    ) -> None:
        """Update the terminal display with the current tree state.

        Args:
            tree: The task tree to display.
            max_depth: Maximum depth to show. Defaults to config.default_max_depth.
            force: Force update even if within refresh interval.
        """
        if self._finalized:
            return

        # Rate limiting
        now = time.time()
        if not force and (now - self._last_update_time) < self.config.refresh_interval:
            return

        with self._lock:
            self._last_update_time = now

            if max_depth is None:
                max_depth = self.config.default_max_depth

            # Render the tree with progress-based stats (stable even with dynamic tree)
            rendered = self.renderer.render(tree, max_depth=max_depth, show_stats=True)
            lines = rendered.split("\n")

            # Clear previous output
            if self._last_line_count > 0:
                # Move cursor up and clear each line
                for _ in range(self._last_line_count):
                    self.output.write(self.CURSOR_UP + self.CLEAR_LINE)

            # Write new output
            for line in lines:
                self.output.write(self.CURSOR_TO_START + line + "\n")

            self.output.flush()
            self._last_line_count = len(lines)
            self._started = True

    def finalize(
        self,
        tree: TaskTree,
        max_depth: Optional[int] = None,
        show_stats: bool = True,
    ) -> None:
        """Show the final tree state with expanded depth.

        This clears the live display and shows the final result.

        Args:
            tree: The task tree to display.
            max_depth: Maximum depth to show. Defaults to config.final_max_depth.
            show_stats: Whether to show statistics.
        """
        with self._lock:
            self._finalized = True

            if max_depth is None:
                max_depth = self.config.final_max_depth

            # Clear previous output
            if self._last_line_count > 0:
                for _ in range(self._last_line_count):
                    self.output.write(self.CURSOR_UP + self.CLEAR_LINE)

            # Render and write final tree
            rendered = self.renderer.render(
                tree, max_depth=max_depth, show_stats=show_stats
            )
            self.output.write(self.CURSOR_TO_START + rendered + "\n")
            self.output.flush()

            self._last_line_count = 0

    def clear(self) -> None:
        """Clear the current display."""
        with self._lock:
            if self._last_line_count > 0:
                for _ in range(self._last_line_count):
                    self.output.write(self.CURSOR_UP + self.CLEAR_LINE)
                self.output.flush()
                self._last_line_count = 0

    def print_message(self, message: str) -> None:
        """Print a message below the tree display.

        This temporarily clears the tree, prints the message, then redraws.

        Args:
            message: The message to print.
        """
        with self._lock:
            # Messages go below the tree, so just print
            self.output.write(message + "\n")
            self.output.flush()

    def hide_cursor(self) -> None:
        """Hide the terminal cursor."""
        self.output.write(self.HIDE_CURSOR)
        self.output.flush()

    def show_cursor(self) -> None:
        """Show the terminal cursor."""
        self.output.write(self.SHOW_CURSOR)
        self.output.flush()

    def __enter__(self) -> "LiveDisplay":
        """Context manager entry - hide cursor."""
        self.hide_cursor()
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit - show cursor."""
        self.show_cursor()
