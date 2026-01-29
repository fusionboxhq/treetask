"""Test script for treetask package."""

import asyncio
import random

import anyio

from treetask import (
    AsyncExecutor,
    LiveDisplay,
    TreeBuilder,
    TreeRenderer,
    TreeTaskConfig,
)


async def simulate_work(node):
    """Simulate work with random duration."""
    duration = random.uniform(0.5, 2.0)
    await anyio.sleep(duration)
    node.progress = (1, 1)
    return {"duration": duration}


async def failing_task(node):
    """Task that fails on first attempt."""
    if node.retry_count < 1:
        raise ValueError("Simulated failure")
    await anyio.sleep(0.5)
    node.progress = (1, 1)
    return {"recovered": True}


async def main():
    """Run the test."""
    print("Building task tree...")

    # Build a 3-level tree
    tree = (
        TreeBuilder("pipeline", name="Data Pipeline")
        # Phase 1: Parallel tasks
        .add_node("phase1", name="Phase 1: Data Collection", parallel=True)
            .add_child("task1a", name="Fetch API Data", task=simulate_work)
            .add_child("task1b", name="Fetch Database Records", task=simulate_work)
            .add_child("task1c", name="Fetch File Data", task=simulate_work)
        .up()
        # Phase 2: Sequential tasks
        .add_node("phase2", name="Phase 2: Processing", parallel=False)
            .add_child("task2a", name="Validate Data", task=simulate_work)
            .add_child("task2b", name="Transform Data", task=simulate_work)
            .add_child("task2c", name="Enrich Data", task=simulate_work)
        .up()
        # Phase 3: Mixed - parent sequential, children parallel
        .add_node("phase3", name="Phase 3: Output", parallel=True)
            .add_child("task3a", name="Save to Database", task=simulate_work)
            .add_child("task3b", name="Generate Report", task=simulate_work)
            .add_child("task3c", name="Send Notifications", task=failing_task)  # Will retry
        .build()
    )

    print(f"Tree created: {tree}")
    print()

    # Create display
    config = TreeTaskConfig(
        default_max_depth=2,
        final_max_depth=3,
        refresh_interval=0.1,
    )
    renderer = TreeRenderer(config)
    display = LiveDisplay(renderer, config)

    print("Starting execution with live display...")
    print()

    # Execute with live updates
    executor = AsyncExecutor(
        tree,
        on_update=lambda t: display.update(t),
    )

    try:
        with display:
            await executor.run()
    except Exception as e:
        print(f"Execution error: {e}")

    # Show final result
    display.finalize(tree, max_depth=4)

    print()
    print("Execution complete!")

    # Print detailed stats
    stats = tree.get_leaf_stats()
    print(f"Leaf task stats: {stats}")


async def test_simple():
    """Simple test without live display."""
    print("Running simple test...")

    async def quick_task(node):
        await anyio.sleep(0.1)
        return {"ok": True}

    tree = (
        TreeBuilder("test")
        .add_node("a", name="Task A", task=quick_task)
        .up()
        .add_node("b", name="Task B", task=quick_task)
        .build()
    )

    executor = AsyncExecutor(tree)
    await executor.run()

    renderer = TreeRenderer()
    print(renderer.render(tree, show_stats=True))
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("TreeTask Package Test")
    print("=" * 60)
    print()

    # Run simple test first
    anyio.run(test_simple)

    print("=" * 60)
    print()

    # Run full test with live display
    anyio.run(main)
