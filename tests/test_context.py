"""Tests for ExecutionContext."""

import pytest
import anyio
from treetask.context import ExecutionContext


class TestExecutionContext:
    def test_initial_state(self):
        context = ExecutionContext()
        assert context.is_cancelled is False
        assert context.is_paused is False
        assert context.active_count == 0
        assert context.completed_count == 0

    def test_cancel(self):
        context = ExecutionContext()
        context.cancel(reason="test reason")

        assert context.is_cancelled is True
        assert context.cancel_reason == "test reason"

    def test_cancel_without_reason(self):
        context = ExecutionContext()
        context.cancel()

        assert context.is_cancelled is True
        assert context.cancel_reason is None

    def test_pause_resume(self):
        context = ExecutionContext()

        context.pause()
        assert context.is_paused is True

        context.resume()
        assert context.is_paused is False

    def test_record_completion(self):
        context = ExecutionContext()
        context.record_completion(1.0)
        context.record_completion(2.0)
        context.record_completion(3.0)

        assert context.completed_count == 3
        assert context.average_duration == 2.0

    def test_estimate_remaining_time(self):
        context = ExecutionContext()
        context.record_completion(2.0)
        context.record_completion(4.0)

        # Average is 3.0, 5 pending = 15.0
        assert context.estimate_remaining_time(5) == 15.0

    def test_estimate_remaining_time_no_data(self):
        context = ExecutionContext()
        assert context.estimate_remaining_time(5) is None

    def test_get_stats(self):
        context = ExecutionContext()
        context.record_completion(1.0)

        stats = context.get_stats()
        assert stats["completed_count"] == 1
        assert stats["is_cancelled"] is False
        assert stats["is_paused"] is False

    def test_max_concurrency_creates_semaphore(self):
        context = ExecutionContext(max_concurrency=5)
        assert context._semaphore is not None


@pytest.mark.anyio
class TestExecutionContextAsync:
    async def test_initialize(self):
        context = ExecutionContext()
        await context.initialize()

        assert context.start_time is not None
        assert context._pause_event is not None

    async def test_finalize(self):
        context = ExecutionContext()
        await context.initialize()
        context.finalize()

        assert context.end_time is not None
        assert context.elapsed is not None
        assert context.elapsed >= 0

    async def test_wait_if_paused_not_paused(self):
        context = ExecutionContext()
        await context.initialize()

        # Should not block
        await context.wait_if_paused()

    async def test_wait_if_paused_blocks_when_paused(self):
        context = ExecutionContext()
        await context.initialize()

        context.pause()
        waited = False

        async def waiter():
            nonlocal waited
            await context.wait_if_paused()
            waited = True

        async def resumer():
            await anyio.sleep(0.1)
            context.resume()

        async with anyio.create_task_group() as tg:
            tg.start_soon(waiter)
            tg.start_soon(resumer)

        assert waited is True

    async def test_acquire_release_slot_no_limit(self):
        context = ExecutionContext()
        await context.initialize()

        await context.acquire_slot()
        assert context.active_count == 1

        context.release_slot()
        assert context.active_count == 0

    async def test_acquire_slot_with_concurrency_limit(self):
        context = ExecutionContext(max_concurrency=2)
        await context.initialize()

        await context.acquire_slot()
        await context.acquire_slot()
        assert context.active_count == 2

        # Third acquisition should block (we won't actually block in test)
        # Just verify the semaphore is being used
        assert context._semaphore is not None
