"""Tests for AsyncExecutor."""

import pytest
import anyio
from treetask.core import TaskNode, TaskTree
from treetask.config import TreeTaskConfig
from treetask.executor import AsyncExecutor, ExecutionResult
from treetask.hooks import HookDispatcher
from treetask.strategies import FixedDelayRetry, ExponentialBackoffRetry


async def success_task(node):
    node.progress = (1, 1)
    return {"status": "success"}


async def failing_task(node):
    raise ValueError("Task failed")


async def slow_task(node):
    await anyio.sleep(10)
    return {"status": "done"}


class Counter:
    def __init__(self):
        self.count = 0

    async def task(self, node):
        self.count += 1
        return {"count": self.count}


class FailThenSucceed:
    def __init__(self, fail_times=2):
        self.attempts = 0
        self.fail_times = fail_times

    async def task(self, node):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise ValueError(f"Attempt {self.attempts} failed")
        return {"attempts": self.attempts}


@pytest.mark.anyio
class TestAsyncExecutor:
    async def test_basic_execution(self):
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"
        assert root.result == {"status": "success"}

    async def test_executes_children(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1", task_fn=success_task)
        child2 = TaskNode(id="child2", name="Child 2", task_fn=success_task)
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"
        assert child1.status == "done"
        assert child2.status == "done"

    async def test_parallel_execution(self):
        counter = Counter()
        root = TaskNode(id="root", name="Root", parallel=True)
        for i in range(5):
            child = TaskNode(id=f"child{i}", name=f"Child {i}", task_fn=counter.task)
            root.add_child(child)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert counter.count == 5
        assert all(c.status == "done" for c in root.children)

    async def test_sequential_execution(self):
        results = []

        async def ordered_task(node):
            results.append(node.id)
            return {}

        root = TaskNode(id="root", name="Root", parallel=False)
        for i in range(3):
            child = TaskNode(id=f"child{i}", name=f"Child {i}", task_fn=ordered_task)
            root.add_child(child)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # Sequential execution preserves order
        assert results == ["child0", "child1", "child2"]

    async def test_on_update_callback(self):
        updates = []
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree, on_update=lambda t: updates.append(t.root.status))
        await executor.run()

        assert "working" in updates
        assert "done" in updates

    async def test_on_node_start_callback(self):
        started = []
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree, on_node_start=lambda n: started.append(n.id))
        await executor.run()

        assert "root" in started

    async def test_on_node_complete_callback(self):
        completed = []
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree, on_node_complete=lambda n: completed.append(n.id))
        await executor.run()

        assert "root" in completed

    async def test_timing_recorded(self):
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.start_time is not None
        assert root.end_time is not None
        assert root.elapsed is not None
        assert root.elapsed >= 0

    async def test_result_stored(self):
        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.result == {"status": "success"}

    async def test_result_merged_into_data(self):
        root = TaskNode(id="root", name="Root", task_fn=success_task, data={"existing": "value"})
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.data["existing"] == "value"
        assert root.data["status"] == "success"


@pytest.mark.anyio
class TestRetryBehavior:
    async def test_retries_on_failure(self):
        handler = FailThenSucceed(fail_times=2)
        config = TreeTaskConfig(max_retries=3)
        root = TaskNode(id="root", name="Root", task_fn=handler.task)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"
        assert handler.attempts == 3
        assert root.retry_count == 2

    async def test_fails_after_max_retries(self):
        handler = FailThenSucceed(fail_times=10)
        config = TreeTaskConfig(max_retries=2)
        root = TaskNode(id="root", name="Root", task_fn=handler.task)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        with pytest.raises(ValueError):
            await executor.run()

        assert root.status == "failed"
        assert handler.attempts == 3  # 1 initial + 2 retries

    async def test_per_node_max_retries(self):
        handler = FailThenSucceed(fail_times=5)
        config = TreeTaskConfig(max_retries=2)
        root = TaskNode(id="root", name="Root", task_fn=handler.task, max_retries=5)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"
        assert handler.attempts == 6

    async def test_no_retries_when_max_is_zero(self):
        handler = FailThenSucceed(fail_times=1)
        root = TaskNode(id="root", name="Root", task_fn=handler.task, max_retries=0)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        with pytest.raises(ValueError):
            await executor.run()

        assert handler.attempts == 1

    async def test_retry_strategy_with_delay(self):
        handler = FailThenSucceed(fail_times=1)
        strategy = FixedDelayRetry(delay=0.01, max_retries=2)
        config = TreeTaskConfig(default_retry_strategy=strategy)
        root = TaskNode(id="root", name="Root", task_fn=handler.task)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"


