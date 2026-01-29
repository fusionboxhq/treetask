"""Configuration for TreeTask."""

from dataclasses import dataclass, field


@dataclass
class TreeTaskConfig:
    """Configuration for tree task execution and display.

    Attributes:
        default_max_depth: Default depth to show during live updates.
        final_max_depth: Depth to show in final display.
        refresh_interval: Minimum interval between display updates in seconds.
        icons: Status icons for each task state.
        default_parallel: Whether children run in parallel by default.
        max_retries: Maximum retry attempts for failed tasks.
    """

    # Display settings
    default_max_depth: int = 2
    final_max_depth: int = 3
    refresh_interval: float = 0.1

    # Status icons (customizable)
    icons: dict[str, str] = field(
        default_factory=lambda: {
            "pending": "⏳",
            "working": "🔄",
            "done": "✅",
            "failed": "❌",
            "retrying": "🔁",
        }
    )

    # Tree characters
    tree_chars: dict[str, str] = field(
        default_factory=lambda: {
            "branch": "├── ",
            "last_branch": "└── ",
            "vertical": "│   ",
            "empty": "    ",
        }
    )

    # Execution settings
    default_parallel: bool = True
    max_retries: int = 3
