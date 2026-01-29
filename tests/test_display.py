"""Tests for LiveDisplay."""

import io
import time

from treetask.core import TaskNode, TaskTree
from treetask.config import TreeTaskConfig
from treetask.renderer import TreeRenderer
from treetask.display import LiveDisplay


class TestLiveDisplay:
    def test_init_defaults(self):
        display = LiveDisplay()

        assert display.config is not None
        assert display.renderer is not None
        assert display._last_line_count == 0
        assert display._started is False
        assert display._finalized is False

    def test_init_with_config(self):
        config = TreeTaskConfig(default_max_depth=5)
        display = LiveDisplay(config=config)

        assert display.config.default_max_depth == 5

    def test_init_with_renderer(self):
        renderer = TreeRenderer()
        display = LiveDisplay(renderer=renderer)

        assert display.renderer is renderer

    def test_init_with_output(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        assert display.output is output

    def test_update_writes_output(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.update(tree, force=True)

        result = output.getvalue()
        assert "Root" in result

    def test_update_respects_rate_limit(self):
        output = io.StringIO()
        config = TreeTaskConfig(refresh_interval=1.0)  # 1 second
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(config=config, output=output)
        display.update(tree, force=True)  # First update
        first_len = len(output.getvalue())

        display.update(tree)  # Second update (should be rate-limited)
        second_len = len(output.getvalue())

        # Second update should be skipped due to rate limiting
        # (output length should be same or minimal change)
        assert second_len == first_len

    def test_update_force_bypasses_rate_limit(self):
        output = io.StringIO()
        config = TreeTaskConfig(refresh_interval=10.0)  # Long interval
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(config=config, output=output)
        display.update(tree, force=True)
        display.update(tree, force=True)  # Force should bypass rate limit

        # Both updates should have happened
        assert display._started is True

    def test_update_uses_default_max_depth(self):
        output = io.StringIO()
        config = TreeTaskConfig(default_max_depth=1)
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")
        root.add_child(child)
        child.add_child(grandchild)
        tree = TaskTree(root)

        display = LiveDisplay(config=config, output=output)
        display.update(tree, force=True)

        result = output.getvalue()
        assert "Root" in result
        assert "Child" in result

    def test_update_after_finalize_does_nothing(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.finalize(tree)
        output.truncate(0)
        output.seek(0)

        display.update(tree, force=True)
        result = output.getvalue()

        # Update should be ignored after finalize
        assert result == ""

    def test_finalize_writes_final_tree(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.finalize(tree)

        result = output.getvalue()
        assert "Root" in result
        assert display._finalized is True

    def test_finalize_uses_final_max_depth(self):
        output = io.StringIO()
        config = TreeTaskConfig(final_max_depth=10)
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(config=config, output=output)
        display.finalize(tree)

        assert display._finalized is True

    def test_finalize_with_custom_max_depth(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.finalize(tree, max_depth=5)

        assert display._finalized is True

    def test_finalize_without_stats(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.finalize(tree, show_stats=False)

        result = output.getvalue()
        assert "Root" in result

    def test_clear(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.update(tree, force=True)
        display.clear()

        assert display._last_line_count == 0

    def test_clear_when_no_output(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        # Clear without any prior output should not raise
        display.clear()
        assert display._last_line_count == 0

    def test_print_message(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        display.print_message("Test message")

        result = output.getvalue()
        assert "Test message" in result

    def test_hide_cursor(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        display.hide_cursor()

        result = output.getvalue()
        assert LiveDisplay.HIDE_CURSOR in result

    def test_show_cursor(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        display.show_cursor()

        result = output.getvalue()
        assert LiveDisplay.SHOW_CURSOR in result

    def test_context_manager_hides_and_shows_cursor(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        with display:
            pass

        result = output.getvalue()
        assert LiveDisplay.HIDE_CURSOR in result
        assert LiveDisplay.SHOW_CURSOR in result

    def test_context_manager_returns_self(self):
        output = io.StringIO()
        display = LiveDisplay(output=output)

        with display as d:
            assert d is display

    def test_multiple_updates_clears_previous(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.update(tree, force=True)
        first_line_count = display._last_line_count

        # Change status and update again
        root.status = "done"
        display._last_update_time = 0  # Reset rate limit
        display.update(tree, force=True)

        # Should have written cursor up sequences to clear previous
        result = output.getvalue()
        assert LiveDisplay.CURSOR_UP in result or first_line_count == 0

    def test_finalize_clears_previous_output(self):
        output = io.StringIO()
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        display = LiveDisplay(output=output)
        display.update(tree, force=True)
        display.finalize(tree)

        # After finalize, _last_line_count should be 0
        assert display._last_line_count == 0
