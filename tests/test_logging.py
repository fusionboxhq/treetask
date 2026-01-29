"""Tests for logging integration."""

import logging
from io import StringIO

from treetask.core import TaskNode, TaskTree
from treetask.logging_integration import (
    TreeTaskLogger,
    StructuredFormatter,
    configure_treetask_logging,
)


class TestTreeTaskLogger:
    def test_init_defaults(self):
        logger = TreeTaskLogger()

        assert logger.logger_name == "treetask"
        assert logger.level == "INFO"
        assert logger.include_data is False

    def test_init_custom(self):
        logger = TreeTaskLogger(
            logger_name="myapp",
            level="DEBUG",
            include_data=True,
        )

        assert logger.logger_name == "myapp"
        assert logger.level == "DEBUG"
        assert logger.include_data is True

    def test_logger_property(self):
        logger = TreeTaskLogger(logger_name="test_logger")
        assert logger.logger is not None
        assert logger.logger.name == "test_logger"

    def test_on_tree_start(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_tree_start")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        logger.on_tree_start(tree)

        result = output.getvalue()
        assert "started" in result.lower()

    def test_on_tree_complete(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_tree_complete")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        logger.on_tree_complete(tree)

        result = output.getvalue()
        assert "completed" in result.lower() or "complete" in result.lower()

    def test_on_node_start(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_node_start")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        node = TaskNode(id="test", name="Test Node")

        logger.on_node_start(node)

        result = output.getvalue()
        assert "started" in result.lower()

    def test_on_node_start_with_data(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(StructuredFormatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_node_data", include_data=True)
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        node = TaskNode(id="test", name="Test Node", data={"key": "value"})

        logger.on_node_start(node)

        result = output.getvalue()
        assert "started" in result.lower()

    def test_on_node_complete(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_node_complete")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        node = TaskNode(id="test", name="Test Node", status="done")

        logger.on_node_complete(node)

        result = output.getvalue()
        assert "completed" in result.lower() or "complete" in result.lower()

    def test_on_node_complete_with_error(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_node_error")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.WARNING)

        node = TaskNode(id="test", name="Test Node", status="failed", error="Test error")

        logger.on_node_complete(node)

        # Should log at warning level for failed status
        result = output.getvalue()
        assert len(result) > 0

    def test_on_retry(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_retry")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.WARNING)

        node = TaskNode(id="test", name="Test Node")
        error = ValueError("Test error")

        logger.on_retry(node, attempt=2, error=error)

        result = output.getvalue()
        assert "retry" in result.lower() or "2" in result

    def test_on_progress_update(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_progress")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

        node = TaskNode(id="test", name="Test Node")

        logger.on_progress_update(node, current=5, total=10)

        result = output.getvalue()
        assert "progress" in result.lower()

    def test_on_child_added(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_child")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

        parent = TaskNode(id="parent", name="Parent")
        child = TaskNode(id="child", name="Child")

        logger.on_child_added(parent, child)

        result = output.getvalue()
        assert "child" in result.lower() or "added" in result.lower()

    def test_on_timeout(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_timeout")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.ERROR)

        node = TaskNode(id="test", name="Test Node", timeout=30.0)

        logger.on_timeout(node)

        result = output.getvalue()
        assert "timeout" in result.lower() or "timed" in result.lower()

    def test_on_cancel(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_cancel")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.WARNING)

        node = TaskNode(id="test", name="Test Node")

        logger.on_cancel(node, reason="User cancelled")

        result = output.getvalue()
        assert "cancel" in result.lower()

    def test_on_skip(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_skip")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        node = TaskNode(id="test", name="Test Node")

        logger.on_skip(node, reason="condition false")

        result = output.getvalue()
        assert "skip" in result.lower()

    def test_on_dependency_ready(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_dependency")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.DEBUG)

        node = TaskNode(id="test", name="Test Node")

        logger.on_dependency_ready(node)

        result = output.getvalue()
        assert "dependenc" in result.lower() or "satisfied" in result.lower()

    def test_on_error(self):
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = TreeTaskLogger(logger_name="test_error")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.ERROR)

        node = TaskNode(id="test", name="Test Node")
        error = RuntimeError("Something went wrong")

        logger.on_error(node, error)

        result = output.getvalue()
        assert "error" in result.lower()


class TestStructuredFormatter:
    def test_format_without_extra(self):
        formatter = StructuredFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        # Result should contain the message (may or may not have extra brackets)
        assert "Test message" in result

    def test_format_with_extra(self):
        formatter = StructuredFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.node_id = "test_node"
        record.status = "done"

        result = formatter.format(record)

        assert "Test message" in result
        assert "node_id=test_node" in result
        assert "status=done" in result

    def test_format_excludes_standard_attrs(self):
        formatter = StructuredFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should not include standard attributes
        assert "name=" not in result
        assert "levelname=" not in result


class TestConfigureTreetaskLogging:
    def test_configure_default(self):
        logger = configure_treetask_logging()

        assert logger.name == "treetask"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1

    def test_configure_custom_level(self):
        logger = configure_treetask_logging(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_configure_structured(self):
        logger = configure_treetask_logging(structured=True)

        handler = logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_configure_not_structured(self):
        logger = configure_treetask_logging(structured=False)

        handler = logger.handlers[0]
        assert not isinstance(handler.formatter, StructuredFormatter)

    def test_configure_custom_format(self):
        logger = configure_treetask_logging(format_string="%(levelname)s: %(message)s")

        handler = logger.handlers[0]
        assert handler.formatter._fmt == "%(levelname)s: %(message)s"

    def test_configure_clears_existing_handlers(self):
        # Add a handler first
        logger = logging.getLogger("treetask")
        logger.addHandler(logging.StreamHandler())
        initial_count = len(logger.handlers)

        # Configure should clear existing handlers
        configure_treetask_logging()

        assert len(logger.handlers) == 1


class TestTreeTaskLoggerEdgeCases:
    """Test edge cases for TreeTaskLogger."""

    def test_logger_property_when_not_initialized(self):
        """Test logger property creates logger if _logger is None."""
        logger_obj = TreeTaskLogger(logger_name="test_lazy_init")

        # Force _logger to None
        logger_obj._logger = None

        # Accessing .logger should recreate it
        result = logger_obj.logger

        assert result is not None
        assert result.name == "test_lazy_init"
