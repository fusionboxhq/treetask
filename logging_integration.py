"""Structured logging integration for task execution."""

import logging
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import TaskNode, TaskTree


@dataclass
class TreeTaskLogger:
    """Structured logging adapter for tree task execution.

    Implements the TaskHooks protocol for automatic logging of task events.
    Uses Python's standard logging with structured extra data.

    Example:
        >>> import logging
        >>> logging.basicConfig(level=logging.INFO)
        >>>
        >>> logger = TreeTaskLogger(logger_name="my_pipeline", level="DEBUG")
        >>> executor = AsyncExecutor(tree)
        >>> executor.hooks.register(logger)
        >>>
        >>> # Logs will include structured data:
        >>> # INFO my_pipeline: Node started node_id=task1 node_name=Fetch Data depth=1
        >>> # INFO my_pipeline: Node completed node_id=task1 status=done elapsed=2.34
    """

    logger_name: str = "treetask"
    level: str = "INFO"
    include_data: bool = False  # Include node.data in logs
    _logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        """Initialize the logger."""
        self._logger = logging.getLogger(self.logger_name)
        self._logger.setLevel(getattr(logging, self.level.upper()))

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying logger."""
        if self._logger is None:
            self._logger = logging.getLogger(self.logger_name)
        return self._logger

    def _format_extra(self, **kwargs: Any) -> dict[str, Any]:
        """Format extra data for structured logging."""
        return {k: v for k, v in kwargs.items() if v is not None}

    # TaskHooks protocol implementation

    def on_tree_start(self, tree: "TaskTree") -> None:
        """Log tree execution start."""
        self.logger.info(
            "Tree execution started",
            extra=self._format_extra(
                root_id=tree.root.id,
                root_name=tree.root.name,
            ),
        )

    def on_tree_complete(self, tree: "TaskTree") -> None:
        """Log tree execution completion."""
        stats = tree.get_stats()
        self.logger.info(
            "Tree execution completed",
            extra=self._format_extra(
                root_id=tree.root.id,
                root_name=tree.root.name,
                total_nodes=stats.get("total"),
                done=stats.get("done"),
                failed=stats.get("failed"),
            ),
        )

    def on_node_start(self, node: "TaskNode") -> None:
        """Log node execution start."""
        extra = self._format_extra(
            node_id=node.id,
            node_name=node.name,
            depth=node.get_depth(),
            parallel=node.parallel,
        )
        if self.include_data and node.data:
            extra["data"] = node.data

        self.logger.info("Node started", extra=extra)

    def on_node_complete(self, node: "TaskNode") -> None:
        """Log node execution completion."""
        extra = self._format_extra(
            node_id=node.id,
            node_name=node.name,
            status=node.status,
            elapsed=round(node.elapsed, 3) if node.elapsed else None,
            retry_count=node.retry_count if node.retry_count > 0 else None,
        )
        if node.error:
            extra["error"] = node.error[:200]  # Truncate long errors

        log_level = logging.INFO if node.status == "done" else logging.WARNING
        self.logger.log(log_level, "Node completed", extra=extra)

    def on_retry(self, node: "TaskNode", attempt: int, error: Exception) -> None:
        """Log retry attempt."""
        self.logger.warning(
            f"Retry attempt {attempt}",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                attempt=attempt,
                error_type=type(error).__name__,
                error_message=str(error)[:200],
            ),
        )

    def on_progress_update(
        self, node: "TaskNode", current: int, total: int
    ) -> None:
        """Log progress update (debug level)."""
        self.logger.debug(
            "Progress updated",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                progress_current=current,
                progress_total=total,
                progress_percent=round(current / total * 100, 1) if total > 0 else 0,
            ),
        )

    def on_child_added(self, parent: "TaskNode", child: "TaskNode") -> None:
        """Log dynamic child addition (debug level)."""
        self.logger.debug(
            "Child node added",
            extra=self._format_extra(
                parent_id=parent.id,
                parent_name=parent.name,
                child_id=child.id,
                child_name=child.name,
            ),
        )

    def on_timeout(self, node: "TaskNode") -> None:
        """Log node timeout."""
        self.logger.error(
            "Node timed out",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                timeout=node.timeout,
                elapsed=round(node.elapsed, 3) if node.elapsed else None,
            ),
        )

    def on_cancel(self, node: "TaskNode", reason: Optional[str]) -> None:
        """Log node cancellation."""
        self.logger.warning(
            "Node cancelled",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                reason=reason,
            ),
        )

    def on_skip(self, node: "TaskNode", reason: str) -> None:
        """Log node skip."""
        self.logger.info(
            "Node skipped",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                reason=reason,
            ),
        )

    def on_dependency_ready(self, node: "TaskNode") -> None:
        """Log dependency resolution (debug level)."""
        self.logger.debug(
            "Dependencies satisfied",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
            ),
        )

    def on_error(self, node: "TaskNode", error: Exception) -> None:
        """Log node error."""
        self.logger.error(
            f"Node error: {type(error).__name__}",
            extra=self._format_extra(
                node_id=node.id,
                node_name=node.name,
                error_type=type(error).__name__,
                error_message=str(error)[:500],
            ),
            exc_info=True,
        )


class StructuredFormatter(logging.Formatter):
    """Log formatter that includes extra fields in a structured format.

    Example output:
        2024-01-15 10:30:45 INFO treetask: Node started [node_id=task1 node_name=Fetch depth=1]

    Usage:
        >>> handler = logging.StreamHandler()
        >>> handler.setFormatter(StructuredFormatter())
        >>> logging.getLogger("treetask").addHandler(handler)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with extra fields."""
        # Get base message
        message = super().format(record)

        # Extract extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'message', 'asctime',
        }

        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith('_')
        }

        if extra_fields:
            extra_str = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            message = f"{message} [{extra_str}]"

        return message


def configure_treetask_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    structured: bool = True,
) -> logging.Logger:
    """Configure logging for treetask.

    Convenience function to set up logging with sensible defaults.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        format_string: Optional custom format string.
        structured: Whether to include extra fields in output.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("treetask")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if format_string:
        formatter = logging.Formatter(format_string)
    elif structured:
        formatter = StructuredFormatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
