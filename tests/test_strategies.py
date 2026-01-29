"""Tests for retry strategies."""

import pytest
from treetask.strategies import (
    RetryStrategy,
    NoRetry,
    FixedDelayRetry,
    ExponentialBackoffRetry,
    LinearBackoffRetry,
    CustomRetry,
    RetryOnExceptionTypes,
)


class TestNoRetry:
    def test_never_retries(self):
        strategy = NoRetry()
        assert strategy.get_delay(0, ValueError("test")) is None
        assert strategy.get_delay(1, ValueError("test")) is None
        assert strategy.get_delay(10, ValueError("test")) is None

    def test_should_retry_false(self):
        strategy = NoRetry()
        assert strategy.should_retry(0, ValueError("test")) is False


class TestFixedDelayRetry:
    def test_returns_fixed_delay(self):
        strategy = FixedDelayRetry(delay=2.0, max_retries=3)
        assert strategy.get_delay(0, ValueError("test")) == 2.0
        assert strategy.get_delay(1, ValueError("test")) == 2.0
        assert strategy.get_delay(2, ValueError("test")) == 2.0

    def test_stops_after_max_retries(self):
        strategy = FixedDelayRetry(delay=1.0, max_retries=3)
        assert strategy.get_delay(3, ValueError("test")) is None
        assert strategy.get_delay(4, ValueError("test")) is None

    def test_default_values(self):
        strategy = FixedDelayRetry()
        assert strategy.delay == 1.0
        assert strategy.max_retries == 3


class TestExponentialBackoffRetry:
    def test_exponential_increase(self):
        strategy = ExponentialBackoffRetry(
            base_delay=1.0,
            multiplier=2.0,
            max_retries=5,
            jitter=False,
        )
        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(1, ValueError("test")) == 2.0
        assert strategy.get_delay(2, ValueError("test")) == 4.0
        assert strategy.get_delay(3, ValueError("test")) == 8.0

    def test_respects_max_delay(self):
        strategy = ExponentialBackoffRetry(
            base_delay=1.0,
            max_delay=5.0,
            multiplier=2.0,
            max_retries=10,
            jitter=False,
        )
        # 2^3 = 8 > 5, should be capped
        assert strategy.get_delay(3, ValueError("test")) == 5.0

    def test_stops_after_max_retries(self):
        strategy = ExponentialBackoffRetry(max_retries=3, jitter=False)
        assert strategy.get_delay(3, ValueError("test")) is None

    def test_jitter_adds_randomness(self):
        strategy = ExponentialBackoffRetry(
            base_delay=1.0,
            max_retries=5,
            jitter=True,
            jitter_factor=0.5,
        )
        # With jitter, delay should be >= base but vary
        delays = [strategy.get_delay(0, ValueError("test")) for _ in range(10)]
        assert all(d >= 1.0 for d in delays)
        # Should have some variation (not all equal)
        assert len(set(delays)) > 1


class TestLinearBackoffRetry:
    def test_linear_increase(self):
        strategy = LinearBackoffRetry(
            base_delay=1.0,
            increment=1.0,
            max_retries=5,
        )
        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(1, ValueError("test")) == 2.0
        assert strategy.get_delay(2, ValueError("test")) == 3.0
        assert strategy.get_delay(3, ValueError("test")) == 4.0

    def test_respects_max_delay(self):
        strategy = LinearBackoffRetry(
            base_delay=1.0,
            increment=5.0,
            max_delay=10.0,
            max_retries=10,
        )
        assert strategy.get_delay(3, ValueError("test")) == 10.0  # 1 + 3*5 = 16 > 10

    def test_stops_after_max_retries(self):
        strategy = LinearBackoffRetry(max_retries=3)
        assert strategy.get_delay(3, ValueError("test")) is None


class TestCustomRetry:
    def test_calls_custom_function(self):
        def my_retry(attempt: int, error: Exception) -> float | None:
            if attempt >= 2:
                return None
            return attempt * 0.5

        strategy = CustomRetry(my_retry)
        assert strategy.get_delay(0, ValueError("test")) == 0.0
        assert strategy.get_delay(1, ValueError("test")) == 0.5
        assert strategy.get_delay(2, ValueError("test")) is None

    def test_receives_exception(self):
        def my_retry(attempt: int, error: Exception) -> float | None:
            if isinstance(error, ValueError):
                return 1.0
            return None

        strategy = CustomRetry(my_retry)
        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(0, TypeError("test")) is None


class TestRetryOnExceptionTypes:
    def test_only_retries_specified_types(self):
        base = FixedDelayRetry(delay=1.0, max_retries=3)
        strategy = RetryOnExceptionTypes(base, retry_on=(ValueError, TypeError))

        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(0, TypeError("test")) == 1.0
        assert strategy.get_delay(0, RuntimeError("test")) is None

    def test_never_retries_excluded_types(self):
        base = FixedDelayRetry(delay=1.0, max_retries=3)
        strategy = RetryOnExceptionTypes(
            base,
            retry_on=(Exception,),
            no_retry_on=(KeyboardInterrupt, SystemExit),
        )

        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(0, KeyboardInterrupt()) is None

    def test_respects_base_strategy_limits(self):
        base = FixedDelayRetry(delay=1.0, max_retries=2)
        strategy = RetryOnExceptionTypes(base, retry_on=(ValueError,))

        assert strategy.get_delay(0, ValueError("test")) == 1.0
        assert strategy.get_delay(1, ValueError("test")) == 1.0
        assert strategy.get_delay(2, ValueError("test")) is None