@pytest.mark.anyio
class TestTimeoutBehavior:
    async def test_task_timeout(self):
        root = TaskNode(id="root", name="Root", task_fn=slow_task, timeout=0.1)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        with pytest.raises(TimeoutError):
            await executor.run()

        assert root.status == "timed_out"

    async def test_global_timeout(self):
        config = TreeTaskConfig(global_timeout=0.1)
        root = TaskNode(id="root", name="Root", task_fn=slow_task)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()  # Global timeout doesn't raise

        assert root.status == "timed_out"


@pytest.mark.anyio
class TestConditionalExecution:
    async def test_skip_condition(self):
        root = TaskNode(
            id="root",
            name="Root",
            task_fn=success_task,
            skip_condition=lambda n: True,
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "skipped"

    async def test_run_condition_false(self):
        root = TaskNode(
            id="root",
            name="Root",
            task_fn=success_task,
            run_condition=lambda n: False,
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "skipped"

    async def test_run_condition_true(self):
        root = TaskNode(
            id="root",
            name="Root",
            task_fn=success_task,
            run_condition=lambda n: True,
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"


@pytest.mark.anyio
class TestSkipCompleted:
    async def test_skip_completed_nodes(self):
        counter = Counter()
        root = TaskNode(id="root", name="Root", status="done")
        child = TaskNode(id="child", name="Child", task_fn=counter.task)
        root.add_child(child)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree, skip_completed=True)
        await executor.run()

        # Root was skipped because it was already done
        # Child should have run
        assert counter.count == 1


@pytest.mark.anyio
class TestHooksIntegration:
    async def test_hooks_called(self):
        events = []
        hooks = HookDispatcher()
        hooks.on("on_tree_start", lambda t: events.append("tree_start"))
        hooks.on("on_tree_complete", lambda t: events.append("tree_complete"))
        hooks.on("on_node_start", lambda n: events.append(f"node_start:{n.id}"))
        hooks.on("on_node_complete", lambda n: events.append(f"node_complete:{n.id}"))

        root = TaskNode(id="root", name="Root", task_fn=success_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree, hooks=hooks)
        await executor.run()

        assert "tree_start" in events
        assert "tree_complete" in events
        assert "node_start:root" in events
        assert "node_complete:root" in events

    async def test_on_retry_hook(self):
        retries = []
        hooks = HookDispatcher()
        hooks.on("on_retry", lambda n, a, e: retries.append(a))

        handler = FailThenSucceed(fail_times=2)
        config = TreeTaskConfig(max_retries=3)
        root = TaskNode(id="root", name="Root", task_fn=handler.task)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree, hooks=hooks)
        await executor.run()

        assert retries == [1, 2]


@pytest.mark.anyio
class TestDependencies:
    async def test_waits_for_dependency(self):
        order = []

        async def tracking_task(node):
            order.append(node.id)
            return {}

        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A", task_fn=tracking_task)
        task_b = TaskNode(id="task_b", name="Task B", task_fn=tracking_task, depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # task_a must complete before task_b
        assert order.index("task_a") < order.index("task_b")


class TestExecutionResult:
    def test_success(self):
        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        assert result.success is True
        assert result.failed_nodes == []

    def test_failure(self):
        root = TaskNode(id="root", name="Root", status="failed")
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        assert result.success is False
        assert len(result.failed_nodes) == 1

    def test_timeout_is_failure(self):
        root = TaskNode(id="root", name="Root", status="timed_out")
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        assert result.success is False

    def test_results_property(self):
        root = TaskNode(id="root", name="Root", status="done", result={"value": 42})
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        assert result.results == {"root": {"value": 42}}

    def test_timing_stats_property(self):
        root = TaskNode(id="root", name="Root", status="done", start_time=0.0, end_time=1.0)
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        stats = result.timing_stats
        assert stats["count"] == 1
        assert stats["total"] == 1.0

    def test_repr(self):
        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        result = ExecutionResult(tree)

        repr_str = repr(result)
        assert "success=True" in repr_str


@pytest.mark.anyio
class TestCancellationAndControl:
    """Test executor cancellation and control methods."""

    async def test_cancel_method(self):
        """Test that cancel() method marks context as cancelled."""
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        executor.cancel(reason="test cancel")

        assert executor.is_cancelled is True

    async def test_pause_method(self):
        """Test that pause() method marks context as paused."""
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        executor.pause()

        assert executor.is_paused is True

    async def test_resume_method(self):
        """Test that resume() method resumes execution."""
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        executor.pause()
        assert executor.is_paused is True

        executor.resume()
        assert executor.is_paused is False

    async def test_cancellation_marks_node_cancelled(self):
        """Test that cancellation marks node with cancelled status."""
        async def slow_task(node):
            await anyio.sleep(10)
            return {}

        root = TaskNode(id="root", name="Root", task_fn=slow_task)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)

        # Cancel immediately
        executor.cancel(reason="immediate cancel")

        # Run should mark node as cancelled
        await executor.run()

        assert root.status == "cancelled"

    async def test_skip_condition_error_does_not_skip(self):
        """Test that if skip_condition raises an error, node is not skipped."""
        def broken_skip(node):
            raise ValueError("broken condition")

        root = TaskNode(
            id="root",
            name="Root",
            task_fn=success_task,
            skip_condition=broken_skip,
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # Should not be skipped, should run normally
        assert root.status == "done"

    async def test_run_condition_error_runs_anyway(self):
        """Test that if run_condition raises an error, node still runs."""
        def broken_condition(node):
            raise ValueError("broken condition")

        root = TaskNode(
            id="root",
            name="Root",
            task_fn=success_task,
            run_condition=broken_condition,
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # Should run anyway when condition errors
        assert root.status == "done"

    async def test_dependency_signal_on_complete(self):
        """Test that dependency event is signaled when node completes."""
        order = []

        async def tracking_task(node):
            order.append(node.id)
            return {}

        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A", task_fn=tracking_task)
        task_b = TaskNode(id="task_b", name="Task B", task_fn=tracking_task, depends_on=["task_a"])
        task_c = TaskNode(id="task_c", name="Task C", task_fn=tracking_task, depends_on=["task_b"])
        root.add_child(task_a)
        root.add_child(task_b)
        root.add_child(task_c)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # All should be done
        assert task_a.status == "done"
        assert task_b.status == "done"
        assert task_c.status == "done"

        # Order should respect dependencies
        assert order.index("task_a") < order.index("task_b")
        assert order.index("task_b") < order.index("task_c")


@pytest.mark.anyio
class TestGlobalTimeoutBehavior:
    """Test global timeout behavior."""

    async def test_global_timeout_marks_remaining_timed_out(self):
        """Test that global timeout marks all remaining nodes as timed_out."""
        async def slow_task(node):
            await anyio.sleep(10)
            return {}

        config = TreeTaskConfig(global_timeout=0.1)
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1", task_fn=slow_task)
        child2 = TaskNode(id="child2", name="Child 2", task_fn=slow_task)
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()

        # Some or all nodes should be timed_out
        statuses = [n.status for n in tree.walk()]
        assert "timed_out" in statuses


@pytest.mark.anyio
class TestPerNodeRetryStrategy:
    """Test per-node retry strategy handling."""

    async def test_per_node_retry_strategy(self):
        """Test that node.retry_strategy takes precedence."""
        handler = FailThenSucceed(fail_times=2)
        strategy = FixedDelayRetry(delay=0.01, max_retries=5)

        root = TaskNode(
            id="root",
            name="Root",
            task_fn=handler.task,
            retry_strategy=strategy,  # Per-node strategy
        )
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        assert root.status == "done"
        assert handler.attempts == 3  # 1 initial + 2 retries


@pytest.mark.anyio
class TestDependencyEvents:
    """Test dependency event creation and signaling."""

    async def test_dependency_event_created_and_signaled(self):
        """Test that dependency events are created and signaled properly."""
        order = []

        async def ordered_task(node):
            order.append(node.id)
            # Small delay to ensure ordering
            await anyio.sleep(0.01)
            return {}

        root = TaskNode(id="root", name="Root", parallel=True)
        task_a = TaskNode(id="task_a", name="Task A", task_fn=ordered_task)
        task_b = TaskNode(id="task_b", name="Task B", task_fn=ordered_task, depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # Both should be done
        assert task_a.status == "done"
        assert task_b.status == "done"
        # task_a should come before task_b despite parallel execution
        assert order.index("task_a") < order.index("task_b")

    async def test_dependency_event_wait_for_not_yet_completed(self):
        """Test waiting for a dependency that hasn't completed yet."""
        started = []
        completed = []

        async def tracking_task(node):
            started.append(node.id)
            await anyio.sleep(0.05)
            completed.append(node.id)
            return {}

        root = TaskNode(id="root", name="Root", parallel=True)
        task_a = TaskNode(id="task_a", name="Task A", task_fn=tracking_task)
        task_b = TaskNode(id="task_b", name="Task B", task_fn=tracking_task, depends_on=["task_a"])
        task_c = TaskNode(id="task_c", name="Task C", task_fn=tracking_task, depends_on=["task_b"])
        root.add_child(task_a)
        root.add_child(task_b)
        root.add_child(task_c)
        tree = TaskTree(root)

        executor = AsyncExecutor(tree)
        await executor.run()

        # All should complete in order
        assert completed.index("task_a") < completed.index("task_b")
        assert completed.index("task_b") < completed.index("task_c")


@pytest.mark.anyio
class TestCancellationDuringExecution:
    """Test cancellation during actual task execution."""

    async def test_global_timeout_marks_pending_and_working_nodes(self):
        """Test that global timeout marks both pending and working nodes as timed_out."""
        execution_started = False

        async def slow_task(node):
            nonlocal execution_started
            execution_started = True
            await anyio.sleep(10)
            return {}

        config = TreeTaskConfig(global_timeout=0.1)
        root = TaskNode(id="root", name="Root", parallel=False)  # Sequential
        child1 = TaskNode(id="child1", name="Child 1", task_fn=slow_task)
        child2 = TaskNode(id="child2", name="Child 2", task_fn=slow_task)  # Won't start
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)
        await executor.run()

        # child1 should be working or timed_out
        # child2 should still be pending (timed out before starting)
        assert child1.status == "timed_out"
        # child2 could be pending or timed_out depending on timing
        assert child2.status in ("pending", "timed_out")

    async def test_cancel_with_global_timeout_scope(self):
        """Test that cancellation through global timeout scope marks as cancelled."""
        task_started = anyio.Event()

        async def wait_for_cancel(node):
            task_started.set()
            await anyio.sleep(10)  # Long wait - will be cancelled
            return {}

        config = TreeTaskConfig(global_timeout=60.0)  # Long timeout
        root = TaskNode(id="root", name="Root", task_fn=wait_for_cancel)
        tree = TaskTree(root, config)

        executor = AsyncExecutor(tree)

        async def cancel_after_start():
            await task_started.wait()
            await anyio.sleep(0.05)  # Small delay
            # Cancel through the executor (which cancels the context and scope)
            executor.cancel(reason="Test cancellation via scope")

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(executor.run)
                tg.start_soon(cancel_after_start)
        except anyio.get_cancelled_exc_class():
            pass  # Expected when cancel scope is cancelled

        # The node should be cancelled
        assert root.status == "cancelled"
