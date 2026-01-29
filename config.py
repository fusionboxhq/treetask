"""Configuration for TreeTask."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .strategies import RetryStrategy


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
        global_timeout: Total execution timeout for the entire tree.
        default_task_timeout: Default timeout for individual tasks.
        max_concurrency: Maximum concurrent tasks (None = unlimited).
        default_retry_strategy: Default retry strategy for all tasks.
        enable_logging: Whether to enable built-in logging.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        logger_name: Name for the logger.
        show_eta: Whether to show ETA in progress display.
    """

    # Display settings
    default_max_depth: int = 2
    final_max_depth: int = 3
    refresh_interval: float = 0.1
    show_eta: bool = True

    # Status icons (customizable)
    icons: dict[str, str] = field(
        default_factory=lambda: {
            "pending": "⏳",
            "working": "🔄",
            "done": "✅",
            "failed": "❌",
            "retrying": "🔁",
            "cancelled": "🚫",
            "skipped": "⏭️",
            "timed_out": "⏰",
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

    # Timeout settings (Feature 1)
    global_timeout: Optional[float] = None
    default_task_timeout: Optional[float] = None

    # Concurrency settings (Feature 3)
    max_concurrency: Optional[int] = None

    # Retry strategy (Feature 5)
    default_retry_strategy: Optional["RetryStrategy"] = None

    # Logging settings (Feature 15)
    enable_logging: bool = False
    log_level: str = "INFO"
    logger_name: str = "treetask"

    def get_retry_strategy(self) -> Optional["RetryStrategy"]:
        """Get the configured retry strategy.

        Returns the explicit strategy if set, otherwise creates a default
        FixedDelayRetry with no delay based on max_retries.
        """
        if self.default_retry_strategy is not None:
            return self.default_retry_strategy

        # Create default strategy based on max_retries
        if self.max_retries > 0:
            from .strategies import FixedDelayRetry
            return FixedDelayRetry(delay=0, max_retries=self.max_retries)

        return None

    def merge_with(self, other: "TreeTaskConfig") -> "TreeTaskConfig":
        """Create a new config by merging with another.

        Values from `other` take precedence where set.

        Args:
            other: Config to merge with.

        Returns:
            New merged config.
        """
        return TreeTaskConfig(
            default_max_depth=other.default_max_depth or self.default_max_depth,
            final_max_depth=other.final_max_depth or self.final_max_depth,
            refresh_interval=other.refresh_interval or self.refresh_interval,
            show_eta=other.show_eta if other.show_eta is not None else self.show_eta,
            icons={**self.icons, **other.icons},
            tree_chars={**self.tree_chars, **other.tree_chars},
            default_parallel=other.default_parallel if other.default_parallel is not None else self.default_parallel,
            max_retries=other.max_retries if other.max_retries is not None else self.max_retries,
            global_timeout=other.global_timeout or self.global_timeout,
            default_task_timeout=other.default_task_timeout or self.default_task_timeout,
            max_concurrency=other.max_concurrency or self.max_concurrency,
            default_retry_strategy=other.default_retry_strategy or self.default_retry_strategy,
            enable_logging=other.enable_logging if other.enable_logging is not None else self.enable_logging,
            log_level=other.log_level or self.log_level,
            logger_name=other.logger_name or self.logger_name,
        )
