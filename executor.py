"""Async executor for task trees."""

import time
import traceback
from typing import Any, Callable, Optional

import anyio

from .context import ExecutionContext
from .core import TaskNode, TaskTree
from .hooks import HookDispatcher
from .strategies import RetryStrategy, FixedDelayRetry


class AsyncExecutor:
    """Executes task trees with configurable parallelism.

    The executor respects the `parallel` flag on each node to determine
    whether children should be executed concurrently or sequentially.

    Supports:
    - Timeout (global and per-task)
    - Cancellation
    - Pause/Resume
    - Concurrency limits
    - Retry strategies
    - Conditional execution
    - DAG dependencies
    - Skip completed (for resume from checkpoint)

    Example:
        >>> executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
        >>> anyio.run(executor.run)
        >>>
        >>> # With hooks
        >>> hooks = HookDispatcher()
        >>> hooks.on("on_retry", lambda n, a, e: print(f"Retry {a}"))
        >>> executor = AsyncExecutor(tree, hooks=hooks)
    """

    def __init__(
        self,
        tree: TaskTree,
        on_update: Optional[Callable[[TaskTree], None]] = None,
        on_node_start: Optional[Callable[[TaskNode], None]] = None,
        on_node_complete: Optional[Callable[[TaskNode], None]] = None,
        hooks: Optional[HookDispatcher] = None,
        context: Optional[ExecutionContext] = None,
        skip_completed: bool = False,
    ):
        """Initialize the executor.

        Args:
            tree: The task tree to execute.
            on_update: Callback when any node status changes.
            on_node_start: Callback when a node starts executing.
            on_node_complete: Callback when a node completes (success or failure).
            hooks: HookDispatcher for extended event handling.
            context: Execution context for external control (cancel, pause).
            skip_completed: Skip nodes that are already done (for checkpoint resume).
        """
        self.tree = tree
        self.on_update = on_update
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete
        self.hooks = hooks or HookDispatcher()
        self.skip_completed = skip_completed

        # Create context if not provided
        self.context = context or ExecutionContext(
            max_concurrency=tree.config.max_concurrency
        )

        # Track completed nodes for dependency resolution
        self._completed_ids: set[str] = set()
        self._dependency_events: dict[str, anyio.Event] = {}

        # Register legacy callbacks as hooks for backward compatibility
        if on_update:
            self.hooks.on("on_update", lambda: on_update(tree))
        if on_node_start:
            self.hooks.on("on_node_start", on_node_start)
        if on_node_complete:
            self.hooks.on("on_node_complete", on_node_complete)

    async def run(self) -> TaskTree:
        """Execute all tasks in the tree.

        Returns:
            The task tree with updated statuses.
        """
        await self.context.initialize()
        self.hooks.emit("on_tree_start", self.tree)

        # Initialize completed IDs if resuming
        if self.skip_completed:
            self._completed_ids = self.tree.get_completed_ids()

        try:
            # Global timeout
            timeout = self.tree.config.global_timeout

            if timeout:
                with anyio.move_on_after(timeout) as cancel_scope:
                    self.context.set_cancel_scope(cancel_scope)
                    await self._execute_node(self.tree.root)

                if cancel_scope.cancelled_caught:
                    # Global timeout exceeded
                    self._mark_remaining_timed_out()
            else:
                await self._execute_node(self.tree.root)

        finally:
            self.context.finalize()
            self.hooks.emit("on_tree_complete", self.tree)

        return self.tree

    async def _execute_node(self, node: TaskNode) -> None:
        """Execute a single node and its children.

        Args:
            node: The node to execute.
        """
        # Check for cancellation
        if self.context.is_cancelled:
            node.status = "cancelled"
            self.hooks.emit("on_cancel", node, self.context.cancel_reason)
            return

        # Wait if paused
        await self.context.wait_if_paused()

        # Skip if already completed (checkpoint resume)
        if self.skip_completed and node.id in self._completed_ids:
            return

        # Evaluate skip condition
        if node.skip_condition is not None:
            try:
                if node.skip_condition(node):
                    node.status = "skipped"
                    self._mark_completed(node)
                    self.hooks.emit("on_skip", node, "skip_condition")
                    self._notify_update()
                    return
            except Exception:
                pass  # If condition errors, don't skip

        # Evaluate run condition
        if node.run_condition is not None:
            try:
                if not node.run_condition(node):
                    node.status = "skipped"
                    self._mark_completed(node)
                    self.hooks.emit("on_skip", node, "run_condition_false")
                    self._notify_update()
                    return
            except Exception:
                pass  # If condition errors, run anyway

        # Wait for dependencies (except parent which is implicit)
        await self._wait_for_dependencies(node)

        # Acquire concurrency slot
        await self.context.acquire_slot()

        try:
            # Mark as working and record start time
            node.start_time = time.time()
            node.status = "working"
            self._notify_update()
            self.hooks.emit("on_node_start", node)

            # Execute the node's task function if present
            if node.task_fn is not None:
                timeout = node.timeout or self.tree.config.default_task_timeout
                result = await self._run_with_timeout_and_retry(node, timeout)
                node.result = result
                if result is not None and isinstance(result, dict):
                    node.data.update(result)

            # Execute children
            if node.children:
                await self._execute_children(node)

            # Mark as done if not already failed/cancelled/timed_out
            if node.status == "working":
                node.status = "done"
                node.end_time = time.time()
                self._mark_completed(node)
                self._notify_update()

        except anyio.get_cancelled_exc_class():
            if self.context.is_cancelled:
                node.status = "cancelled"
                self.hooks.emit("on_cancel", node, self.context.cancel_reason)
            else:
                node.status = "timed_out"
                self.hooks.emit("on_timeout", node)
            node.end_time = time.time()
            self._notify_update()
            raise

        except Exception as e:
            node.status = "failed"
            node.error = f"{e}\n{traceback.format_exc()}"
            node.end_time = time.time()
            self._mark_completed(node)
            self._notify_update()
            raise

        finally:
            self.context.release_slot()
            if node.elapsed is not None:
                self.context.record_completion(node.elapsed)
            self.hooks.emit("on_node_complete", node)

    async def _execute_children(self, node: TaskNode) -> None:
        """Execute children of a node.

        Args:
            node: The parent node whose children to execute.
        """
        if node.parallel:
            # Run children concurrently
            async with anyio.create_task_group() as tg:
                for child in node.children:
                    tg.start_soon(self._execute_node, child)
        else:
            # Run children sequentially
            for child in node.children:
                await self._execute_node(child)

    async def _run_with_timeout_and_retry(
        self, node: TaskNode, timeout: Optional[float]
    ) -> Any:
        """Run a node's task function with timeout and retry logic.

        Args:
            node: The node whose task to execute.
            timeout: Timeout in seconds, or None for no timeout.

        Returns:
            The result of the task function.

        Raises:
            Exception: If all retries are exhausted or timeout occurs.
        """
        # Get retry strategy
        strategy = self._get_retry_strategy(node)

        attempt = 0
        last_error: Optional[Exception] = None

        while True:
            try:
                # Execute with timeout if specified
                if timeout:
                    with anyio.fail_after(timeout):
                        return await node.task_fn(node)
                else:
                    return await node.task_fn(node)

            except TimeoutError:
                node.status = "timed_out"
                node.error = f"Task timed out after {timeout}s"
                self.hooks.emit("on_timeout", node)
                self._notify_update()
                raise

            except anyio.get_cancelled_exc_class():
                # Don't retry on cancellation
                raise

            except Exception as e:
                last_error = e
                node.error = f"{e}\n{traceback.format_exc()}"
                self.hooks.emit("on_error", node, e)

                # Check retry strategy
                delay = strategy.get_delay(attempt, e) if strategy else None

                if delay is None:
                    # No more retries
                    node.status = "failed"
                    self._notify_update()
                    raise

                # Retry
                attempt += 1
                node.retry_count = attempt
                node.status = "retrying"
                self._notify_update()
                self.hooks.emit("on_retry", node, attempt, e)

                # Wait before retry
                if delay > 0:
                    await anyio.sleep(delay)

        # Should not reach here
        if last_error:
            raise last_error

    def _get_retry_strategy(self, node: TaskNode) -> Optional[RetryStrategy]:
        """Get the retry strategy for a node.

        Args:
            node: The node to get strategy for.

        Returns:
            RetryStrategy or None if no retries.
        """
        # Per-node strategy takes precedence
        if node.retry_strategy is not None:
            return node.retry_strategy

        # Per-node max_retries
        if node.max_retries is not None:
            if node.max_retries <= 0:
                return None
            return FixedDelayRetry(delay=0, max_retries=node.max_retries)

        # Global config strategy
        return self.tree.config.get_retry_strategy()

    async def _wait_for_dependencies(self, node: TaskNode) -> None:
        """Wait for all dependencies to complete.

        Args:
            node: The node whose dependencies to wait for.
        """
        if not node.depends_on:
            return

        for dep_id in node.depends_on:
            # Skip if already completed
            if dep_id in self._completed_ids:
                continue

            # Create or get event for this dependency
            if dep_id not in self._dependency_events:
                self._dependency_events[dep_id] = anyio.Event()

            # Wait for the dependency
            await self._dependency_events[dep_id].wait()

        self.hooks.emit("on_dependency_ready", node)

    def _mark_completed(self, node: TaskNode) -> None:
        """Mark a node as completed and notify dependents.

        Args:
            node: The completed node.
        """
        self._completed_ids.add(node.id)

        # Signal any waiting dependents
        if node.id in self._dependency_events:
            self._dependency_events[node.id].set()

    def _mark_remaining_timed_out(self) -> None:
        """Mark all remaining pending/working nodes as timed out."""
        for node in self.tree.walk():
            if node.status in ("pending", "working"):
                node.status = "timed_out"
                self.hooks.emit("on_timeout", node)

    def _notify_update(self) -> None:
        """Notify listeners of a tree update."""
        self.hooks.emit("on_update")
        if self.on_update:
            self.on_update(self.tree)

    # External control methods

    def cancel(self, reason: Optional[str] = None) -> None:
        """Request cancellation of all tasks.

        Args:
            reason: Optional reason for cancellation.
        """
        self.context.cancel(reason)

    def pause(self) -> None:
        """Pause execution (new tasks won't start)."""
        self.context.pause()

    def resume(self) -> None:
        """Resume paused execution."""
        self.context.resume()

    @property
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self.context.is_cancelled

    @property
    def is_paused(self) -> bool:
        """Check if execution is paused."""
        return self.context.is_paused


class ExecutionResult:
    """Result of executing a task tree.

    Attributes:
        tree: The executed task tree.
        success: Whether all tasks completed successfully.
        failed_nodes: List of nodes that failed.
        stats: Statistics about the execution.
    """

    def __init__(self, tree: TaskTree):
        self.tree = tree
        self.stats = tree.get_stats()
        self.failed_nodes = tree.get_failed_nodes()
        self.success = self.stats["failed"] == 0 and self.stats["timed_out"] == 0

    @property
    def results(self) -> dict[str, Any]:
        """Get all node results."""
        return self.tree.collect_results()

    @property
    def timing_stats(self) -> dict[str, Any]:
        """Get timing statistics."""
        return self.tree.get_timing_stats()

    def __repr__(self) -> str:
        return f"ExecutionResult(success={self.success}, stats={self.stats})"
