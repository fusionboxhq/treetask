"""Tests for TaskNode and TaskTree."""

import pytest
from treetask.core import TaskNode, TaskTree
from treetask.config import TreeTaskConfig


class TestTaskNode:
    def test_create_with_defaults(self):
        node = TaskNode(id="test", name="Test")

        assert node.id == "test"
        assert node.name == "Test"
        assert node.status == "pending"
        assert node.children == []
        assert node.parent is None
        assert node.data == {}
        assert node.progress is None
        assert node.retry_count == 0
        assert node.error is None
        assert node.parallel is True
        assert node.task_fn is None

    def test_create_with_all_fields(self):
        async def task(n):
            pass

        node = TaskNode(
            id="test",
            name="Test",
            status="done",
            data={"key": "value"},
            progress=(5, 10),
            retry_count=2,
            error="Some error",
            parallel=False,
            task_fn=task,
            timeout=30.0,
            max_retries=5,
            depends_on=["other"],
        )

        assert node.status == "done"
        assert node.data["key"] == "value"
        assert node.progress == (5, 10)
        assert node.retry_count == 2
        assert node.error == "Some error"
        assert node.parallel is False
        assert node.task_fn is task
        assert node.timeout == 30.0
        assert node.max_retries == 5
        assert "other" in node.depends_on

    def test_add_child(self):
        parent = TaskNode(id="parent", name="Parent")
        child = TaskNode(id="child", name="Child")

        parent.add_child(child)

        assert len(parent.children) == 1
        assert parent.children[0] is child
        assert child.parent is parent

    def test_add_multiple_children(self):
        parent = TaskNode(id="parent", name="Parent")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")

        parent.add_child(child1)
        parent.add_child(child2)

        assert len(parent.children) == 2

    def test_get_depth_root(self):
        node = TaskNode(id="root", name="Root")
        assert node.get_depth() == 0

    def test_get_depth_nested(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child)
        child.add_child(grandchild)

        assert root.get_depth() == 0
        assert child.get_depth() == 1
        assert grandchild.get_depth() == 2

    def test_is_leaf_true(self):
        node = TaskNode(id="leaf", name="Leaf")
        assert node.is_leaf() is True

    def test_is_leaf_false(self):
        parent = TaskNode(id="parent", name="Parent")
        child = TaskNode(id="child", name="Child")
        parent.add_child(child)

        assert parent.is_leaf() is False

    def test_get_ancestors_root(self):
        root = TaskNode(id="root", name="Root")
        assert root.get_ancestors() == []

    def test_get_ancestors_nested(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child)
        child.add_child(grandchild)

        ancestors = grandchild.get_ancestors()
        assert len(ancestors) == 2
        assert ancestors[0] is child
        assert ancestors[1] is root

    def test_elapsed_property_none_when_no_times(self):
        node = TaskNode(id="test", name="Test")
        assert node.elapsed is None

    def test_elapsed_property_returns_current_when_no_end_time(self):
        # When start_time is set but end_time is None, elapsed returns current time - start_time
        import time
        start = time.time()
        node = TaskNode(id="test", name="Test", start_time=start)
        elapsed = node.elapsed
        assert elapsed is not None
        assert elapsed >= 0

    def test_elapsed_property_calculates_duration(self):
        node = TaskNode(id="test", name="Test", start_time=100.0, end_time=105.5)
        assert node.elapsed == 5.5

    def test_str_representation(self):
        node = TaskNode(id="test", name="Test Node", status="done")
        s = str(node)
        assert "test" in s or "Test Node" in s

    def test_repr_representation(self):
        node = TaskNode(id="test", name="Test Node", status="done")
        r = repr(node)
        assert "test" in r or "TaskNode" in r


