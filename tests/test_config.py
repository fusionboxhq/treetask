"""Tests for TreeTaskConfig."""

from treetask.config import TreeTaskConfig
from treetask.strategies import FixedDelayRetry, ExponentialBackoffRetry


class TestTreeTaskConfig:
    def test_default_values(self):
        config = TreeTaskConfig()
        assert config.default_max_depth == 2
        assert config.final_max_depth == 3
        assert config.max_retries == 3

    def test_get_retry_strategy_with_explicit_strategy(self):
        """Test that explicit strategy is returned."""
        strategy = ExponentialBackoffRetry()
        config = TreeTaskConfig(default_retry_strategy=strategy)

        result = config.get_retry_strategy()
        assert result is strategy

    def test_get_retry_strategy_with_max_retries(self):
        """Test that FixedDelayRetry is created from max_retries."""
        config = TreeTaskConfig(max_retries=5)

        result = config.get_retry_strategy()
        assert isinstance(result, FixedDelayRetry)
        assert result.max_retries == 5
        assert result.delay == 0

    def test_get_retry_strategy_with_zero_max_retries(self):
        """Test that None is returned when max_retries is 0."""
        config = TreeTaskConfig(max_retries=0)

        result = config.get_retry_strategy()
        assert result is None

    def test_merge_with_basic(self):
        """Test merging two configs."""
        base = TreeTaskConfig(
            default_max_depth=2,
            max_retries=3,
            global_timeout=100.0,
        )
        override = TreeTaskConfig(
            default_max_depth=5,
            global_timeout=50.0,
        )

        merged = base.merge_with(override)

        assert merged.default_max_depth == 5
        assert merged.global_timeout == 50.0

    def test_merge_with_icons(self):
        """Test that icons are merged."""
        base = TreeTaskConfig()
        override = TreeTaskConfig(icons={"custom": "X"})

        merged = base.merge_with(override)

        # Base icons should be preserved
        assert "done" in merged.icons
        # Override icon should be added
        assert merged.icons["custom"] == "X"

    def test_merge_with_strategy(self):
        """Test merging strategies."""
        strategy = ExponentialBackoffRetry()
        base = TreeTaskConfig()
        override = TreeTaskConfig(default_retry_strategy=strategy)

        merged = base.merge_with(override)

        assert merged.default_retry_strategy is strategy

    def test_default_icons(self):
        """Test that default icons are set."""
        config = TreeTaskConfig()

        assert "pending" in config.icons
        assert "working" in config.icons
        assert "done" in config.icons
        assert "failed" in config.icons

    def test_default_tree_chars(self):
        """Test that default tree chars are set."""
        config = TreeTaskConfig()

        assert "branch" in config.tree_chars
        assert "last_branch" in config.tree_chars
        assert "vertical" in config.tree_chars
        assert "empty" in config.tree_chars
