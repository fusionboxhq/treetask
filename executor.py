"""Async executor for task trees."""

import traceback
from typing import Any, Callable, Optional

import anyio

from .core import TaskNode, TaskTree


class AsyncExecutor:
    """Executes task trees with configurable parallelism.

    The executor respects the `parallel` flag on each node to determine
    whether children should be executed concurrently or sequentially.

    Example:
        >>> executor = AsyncExecutor(tree, on_update=lambda t: display.update(t))
        >>> anyio.run(executor.run)
    """

    def __init__(
        self,
        tree: TaskTree,
        on_update: Optional[Callable[[TaskTree], None]] = None,
        on_node_start: Optional[Callable[[TaskNode], None]] = None,
        on_node_complete: Optional[Callable[[TaskNode], None]] = None,
    ):
        """Initialize the executor.

        Args:
            tree: The task tree to execute.
            on_update: Callback when any node status changes.
            on_node_start: Callback when a node starts executing.
            on_node_complete: Callback when a node completes (success or failure).
        """
        self.tree = tree
        self.on_update = on_update
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete

    async def run(self) -> TaskTree:
        """Execute all tasks in the tree.

        Returns:
            The task tree with updated statuses.
        """
        await self._execute_node(self.tree.root)
        return self.tree

    async def _execute_node(self, node: TaskNode) -> None:
        """Execute a single node and its children.

        Args:
            node: The node to execute.
        """
        # Mark as working
        node.status = "working"
        self._notify_update()
        if self.on_node_start:
            self.on_node_start(node)

        try:
            # Execute the node's task function if present
            if node.task_fn is not None:
                result = await self._run_with_retry(node)
                if result is not None and isinstance(result, dict):
                    node.data.update(result)

            # Execute children
            if node.children:
                await self._execute_children(node)

            # Mark as done if not already failed
            if node.status != "failed":
                node.status = "done"
                self._notify_update()

        except Exception as e:
            node.status = "failed"
            node.error = str(e)
            self._notify_update()
            raise

        finally:
            if self.on_node_complete:
                self.on_node_complete(node)

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

    async def _run_with_retry(self, node: TaskNode) -> Any:
        """Run a node's task function with retry logic.

        Args:
            node: The node whose task to execute.

        Returns:
            The result of the task function.

        Raises:
            Exception: If all retries are exhausted.
        """
        max_retries = self.tree.config.max_retries
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    node.status = "retrying"
                    node.retry_count = attempt
                    self._notify_update()

                return await node.task_fn(node)

            except Exception as e:
                last_error = e
                node.error = f"{e}\n{traceback.format_exc()}"

                if attempt < max_retries:
                    # Will retry
                    continue
                else:
                    # All retries exhausted
                    node.status = "failed"
                    self._notify_update()
                    raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error

    def _notify_update(self) -> None:
        """Notify listeners of a tree update."""
        if self.on_update:
            self.on_update(self.tree)


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
        self.failed_nodes = [n for n in tree.walk() if n.status == "failed"]
        self.success = self.stats["failed"] == 0

    def __repr__(self) -> str:
        return f"ExecutionResult(success={self.success}, stats={self.stats})"
