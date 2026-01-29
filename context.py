"""Execution context for managing shared execution state."""

import time
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from .core import TaskNode


@dataclass
class ExecutionContext:
    """Shared execution state across the task tree.

    Manages cancellation, pause/resume, concurrency limits, and timing statistics.
    Created automatically by AsyncExecutor but can be provided for external control.

    Example:
        >>> # External cancellation
        >>> context = ExecutionContext()
        >>> executor = AsyncExecutor(tree, context=context)
        >>>
        >>> # In another task/thread:
        >>> context.cancel(reason="User requested stop")
        >>>
        >>> # Or pause/resume:
        >>> context.pause()
        >>> # ... later ...
        >>> context.resume()
    """

    # Concurrency control
    max_concurrency: Optional[int] = None

    # Internal state (initialized in __post_init__)
    _cancelled: bool = field(default=False, init=False)
    _cancel_reason: Optional[str] = field(default=None, init=False)
    _paused: bool = field(default=False, init=False)
    _pause_event: Optional[anyio.Event] = field(default=None, init=False)
    _semaphore: Optional[anyio.Semaphore] = field(default=None, init=False)
    _cancel_scope: Optional[anyio.CancelScope] = field(default=None, init=False)

    # Timing tracking
    start_time: Optional[float] = field(default=None, init=False)
    end_time: Optional[float] = field(default=None, init=False)
    _completed_durations: list[float] = field(default_factory=list, init=False)
    _active_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Initialize async primitives."""
        # Semaphore for concurrency limiting
        if self.max_concurrency is not None:
            self._semaphore = anyio.Semaphore(self.max_concurrency)

    async def initialize(self) -> None:
        """Initialize async resources. Call at start of execution."""
        self._pause_event = anyio.Event()
        self._pause_event.set()  # Start unpaused
        self.start_time = time.time()

        # Re-initialize semaphore in async context if needed
        if self.max_concurrency is not None and self._semaphore is None:
            self._semaphore = anyio.Semaphore(self.max_concurrency)

    def finalize(self) -> None:
        """Record end time. Call at end of execution."""
        self.end_time = time.time()

    # Cancellation

    def cancel(self, reason: Optional[str] = None) -> None:
        """Request cancellation of all tasks.

        Args:
            reason: Optional reason for cancellation.
        """
        self._cancelled = True
        self._cancel_reason = reason
        if self._cancel_scope is not None:
            self._cancel_scope.cancel()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    @property
    def cancel_reason(self) -> Optional[str]:
        """Get the cancellation reason if cancelled."""
        return self._cancel_reason

    def set_cancel_scope(self, scope: anyio.CancelScope) -> None:
        """Set the cancel scope for the execution.

        Args:
            scope: The anyio CancelScope to use.
        """
        self._cancel_scope = scope

    # Pause/Resume

    def pause(self) -> None:
        """Pause execution. New tasks won't start until resumed."""
        self._paused = True
        if self._pause_event is not None:
            self._pause_event = anyio.Event()  # Reset to unset state

    def resume(self) -> None:
        """Resume paused execution."""
        self._paused = False
        if self._pause_event is not None:
            self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        """Check if execution is paused."""
        return self._paused

    async def wait_if_paused(self) -> None:
        """Wait if execution is paused. Call before starting each task."""
        if self._pause_event is not None:
            await self._pause_event.wait()

    # Concurrency control

    async def acquire_slot(self) -> None:
        """Acquire a concurrency slot. Blocks if at limit."""
        if self._semaphore is not None:
            await self._semaphore.acquire()
        self._active_count += 1

    def release_slot(self) -> None:
        """Release a concurrency slot."""
        self._active_count -= 1
        if self._semaphore is not None:
            self._semaphore.release()

    @property
    def active_count(self) -> int:
        """Get the number of currently active tasks."""
        return self._active_count

    # Timing and ETA

    def record_completion(self, duration: float) -> None:
        """Record a task completion duration for ETA calculation.

        Args:
            duration: Task duration in seconds.
        """
        self._completed_durations.append(duration)

    @property
    def elapsed(self) -> Optional[float]:
        """Get elapsed execution time."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def completed_count(self) -> int:
        """Get the number of completed tasks."""
        return len(self._completed_durations)

    @property
    def average_duration(self) -> Optional[float]:
        """Get the average task duration."""
        if not self._completed_durations:
            return None
        return sum(self._completed_durations) / len(self._completed_durations)

    def estimate_remaining_time(self, pending_count: int) -> Optional[float]:
        """Estimate time remaining based on completed task durations.

        Args:
            pending_count: Number of tasks still pending.

        Returns:
            Estimated seconds remaining, or None if no data.
        """
        avg = self.average_duration
        if avg is None:
            return None
        return avg * pending_count

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with timing and count statistics.
        """
        return {
            "elapsed": self.elapsed,
            "completed_count": self.completed_count,
            "active_count": self.active_count,
            "average_duration": self.average_duration,
            "is_cancelled": self.is_cancelled,
            "is_paused": self.is_paused,
        }


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior.

    Attributes:
        global_timeout: Total execution timeout for the entire tree.
        default_task_timeout: Default timeout for individual tasks.
        cancel_on_timeout: Whether to cancel remaining tasks when one times out.
    """

    global_timeout: Optional[float] = None
    default_task_timeout: Optional[float] = None
    cancel_on_timeout: bool = False
