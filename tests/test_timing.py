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
