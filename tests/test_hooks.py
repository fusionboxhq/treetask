"""Tests for hooks and event dispatching."""

import pytest
from treetask.hooks import HookDispatcher, create_logging_hooks
from treetask.core import TaskNode, TaskTree


class TestHookDispatcher:
    def test_register_callback(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda x: results.append(x))
        hooks.emit("on_test", "value")

        assert results == ["value"]

    def test_multiple_callbacks(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda: results.append(1))
        hooks.on("on_test", lambda: results.append(2))
        hooks.emit("on_test")

        assert results == [1, 2]

    def test_different_events(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("event_a", lambda: results.append("a"))
        hooks.on("event_b", lambda: results.append("b"))

        hooks.emit("event_a")
        assert results == ["a"]

        hooks.emit("event_b")
        assert results == ["a", "b"]

    def test_emit_with_args_and_kwargs(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda a, b, c=None: results.append((a, b, c)))
        hooks.emit("on_test", 1, 2, c=3)

        assert results == [(1, 2, 3)]

    def test_unregister_callback(self):
        hooks = HookDispatcher()
        results = []

        callback = lambda: results.append(1)
        hooks.on("on_test", callback)
        hooks.off("on_test", callback)
        hooks.emit("on_test")

        assert results == []

    def test_unregister_all_callbacks(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda: results.append(1))
        hooks.on("on_test", lambda: results.append(2))
        hooks.off("on_test")
        hooks.emit("on_test")

        assert results == []

    def test_register_protocol_handler(self):
        hooks = HookDispatcher()
        results = []

        class MyHandler:
            def on_node_start(self, node):
                results.append(f"start:{node.name}")

            def on_node_complete(self, node):
                results.append(f"complete:{node.name}")

        hooks.register(MyHandler())

        node = TaskNode(id="test", name="Test Node")
        hooks.emit("on_node_start", node)
        hooks.emit("on_node_complete", node)

        assert results == ["start:Test Node", "complete:Test Node"]

    def test_unregister_protocol_handler(self):
        hooks = HookDispatcher()
        results = []

        class MyHandler:
            def on_test(self):
                results.append(1)

        handler = MyHandler()
        hooks.register(handler)
        hooks.unregister(handler)
        hooks.emit("on_test")

        assert results == []

    def test_has_handlers(self):
        hooks = HookDispatcher()

        assert hooks.has_handlers("on_test") is False

        hooks.on("on_test", lambda: None)
        assert hooks.has_handlers("on_test") is True

    def test_clear(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda: results.append(1))
        hooks.register(type("Handler", (), {"on_test": lambda self: results.append(2)})())

        hooks.clear()
        hooks.emit("on_test")

        assert results == []

    def test_chaining(self):
        hooks = HookDispatcher()
        results = []

        (hooks
            .on("event1", lambda: results.append(1))
            .on("event2", lambda: results.append(2))
            .on("event1", lambda: results.append(3)))

        hooks.emit("event1")
        assert results == [1, 3]

    def test_callback_error_does_not_stop_others(self):
        hooks = HookDispatcher()
        results = []

        hooks.on("on_test", lambda: results.append(1))
        hooks.on("on_test", lambda: (_ for _ in ()).throw(ValueError("test")))
        hooks.on("on_test", lambda: results.append(3))

        # Should not raise, should continue to other handlers
        hooks.emit("on_test")
        assert results == [1, 3]


class TestTaskHooksProtocol:
    """Test the TaskHooks protocol default implementations."""

    def test_protocol_methods_exist(self):
        from treetask.hooks import TaskHooks

        # Create a minimal implementation
        class MinimalHooks(TaskHooks):
            pass

        hooks = MinimalHooks()

        # All protocol methods should be callable (they're no-ops by default)
        node = TaskNode(id="test", name="Test")
        tree = TaskTree(node)

        # These should not raise - they're default no-op implementations
        hooks.on_tree_start(tree)
        hooks.on_tree_complete(tree)
        hooks.on_node_start(node)
        hooks.on_node_complete(node)
        hooks.on_retry(node, 1, ValueError("test"))
        hooks.on_progress_update(node, 1, 10)
        hooks.on_child_added(node, node)
        hooks.on_timeout(node)
        hooks.on_cancel(node, "reason")
        hooks.on_skip(node, "reason")
        hooks.on_dependency_ready(node)
        hooks.on_error(node, ValueError("test"))


class TestHookDispatcherEdgeCases:
    """Test edge cases for HookDispatcher."""

    def test_off_event_not_registered(self):
        """Test off() when event doesn't exist returns self."""
        hooks = HookDispatcher()

        result = hooks.off("nonexistent_event")

        assert result is hooks  # Should return self for chaining

    def test_emit_protocol_handler_exception_is_caught(self):
        """Test that exceptions in protocol handlers are caught and don't stop others."""
        hooks = HookDispatcher()
        results = []

        class BrokenHandler:
            def on_test(self):
                raise ValueError("Handler error")

        class WorkingHandler:
            def on_test(self):
                results.append("working")

        hooks.register(BrokenHandler())
        hooks.register(WorkingHandler())

        # Should not raise, should continue to other handlers
        hooks.emit("on_test")
        assert results == ["working"]

    def test_has_handlers_protocol_handler(self):
        """Test has_handlers returns True when protocol handler has method."""
        hooks = HookDispatcher()

        class MyHandler:
            def on_custom_event(self):
                pass

        hooks.register(MyHandler())

        assert hooks.has_handlers("on_custom_event") is True
        assert hooks.has_handlers("on_nonexistent") is False

    def test_has_handlers_protocol_handler_non_callable(self):
        """Test has_handlers returns False when attribute exists but is not callable."""
        hooks = HookDispatcher()

        class MyHandler:
            on_attr = "not callable"

        hooks.register(MyHandler())

        assert hooks.has_handlers("on_attr") is False


class TestCreateLoggingHooks:
    def test_creates_hook_dispatcher(self):
        class MockLogger:
            def __init__(self):
                self.messages = []

            def info(self, msg):
                self.messages.append(("info", msg))

            def warning(self, msg):
                self.messages.append(("warning", msg))

            def error(self, msg):
                self.messages.append(("error", msg))

        logger = MockLogger()
        hooks = create_logging_hooks(logger)

        assert isinstance(hooks, HookDispatcher)

        # Test that hooks log correctly
        node = TaskNode(id="test", name="Test")
        hooks.emit("on_node_start", node)

        assert len(logger.messages) == 1
        assert logger.messages[0][0] == "info"
        assert "Test" in logger.messages[0][1]
