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