class TestTaskTree:
    def test_create_with_root(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        assert tree.root is root

    def test_create_with_config(self):
        root = TaskNode(id="root", name="Root")
        config = TreeTaskConfig(max_retries=10)
        tree = TaskTree(root, config)

        assert tree.config.max_retries == 10

    def test_find_root(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        found = tree.find("root")
        assert found is root

    def test_find_child(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        root.add_child(child)
        tree = TaskTree(root)

        found = tree.find("child")
        assert found is child

    def test_find_not_found(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        found = tree.find("nonexistent")
        assert found is None

    def test_walk_depth_first(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child1)
        root.add_child(child2)
        child1.add_child(grandchild)
        tree = TaskTree(root)

        nodes = list(tree.walk(depth_first=True))
        node_ids = [n.id for n in nodes]

        assert node_ids == ["root", "child1", "grandchild", "child2"]

    def test_walk_breadth_first(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child1)
        root.add_child(child2)
        child1.add_child(grandchild)
        tree = TaskTree(root)

        nodes = list(tree.walk(depth_first=False))
        node_ids = [n.id for n in nodes]

        assert node_ids == ["root", "child1", "child2", "grandchild"]

    def test_get_stats(self):
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="done")
        child2 = TaskNode(id="child2", name="Child 2", status="pending")
        child3 = TaskNode(id="child3", name="Child 3", status="failed")

        root.add_child(child1)
        root.add_child(child2)
        root.add_child(child3)
        tree = TaskTree(root)

        stats = tree.get_stats()

        assert stats["done"] == 2
        assert stats["pending"] == 1
        assert stats["failed"] == 1
        assert stats["total"] == 4

    def test_get_leaf_stats(self):
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="done")
        child2 = TaskNode(id="child2", name="Child 2", status="pending")

        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        stats = tree.get_leaf_stats()

        # Only leaves (child1, child2) should be counted
        assert stats["done"] == 1
        assert stats["pending"] == 1
        assert stats["total"] == 2

    def test_get_work_node_stats(self):
        async def task(n):
            pass

        root = TaskNode(id="root", name="Root")  # No task
        child1 = TaskNode(id="child1", name="Child 1", status="done", task_fn=task)
        child2 = TaskNode(id="child2", name="Child 2", status="pending", task_fn=task)

        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        stats = tree.get_work_node_stats()

        # Only nodes with task_fn should be counted
        assert stats["done"] == 1
        assert stats["pending"] == 1
        assert stats["total"] == 2

    def test_get_progress_stats(self):
        root = TaskNode(id="root", name="Root", progress=(5, 10))
        child = TaskNode(id="child", name="Child", progress=(3, 5))

        root.add_child(child)
        tree = TaskTree(root)

        stats = tree.get_progress_stats()

        assert stats["current"] == 8  # 5 + 3
        assert stats["total"] == 15  # 10 + 5
        assert stats["nodes_with_progress"] == 2

    def test_get_progress_stats_no_progress(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        stats = tree.get_progress_stats()

        assert stats["current"] == 0
        assert stats["total"] == 0
        assert stats["nodes_with_progress"] == 0

    def test_register_node(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        new_node = TaskNode(id="new", name="New")
        tree.register_node(new_node)

        found = tree.find("new")
        assert found is new_node

    def test_collect_results(self):
        root = TaskNode(id="root", name="Root", result={"a": 1})
        child = TaskNode(id="child", name="Child", result={"b": 2})

        root.add_child(child)
        tree = TaskTree(root)

        results = tree.collect_results()

        assert results["root"] == {"a": 1}
        assert results["child"] == {"b": 2}

    def test_collect_results_excludes_none(self):
        root = TaskNode(id="root", name="Root", result={"a": 1})
        child = TaskNode(id="child", name="Child")  # No result

        root.add_child(child)
        tree = TaskTree(root)

        results = tree.collect_results()

        assert "root" in results
        assert "child" not in results

    def test_aggregate_results(self):
        root = TaskNode(id="root", name="Root", result={"value": 10})
        child1 = TaskNode(id="child1", name="Child 1", result={"value": 20})
        child2 = TaskNode(id="child2", name="Child 2", result={"value": 30})

        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        # aggregate_results takes a reducer that receives a list of results
        total = tree.aggregate_results(
            reducer=lambda results: sum(r.get("value", 0) for r in results)
        )

        assert total == 60

    def test_get_failed_nodes(self):
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="failed")
        child2 = TaskNode(id="child2", name="Child 2", status="failed")
        child3 = TaskNode(id="child3", name="Child 3", status="done")

        root.add_child(child1)
        root.add_child(child2)
        root.add_child(child3)
        tree = TaskTree(root)

        failed = tree.get_failed_nodes()

        assert len(failed) == 2
        failed_ids = [n.id for n in failed]
        assert "child1" in failed_ids
        assert "child2" in failed_ids

    def test_get_completed_ids(self):
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="done")
        child2 = TaskNode(id="child2", name="Child 2", status="pending")
        child3 = TaskNode(id="child3", name="Child 3", status="skipped")

        root.add_child(child1)
        root.add_child(child2)
        root.add_child(child3)
        tree = TaskTree(root)

        completed = tree.get_completed_ids()

        assert "root" in completed
        assert "child1" in completed
        assert "child2" not in completed
        assert "child3" in completed

    def test_get_timing_stats(self):
        # Only nodes with status "done" and elapsed are counted
        root = TaskNode(id="root", name="Root", start_time=0, end_time=10, status="done")
        child = TaskNode(id="child", name="Child", start_time=0, end_time=5, status="done")

        root.add_child(child)
        tree = TaskTree(root)

        stats = tree.get_timing_stats()

        assert stats["total"] == 15  # 10 + 5
        assert stats["average"] == 7.5
        assert stats["count"] == 2
        assert stats["min"] == 5
        assert stats["max"] == 10

    def test_get_timing_stats_no_timing(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        stats = tree.get_timing_stats()

        assert stats["total"] == 0
        assert stats["count"] == 0

    def test_reset(self):
        root = TaskNode(id="root", name="Root", status="done", retry_count=2)
        child = TaskNode(id="child", name="Child", status="failed", error="Error")

        root.add_child(child)
        tree = TaskTree(root)

        tree.reset()

        assert root.status == "pending"
        assert root.retry_count == 0
        assert child.status == "pending"
        assert child.error is None

    def test_str_representation(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        s = str(tree)
        assert "root" in s or "Root" in s or "TaskTree" in s

    def test_unregister_node(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        root.add_child(child)
        tree = TaskTree(root)

        # Node should be findable
        assert tree.find("child") is not None

        # Unregister it
        tree.unregister_node("child")

        # Should not be findable by index anymore
        assert tree.find("child") is None


class TestTaskNodeAdditional:
    def test_remove_child(self):
        parent = TaskNode(id="parent", name="Parent")
        child = TaskNode(id="child", name="Child")
        parent.add_child(child)

        assert len(parent.children) == 1

        result = parent.remove_child(child)

        assert result is True
        assert len(parent.children) == 0
        assert child.parent is None

    def test_remove_child_not_found(self):
        parent = TaskNode(id="parent", name="Parent")
        other = TaskNode(id="other", name="Other")

        result = parent.remove_child(other)

        assert result is False

    def test_is_done_true(self):
        for status in ["done", "failed", "cancelled", "skipped", "timed_out"]:
            node = TaskNode(id="test", name="Test", status=status)
            assert node.is_done() is True

    def test_is_done_false(self):
        for status in ["pending", "working", "retrying"]:
            node = TaskNode(id="test", name="Test", status=status)
            assert node.is_done() is False

    def test_is_successful(self):
        node_done = TaskNode(id="test", name="Test", status="done")
        node_failed = TaskNode(id="test", name="Test", status="failed")

        assert node_done.is_successful() is True
        assert node_failed.is_successful() is False

    def test_get_root(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child)
        child.add_child(grandchild)

        assert grandchild.get_root() is root
        assert child.get_root() is root
        assert root.get_root() is root

    def test_find_child(self):
        parent = TaskNode(id="parent", name="Parent")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")

        parent.add_child(child1)
        parent.add_child(child2)

        found = parent.find_child("child1")
        assert found is child1

        not_found = parent.find_child("nonexistent")
        assert not_found is None

    def test_reset(self):
        node = TaskNode(
            id="test",
            name="Test",
            status="failed",
            retry_count=3,
            error="Some error",
            start_time=100.0,
            end_time=110.0,
            result={"data": "value"},
        )

        node.reset()

        assert node.status == "pending"
        assert node.retry_count == 0
        assert node.error is None
        assert node.start_time is None
        assert node.end_time is None
        assert node.result is None

    def test_walk(self):
        """Test that node.walk() yields self and all descendants."""
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child1)
        root.add_child(child2)
        child1.add_child(grandchild)

        walked = list(root.walk())
        walked_ids = [n.id for n in walked]

        assert len(walked) == 4
        assert "root" in walked_ids
        assert "child1" in walked_ids
        assert "child2" in walked_ids
        assert "grandchild" in walked_ids

    def test_walk_from_child(self):
        """Test walk() starting from a child node."""
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")

        root.add_child(child)
        child.add_child(grandchild)

        # Walk from child should only get child and its descendants
        walked = list(child.walk())
        walked_ids = [n.id for n in walked]

        assert len(walked) == 2
        assert "child" in walked_ids
        assert "grandchild" in walked_ids
        assert "root" not in walked_ids
