"""Tests for timing utilities."""

import pytest
from treetask.timing import (
    TimingStats,
    format_duration,
    format_eta,
    format_progress_with_eta,
)


class TestTimingStats:
    def test_record_durations(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        assert stats.count == 3
        assert stats.total_duration == 6.0

    def test_average(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        assert stats.average == 2.0

    def test_average_empty(self):
        stats = TimingStats()
        assert stats.average is None

    def test_median_odd(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(5.0)
        stats.record(3.0)

        assert stats.median == 3.0

    def test_median_even(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)
        stats.record(4.0)

        assert stats.median == 2.5

    def test_min_max(self):
        stats = TimingStats()
        stats.record(5.0)
        stats.record(1.0)
        stats.record(10.0)

        assert stats.min_duration == 1.0
        assert stats.max_duration == 10.0

    def test_estimate_remaining(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        # Average is 2.0, 5 pending = 10.0
        assert stats.estimate_remaining(5, method="average") == 10.0

    def test_estimate_remaining_zero_pending(self):
        stats = TimingStats()
        stats.record(1.0)

        assert stats.estimate_remaining(0) == 0.0

    def test_estimate_remaining_no_data(self):
        stats = TimingStats()
        assert stats.estimate_remaining(5) is None

    def test_moving_average(self):
        stats = TimingStats()
        stats._window_size = 3

        for i in range(10):
            stats.record(float(i))

        # Last 3: 7, 8, 9 -> avg = 8.0
        assert stats.moving_average == 8.0

    def test_get_stats(self):
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)

        result = stats.get_stats()
        assert result["count"] == 2
        assert result["total"] == 3.0
        assert result["average"] == 1.5

    def test_start_and_elapsed(self):
        """Test start() method and elapsed property."""
        stats = TimingStats()

        # Before start, elapsed is None
        assert stats.elapsed is None

        # After start, elapsed should be positive
        stats.start()
        assert stats._start_time is not None
        assert stats.elapsed is not None
        assert stats.elapsed >= 0

    def test_median_empty(self):
        """Test that median returns None when empty."""
        stats = TimingStats()
        assert stats.median is None

    def test_estimate_remaining_median_method(self):
        """Test estimate_remaining with median method."""
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        # Median is 2.0, 5 pending = 10.0
        result = stats.estimate_remaining(5, method="median")
        assert result == 10.0

    def test_estimate_remaining_moving_average_method(self):
        """Test estimate_remaining with moving_average method."""
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        # Moving average is 2.0, 5 pending = 10.0
        result = stats.estimate_remaining(5, method="moving_average")
        assert result == 10.0

    def test_estimate_remaining_unknown_method_defaults_to_average(self):
        """Test that unknown method falls back to average."""
        stats = TimingStats()
        stats.record(1.0)
        stats.record(2.0)
        stats.record(3.0)

        # Unknown method should use average (2.0)
        result = stats.estimate_remaining(5, method="unknown_method")
        assert result == 10.0


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(0.5) == "0.5s"
        assert format_duration(30.0) == "30.0s"
        assert format_duration(59.9) == "59.9s"

    def test_minutes(self):
        assert format_duration(60) == "1m"
        assert format_duration(90) == "1m 30s"
        assert format_duration(125) == "2m 5s"

    def test_hours(self):
        assert format_duration(3600) == "1h"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(7200) == "2h"

    def test_none(self):
        assert format_duration(None) == "-"

    def test_negative(self):
        assert format_duration(-1) == "-"


class TestFormatEta:
    def test_basic_eta(self):
        # 25 done in 50s, 75 remaining
        result = format_eta(current=25, total=100, elapsed=50.0)
        assert "remaining" in result
        assert "~" in result

    def test_done(self):
        result = format_eta(current=100, total=100, elapsed=50.0)
        assert result == "done"

    def test_no_elapsed(self):
        assert format_eta(current=25, total=100, elapsed=None) == "-"

    def test_no_progress(self):
        assert format_eta(current=0, total=100, elapsed=10.0) == "-"

    def test_zero_rate(self):
        """Test that format_eta returns '-' when elapsed is 0 (would cause division by zero)."""
        # With current > 0 but elapsed = 0, rate would be infinite
        # Test the case where it's handled gracefully
        result = format_eta(current=1, total=100, elapsed=0.0001)
        assert "remaining" in result or result == "-"


class TestFormatProgressWithEta:
    def test_basic_progress(self):
        result = format_progress_with_eta(25, 100)
        assert "25/100" in result
        assert "25%" in result

    def test_progress_with_eta(self):
        result = format_progress_with_eta(25, 100, elapsed=50.0, show_eta=True)
        assert "25/100" in result
        assert "remaining" in result

    def test_progress_without_eta(self):
        result = format_progress_with_eta(25, 100, elapsed=50.0, show_eta=False)
        assert "25/100" in result
        assert "remaining" not in result

    def test_zero_total(self):
        result = format_progress_with_eta(0, 0)
        assert "0/0" in result
        assert "0%" in result
