"""Hook system for task execution events."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import TaskNode, TaskTree


class TaskHooks(Protocol):
    """Protocol defining all available task lifecycle hooks.

    Implement this protocol to receive all task events. Methods are optional -
    only implement the ones you need.

    Example:
        >>> class MyHooks:
        ...     def on_node_start(self, node: TaskNode) -> None:
        ...         print(f"Starting {node.name}")
        ...
        ...     def on_node_complete(self, node: TaskNode) -> None:
        ...         print(f"Completed {node.name} in {node.elapsed:.2f}s")
        ...
        >>> hooks = HookDispatcher()
        >>> hooks.register(MyHooks())
    """

    def on_tree_start(self, tree: "TaskTree") -> None:
        """Called when tree execution begins."""
        ...

    def on_tree_complete(self, tree: "TaskTree") -> None:
        """Called when tree execution completes (success or failure)."""
        ...

    def on_node_start(self, node: "TaskNode") -> None:
        """Called when a node starts executing."""
        ...

    def on_node_complete(self, node: "TaskNode") -> None:
        """Called when a node completes (success, failure, or skip)."""
        ...

    def on_retry(self, node: "TaskNode", attempt: int, error: Exception) -> None:
        """Called before a retry attempt.

        Args:
            node: The node being retried.
            attempt: The retry attempt number (1 for first retry).
            error: The exception that triggered the retry.
        """
        ...

    def on_progress_update(
        self, node: "TaskNode", current: int, total: int
    ) -> None:
        """Called when a node's progress is updated.

        Args:
            node: The node whose progress changed.
            current: Current progress value.
            total: Total progress value.
        """
        ...

    def on_child_added(self, parent: "TaskNode", child: "TaskNode") -> None:
        """Called when a child node is dynamically added.

        Args:
            parent: The parent node.
            child: The newly added child node.
        """
        ...

    def on_timeout(self, node: "TaskNode") -> None:
        """Called when a node times out."""
        ...

    def on_cancel(self, node: "TaskNode", reason: Optional[str]) -> None:
        """Called when a node is cancelled.

        Args:
            node: The cancelled node.
            reason: Optional cancellation reason.
        """
        ...

    def on_skip(self, node: "TaskNode", reason: str) -> None:
        """Called when a node is skipped.

        Args:
            node: The skipped node.
            reason: Why the node was skipped (e.g., "condition", "already_done").
        """
        ...

    def on_dependency_ready(self, node: "TaskNode") -> None:
        """Called when all dependencies for a node are satisfied."""
        ...

    def on_error(self, node: "TaskNode", error: Exception) -> None:
        """Called when a node encounters an error (before retry decision).

        Args:
            node: The node that errored.
            error: The exception that occurred.
        """
        ...


# Type for individual hook callbacks
HookCallback = Callable[..., None]


@dataclass
class HookDispatcher:
    """Dispatches events to registered hook handlers.

    Supports both protocol implementations (register a class implementing
    TaskHooks) and individual callbacks (register a function for a specific event).

    Example:
        >>> hooks = HookDispatcher()
        >>>
        >>> # Register individual callbacks
        >>> hooks.on("on_retry", lambda node, attempt, err: print(f"Retry {attempt}"))
        >>> hooks.on("on_timeout", lambda node: send_alert(f"{node.name} timed out"))
        >>>
        >>> # Or register a full protocol implementation
        >>> class MetricsHooks:
        ...     def on_node_complete(self, node):
        ...         metrics.timing("task_duration", node.elapsed)
        ...
        >>> hooks.register(MetricsHooks())
        >>>
        >>> # Use with executor
        >>> executor = AsyncExecutor(tree, hooks=hooks)
    """

    _protocol_handlers: list[Any] = field(default_factory=list)
    _callbacks: dict[str, list[HookCallback]] = field(default_factory=dict)

    def register(self, handler: Any) -> "HookDispatcher":
        """Register a protocol handler.

        The handler should implement some or all methods from TaskHooks.

        Args:
            handler: Object implementing TaskHooks protocol methods.

        Returns:
            Self for chaining.
        """
        self._protocol_handlers.append(handler)
        return self

    def unregister(self, handler: Any) -> "HookDispatcher":
        """Unregister a protocol handler.

        Args:
            handler: Previously registered handler.

        Returns:
            Self for chaining.
        """
        if handler in self._protocol_handlers:
            self._protocol_handlers.remove(handler)
        return self

    def on(self, event: str, callback: HookCallback) -> "HookDispatcher":
        """Register a callback for a specific event.

        Args:
            event: Event name (e.g., "on_retry", "on_node_complete").
            callback: Function to call when event occurs.

        Returns:
            Self for chaining.
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
        return self

    def off(self, event: str, callback: Optional[HookCallback] = None) -> "HookDispatcher":
        """Unregister callbacks for an event.

        Args:
            event: Event name.
            callback: Specific callback to remove, or None to remove all.

        Returns:
            Self for chaining.
        """
        if event not in self._callbacks:
            return self

        if callback is None:
            self._callbacks[event] = []
        elif callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

        return self

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event to all registered handlers.

        Errors in handlers are caught and logged but don't stop other handlers.

        Args:
            event: Event name to emit.
            *args: Positional arguments to pass to handlers.
            **kwargs: Keyword arguments to pass to handlers.
        """
        # Call protocol implementations
        for handler in self._protocol_handlers:
            method = getattr(handler, event, None)
            if method is not None and callable(method):
                try:
                    method(*args, **kwargs)
                except Exception:
                    # Log but don't propagate - hooks shouldn't break execution
                    pass

        # Call individual callbacks
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception:
                # Log but don't propagate
                pass

    def has_handlers(self, event: str) -> bool:
        """Check if any handlers are registered for an event.

        Args:
            event: Event name to check.

        Returns:
            True if at least one handler is registered.
        """
        # Check callbacks
        if self._callbacks.get(event):
            return True

        # Check protocol handlers
        for handler in self._protocol_handlers:
            if hasattr(handler, event) and callable(getattr(handler, event)):
                return True

        return False

    def clear(self) -> "HookDispatcher":
        """Remove all registered handlers.

        Returns:
            Self for chaining.
        """
        self._protocol_handlers.clear()
        self._callbacks.clear()
        return self


def create_logging_hooks(logger: Any) -> "HookDispatcher":
    """Create a HookDispatcher that logs all events.

    Convenience function for debugging.

    Args:
        logger: Logger instance with info/warning/error methods.

    Returns:
        Configured HookDispatcher.
    """
    hooks = HookDispatcher()

    hooks.on("on_tree_start", lambda tree: logger.info(f"Tree execution started: {tree.root.name}"))
    hooks.on("on_tree_complete", lambda tree: logger.info(f"Tree execution completed: {tree.root.name}"))
    hooks.on("on_node_start", lambda node: logger.info(f"Node started: {node.name} (id={node.id})"))
    hooks.on("on_node_complete", lambda node: logger.info(
        f"Node completed: {node.name} status={node.status} elapsed={node.elapsed:.2f}s"
        if node.elapsed else f"Node completed: {node.name} status={node.status}"
    ))
    hooks.on("on_retry", lambda node, attempt, err: logger.warning(
        f"Retry {attempt} for {node.name}: {err}"
    ))
    hooks.on("on_timeout", lambda node: logger.error(f"Timeout: {node.name}"))
    hooks.on("on_cancel", lambda node, reason: logger.warning(f"Cancelled: {node.name} reason={reason}"))
    hooks.on("on_skip", lambda node, reason: logger.info(f"Skipped: {node.name} reason={reason}"))
    hooks.on("on_error", lambda node, err: logger.error(f"Error in {node.name}: {err}"))

    return hooks
