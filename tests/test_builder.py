"""Tests for TreeBuilder."""

import pytest
from treetask.builder import TreeBuilder
from treetask.strategies import FixedDelayRetry, ExponentialBackoffRetry


async def dummy_task(node):
    return {"done": True}


class TestTreeBuilder:
    def test_basic_build(self):
        tree = TreeBuilder("root", name="Root").build()

        assert tree.root.id == "root"
        assert tree.root.name == "Root"

    def test_add_node(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("child", name="Child")
            .build()
        )

        assert len(tree.root.children) == 1
        assert tree.root.children[0].id == "child"

    def test_add_child(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("child1", name="Child 1")
            .add_child("child2", name="Child 2")
            .build()
        )

        assert len(tree.root.children) == 2

    def test_up(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("child", name="Child")
            .up()
            .add_child("sibling", name="Sibling")
            .build()
        )

        assert len(tree.root.children) == 2

    def test_up_at_root_stays_at_root(self):
        tree = (
            TreeBuilder("root", name="Root")
            .up()  # Should stay at root
            .add_child("child", name="Child")
            .build()
        )

        assert len(tree.root.children) == 1

    def test_add_node_with_task(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("task", name="Task", task=dummy_task)
            .build()
        )

        assert tree.root.children[0].task_fn is dummy_task

    def test_add_node_with_data(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("task", name="Task", data={"key": "value"})
            .build()
        )

        assert tree.root.children[0].data["key"] == "value"

    def test_add_node_with_parallel(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("task", name="Task", parallel=False)
            .build()
        )

        assert tree.root.children[0].parallel is False

    def test_nested_structure(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("level1", name="Level 1")
                .add_node("level2", name="Level 2")
                    .add_child("level3", name="Level 3")
                .up()
            .up()
            .build()
        )

        assert tree.root.children[0].children[0].children[0].name == "Level 3"

    def test_set_timeout(self):
        # Use add_node to move into the child, then set_timeout
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task")
            .set_timeout(30.0)
            .build()
        )

        assert tree.root.children[0].timeout == 30.0

    def test_set_timeout_on_root(self):
        tree = (
            TreeBuilder("root", name="Root")
            .set_timeout(60.0)
            .build()
        )

        assert tree.root.timeout == 60.0

    def test_set_max_retries(self):
        # Use add_node to move into the child
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task")
            .set_max_retries(5)
            .build()
        )

        assert tree.root.children[0].max_retries == 5

    def test_set_retry_strategy(self):
        strategy = FixedDelayRetry(delay=1.0, max_retries=3)
        # Use add_node to move into the child
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task")
            .set_retry_strategy(strategy)
            .build()
        )

        assert tree.root.children[0].retry_strategy is strategy

    def test_depends_on_single(self):
        # Use add_node for task2 so we can add dependencies
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("task1", name="Task 1")
            .add_node("task2", name="Task 2")
            .depends_on("task1")
            .build()
        )

        assert "task1" in tree.root.children[1].depends_on

    def test_depends_on_multiple(self):
        # Use add_node to move into task3
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("task1", name="Task 1")
            .add_child("task2", name="Task 2")
            .add_node("task3", name="Task 3")
            .depends_on("task1", "task2")
            .build()
        )

        deps = tree.root.children[2].depends_on
        assert "task1" in deps
        assert "task2" in deps

    def test_set_skip_condition(self):
        condition = lambda node: node.data.get("skip", False)
        # Use add_node to move into the child
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task")
            .set_skip_condition(condition)
            .build()
        )

        assert tree.root.children[0].skip_condition is condition

    def test_set_run_condition(self):
        condition = lambda node: node.data.get("run", True)
        # Use add_node to move into the child
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task")
            .set_run_condition(condition)
            .build()
        )

        assert tree.root.children[0].run_condition is condition

    def test_chained_configuration(self):
        strategy = ExponentialBackoffRetry(max_retries=3)
        skip_cond = lambda n: False
        run_cond = lambda n: True

        # Use add_node to move into the task node
        tree = (
            TreeBuilder("root", name="Root")
            .add_node("task", name="Task", task=dummy_task)
            .set_timeout(10.0)
            .set_max_retries(5)
            .set_retry_strategy(strategy)
            .depends_on("other")
            .set_skip_condition(skip_cond)
            .set_run_condition(run_cond)
            .build()
        )

        task = tree.root.children[0]
        assert task.timeout == 10.0
        assert task.max_retries == 5
        assert task.retry_strategy is strategy
        assert "other" in task.depends_on
        assert task.skip_condition is skip_cond
        assert task.run_condition is run_cond

    def test_complex_tree_structure(self):
        tree = (
            TreeBuilder("pipeline", name="Pipeline")
            .add_node("phase1", name="Phase 1", parallel=True)
                .add_child("t1a", name="Task 1A", task=dummy_task)
                .add_child("t1b", name="Task 1B", task=dummy_task)
            .up()
            .add_node("phase2", name="Phase 2", parallel=False)
                .add_child("t2a", name="Task 2A", task=dummy_task)
                .depends_on("t1a", "t1b")
                .add_child("t2b", name="Task 2B", task=dummy_task)
            .up()
            .build()
        )

        assert tree.root.name == "Pipeline"
        assert len(tree.root.children) == 2

        phase1 = tree.root.children[0]
        assert phase1.parallel is True
        assert len(phase1.children) == 2

        phase2 = tree.root.children[1]
        assert phase2.parallel is False
        assert len(phase2.children) == 2

    def test_default_parallel_true(self):
        tree = TreeBuilder("root", name="Root").build()
        assert tree.root.parallel is True

    def test_explicit_parallel_false(self):
        tree = TreeBuilder("root", name="Root", parallel=False).build()
        assert tree.root.parallel is False

    def test_root_with_data(self):
        tree = TreeBuilder("root", name="Root", data={"key": "value"}).build()
        assert tree.root.data["key"] == "value"

    def test_tree_find_after_build(self):
        tree = (
            TreeBuilder("root", name="Root")
            .add_child("child", name="Child")
            .build()
        )

        found = tree.find("child")
        assert found is not None
        assert found.name == "Child"
