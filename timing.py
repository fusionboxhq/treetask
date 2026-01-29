"""Timing and ETA estimation utilities."""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingStats:
    """Accumulated timing statistics for ETA estimation.

    Tracks completed task durations and provides ETA calculations
    using various estimation strategies.

    Example:
        >>> stats = TimingStats()
        >>> stats.record(1.5)  # Task took 1.5s
        >>> stats.record(2.0)  # Task took 2.0s
        >>> eta = stats.estimate_remaining(pending_count=10)
        >>> print(f"ETA: {eta:.1f}s")
    """

    _durations: list[float] = field(default_factory=list)
    _start_time: Optional[float] = field(default=None)
    _window_size: int = 50  # For moving average

    def start(self) -> None:
        """Mark the start of execution."""
        self._start_time = time.time()

    def record(self, duration: float) -> None:
        """Record a completed task duration.

        Args:
            duration: Task duration in seconds.
        """
        self._durations.append(duration)

    @property
    def elapsed(self) -> Optional[float]:
        """Get elapsed time since start."""
        if self._start_time is None:
            return None
        return time.time() - self._start_time

    @property
    def count(self) -> int:
        """Get the number of recorded durations."""
        return len(self._durations)

    @property
    def total_duration(self) -> float:
        """Get the sum of all recorded durations."""
        return sum(self._durations)

    @property
    def average(self) -> Optional[float]:
        """Get the average duration."""
        if not self._durations:
            return None
        return sum(self._durations) / len(self._durations)

    @property
    def moving_average(self) -> Optional[float]:
        """Get the moving average of recent durations."""
        if not self._durations:
            return None
        recent = self._durations[-self._window_size:]
        return sum(recent) / len(recent)

    @property
    def median(self) -> Optional[float]:
        """Get the median duration."""
        if not self._durations:
            return None
        sorted_durations = sorted(self._durations)
        n = len(sorted_durations)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_durations[mid - 1] + sorted_durations[mid]) / 2
        return sorted_durations[mid]

    @property
    def min_duration(self) -> Optional[float]:
        """Get the minimum duration."""
        return min(self._durations) if self._durations else None

    @property
    def max_duration(self) -> Optional[float]:
        """Get the maximum duration."""
        return max(self._durations) if self._durations else None

    def estimate_remaining(
        self,
        pending_count: int,
        method: str = "moving_average",
    ) -> Optional[float]:
        """Estimate time remaining for pending tasks.

        Args:
            pending_count: Number of tasks still pending.
            method: Estimation method - "average", "moving_average", or "median".

        Returns:
            Estimated seconds remaining, or None if insufficient data.
        """
        if pending_count <= 0:
            return 0.0

        if method == "average":
            avg = self.average
        elif method == "moving_average":
            avg = self.moving_average
        elif method == "median":
            avg = self.median
        else:
            avg = self.average

        if avg is None:
            return None

        return avg * pending_count

    def get_stats(self) -> dict[str, Optional[float]]:
        """Get all timing statistics.

        Returns:
            Dictionary with timing statistics.
        """
        return {
            "count": self.count,
            "total": self.total_duration,
            "elapsed": self.elapsed,
            "average": self.average,
            "moving_average": self.moving_average,
            "median": self.median,
            "min": self.min_duration,
            "max": self.max_duration,
        }


def format_duration(seconds: Optional[float]) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds, or None.

    Returns:
        Formatted string like "1.5s", "2m 30s", "1h 15m", or "-" if None.

    Example:
        >>> format_duration(90.5)
        '1m 30s'
        >>> format_duration(3665)
        '1h 1m'
    """
    if seconds is None:
        return "-"

    if seconds < 0:
        return "-"

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def format_eta(
    current: int,
    total: int,
    elapsed: Optional[float],
) -> str:
    """Format ETA based on progress and elapsed time.

    Args:
        current: Current progress (completed count).
        total: Total count.
        elapsed: Elapsed time in seconds.

    Returns:
        Formatted ETA string, or "-" if cannot estimate.

    Example:
        >>> format_eta(current=25, total=100, elapsed=30.0)
        '~1m 30s remaining'
    """
    if elapsed is None or current <= 0 or total <= 0:
        return "-"

    remaining_count = total - current
    if remaining_count <= 0:
        return "done"

    # Calculate rate and ETA
    rate = current / elapsed  # items per second
    if rate <= 0:
        return "-"

    eta_seconds = remaining_count / rate
    return f"~{format_duration(eta_seconds)} remaining"


def format_progress_with_eta(
    current: int,
    total: int,
    elapsed: Optional[float] = None,
    show_eta: bool = True,
) -> str:
    """Format progress with optional ETA.

    Args:
        current: Current progress value.
        total: Total progress value.
        elapsed: Optional elapsed time for ETA calculation.
        show_eta: Whether to include ETA.

    Returns:
        Formatted progress string.

    Example:
        >>> format_progress_with_eta(25, 100, elapsed=30.0)
        'Progress: 25/100 (25%) ~1m 30s remaining'
    """
    if total <= 0:
        return "Progress: 0/0 (0%)"

    percentage = int((current / total) * 100)
    base = f"Progress: {current}/{total} ({percentage}%)"

    if show_eta and elapsed is not None and current > 0:
        remaining = total - current
        if remaining > 0:
            rate = current / elapsed
            if rate > 0:
                eta_seconds = remaining / rate
                base += f" ~{format_duration(eta_seconds)} remaining"

    return base
