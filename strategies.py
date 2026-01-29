"""Retry strategies for task execution."""

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional


class RetryStrategy(ABC):
    """Base class for retry strategies.

    Retry strategies determine the delay between retry attempts and when
    to stop retrying. Implement get_delay() to create custom strategies.

    Example:
        >>> strategy = ExponentialBackoffRetry(base_delay=1.0, max_retries=5)
        >>> delay = strategy.get_delay(attempt=2, error=ValueError("oops"))
        >>> if delay is not None:
        ...     await anyio.sleep(delay)
    """

    @abstractmethod
    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Get the delay before the next retry attempt.

        Args:
            attempt: The current attempt number (0-indexed, so first retry is attempt=1).
            error: The exception that caused the failure.

        Returns:
            The delay in seconds before the next retry, or None to stop retrying.
        """
        ...

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if another retry should be attempted.

        Args:
            attempt: The current attempt number.
            error: The exception that caused the failure.

        Returns:
            True if another retry should be attempted.
        """
        return self.get_delay(attempt, error) is not None


@dataclass
class NoRetry(RetryStrategy):
    """Strategy that never retries."""

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Never retry."""
        return None


@dataclass
class FixedDelayRetry(RetryStrategy):
    """Fixed delay between retry attempts.

    Example:
        >>> strategy = FixedDelayRetry(delay=2.0, max_retries=3)
        >>> # Will retry up to 3 times with 2 second delays
    """

    delay: float = 1.0
    max_retries: int = 3

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Get fixed delay if within retry limit."""
        if attempt >= self.max_retries:
            return None
        return self.delay


@dataclass
class ExponentialBackoffRetry(RetryStrategy):
    """Exponential backoff with optional jitter.

    The delay increases exponentially: base_delay * (multiplier ** attempt)
    Optionally adds random jitter to prevent thundering herd.

    Example:
        >>> strategy = ExponentialBackoffRetry(
        ...     base_delay=1.0,
        ...     max_delay=60.0,
        ...     multiplier=2.0,
        ...     max_retries=5,
        ...     jitter=True,
        ... )
        >>> # Delays: ~1s, ~2s, ~4s, ~8s, ~16s (capped at 60s)
    """

    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    max_retries: int = 5
    jitter: bool = True
    jitter_factor: float = 0.5  # Random factor between 0 and this value

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Get exponentially increasing delay with optional jitter."""
        if attempt >= self.max_retries:
            return None

        # Calculate base exponential delay
        delay = self.base_delay * (self.multiplier ** attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            jitter = random.uniform(0, self.jitter_factor * delay)
            delay += jitter

        return delay


@dataclass
class LinearBackoffRetry(RetryStrategy):
    """Linear backoff - delay increases linearly with each attempt.

    Example:
        >>> strategy = LinearBackoffRetry(
        ...     base_delay=1.0,
        ...     increment=1.0,
        ...     max_retries=5,
        ... )
        >>> # Delays: 1s, 2s, 3s, 4s, 5s
    """

    base_delay: float = 1.0
    increment: float = 1.0
    max_delay: float = 60.0
    max_retries: int = 5

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Get linearly increasing delay."""
        if attempt >= self.max_retries:
            return None

        delay = self.base_delay + (self.increment * attempt)
        return min(delay, self.max_delay)


class CustomRetry(RetryStrategy):
    """User-defined retry logic via a callable.

    The callable receives the attempt number and exception, and should
    return the delay in seconds or None to stop retrying.

    Example:
        >>> def my_retry(attempt: int, error: Exception) -> Optional[float]:
        ...     if isinstance(error, RateLimitError):
        ...         return error.retry_after  # Use server-provided delay
        ...     if attempt >= 3:
        ...         return None
        ...     return 2 ** attempt
        ...
        >>> strategy = CustomRetry(my_retry)
    """

    def __init__(self, func: Callable[[int, Exception], Optional[float]]):
        """Initialize with a retry function.

        Args:
            func: Function that takes (attempt, error) and returns delay or None.
        """
        self.func = func

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Delegate to the user-provided function."""
        return self.func(attempt, error)


class RetryOnExceptionTypes(RetryStrategy):
    """Only retry for specific exception types.

    Wraps another strategy and only retries if the exception matches
    one of the specified types.

    Example:
        >>> base = ExponentialBackoffRetry(max_retries=3)
        >>> strategy = RetryOnExceptionTypes(
        ...     base,
        ...     retry_on=(ConnectionError, TimeoutError),
        ... )
        >>> # Only retries ConnectionError and TimeoutError
    """

    def __init__(
        self,
        strategy: RetryStrategy,
        retry_on: tuple[type[Exception], ...],
        no_retry_on: Optional[tuple[type[Exception], ...]] = None,
    ):
        """Initialize with a base strategy and exception filters.

        Args:
            strategy: The underlying retry strategy.
            retry_on: Exception types that should trigger a retry.
            no_retry_on: Exception types that should never be retried.
        """
        self.strategy = strategy
        self.retry_on = retry_on
        self.no_retry_on = no_retry_on or ()

    def get_delay(self, attempt: int, error: Exception) -> Optional[float]:
        """Get delay only if exception type matches."""
        # Never retry these exceptions
        if isinstance(error, self.no_retry_on):
            return None

        # Only retry these exceptions
        if not isinstance(error, self.retry_on):
            return None

        return self.strategy.get_delay(attempt, error)
