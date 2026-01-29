"""Tests for dependency resolution."""

import pytest
from treetask.core import TaskNode, TaskTree
from treetask.dependencies import DependencyResolver, CyclicDependencyError


class TestDependencyResolver:
    def test_no_dependencies(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # Root has no deps, children depend on root (implicit)
        assert resolver.get_dependencies("root") == set()
        assert "root" in resolver.get_dependencies("child1")
        assert "root" in resolver.get_dependencies("child2")

    def test_explicit_dependencies(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # task_b depends on task_a AND root (implicit)
        deps = resolver.get_dependencies("task_b")
        assert "task_a" in deps
        assert "root" in deps

    def test_get_dependents(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # task_a has task_b as dependent
        dependents = resolver.get_dependents("task_a")
        assert "task_b" in dependents

    def test_is_ready(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # Root is ready immediately
        assert resolver.is_ready("root", set()) is True

        # task_a needs root
        assert resolver.is_ready("task_a", set()) is False
        assert resolver.is_ready("task_a", {"root"}) is True

        # task_b needs root and task_a
        assert resolver.is_ready("task_b", {"root"}) is False
        assert resolver.is_ready("task_b", {"root", "task_a"}) is True

    def test_get_ready_nodes(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # Initially only root is ready
        ready = resolver.get_ready_nodes(set())
        assert len(ready) == 1
        assert ready[0].id == "root"

        # After root completes, task_a is ready
        ready = resolver.get_ready_nodes({"root"})
        ready_ids = [n.id for n in ready]
        assert "task_a" in ready_ids
        assert "task_b" not in ready_ids

        # After task_a completes, task_b is ready
        ready = resolver.get_ready_nodes({"root", "task_a"})
        ready_ids = [n.id for n in ready]
        assert "task_b" in ready_ids

    def test_topological_order(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B")
        task_c = TaskNode(id="task_c", name="Task C", depends_on=["task_a", "task_b"])
        root.add_child(task_a)
        root.add_child(task_b)
        root.add_child(task_c)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        order = list(resolver.topological_order())
        order_ids = [n.id for n in order]

        # Root must be first
        assert order_ids[0] == "root"

        # task_a and task_b must come before task_c
        assert order_ids.index("task_a") < order_ids.index("task_c")
        assert order_ids.index("task_b") < order_ids.index("task_c")

    def test_detect_cycles_no_cycle(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        cycles = resolver.detect_cycles()

        assert cycles == []

    def test_detect_cycles_with_cycle(self):
        # Create a cycle: task_a -> task_b -> task_a
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A", depends_on=["task_b"])
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        cycles = resolver.detect_cycles()

        assert len(cycles) > 0

    def test_topological_order_raises_on_cycle(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A", depends_on=["task_b"])
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        with pytest.raises(CyclicDependencyError):
            list(resolver.topological_order())

    def test_validate_missing_dependency(self):
        root = TaskNode(id="root", name="Root")
        task = TaskNode(id="task", name="Task", depends_on=["nonexistent"])
        root.add_child(task)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        errors = resolver.validate()

        assert len(errors) > 0
        assert "nonexistent" in errors[0]

    def test_validate_no_errors(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        errors = resolver.validate()

        assert errors == []

    def test_get_execution_levels(self):
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A")
        task_b = TaskNode(id="task_b", name="Task B")
        task_c = TaskNode(id="task_c", name="Task C", depends_on=["task_a", "task_b"])
        root.add_child(task_a)
        root.add_child(task_b)
        root.add_child(task_c)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        levels = resolver.get_execution_levels()

        # Level 0: root
        # Level 1: task_a, task_b
        # Level 2: task_c
        assert len(levels) == 3
        assert levels[0][0].id == "root"
        assert set(n.id for n in levels[1]) == {"task_a", "task_b"}
        assert levels[2][0].id == "task_c"

    def test_get_ready_nodes_skips_completed(self):
        """Test that get_ready_nodes skips already completed nodes."""
        root = TaskNode(id="root", name="Root", status="done")
        task_a = TaskNode(id="task_a", name="Task A", status="done")
        task_b = TaskNode(id="task_b", name="Task B")
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # task_a is already in completed, so it should be skipped
        ready = resolver.get_ready_nodes({"root", "task_a"})
        ready_ids = [n.id for n in ready]

        assert "task_a" not in ready_ids
        assert "task_b" in ready_ids

    def test_get_ready_nodes_skips_working_status(self):
        """Test that get_ready_nodes skips nodes with non-pending status."""
        root = TaskNode(id="root", name="Root", status="done")
        task_a = TaskNode(id="task_a", name="Task A", status="working")
        task_b = TaskNode(id="task_b", name="Task B", status="pending")
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # Only pending nodes should be returned
        ready = resolver.get_ready_nodes({"root"})
        ready_ids = [n.id for n in ready]

        assert "task_a" not in ready_ids  # working status
        assert "task_b" in ready_ids  # pending status

    def test_get_execution_levels_with_cycle(self):
        """Test that get_execution_levels handles cycles gracefully."""
        root = TaskNode(id="root", name="Root")
        task_a = TaskNode(id="task_a", name="Task A", depends_on=["task_b"])
        task_b = TaskNode(id="task_b", name="Task B", depends_on=["task_a"])
        root.add_child(task_a)
        root.add_child(task_b)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)
        levels = resolver.get_execution_levels()

        # Should only contain root since task_a and task_b are in a cycle
        assert len(levels) == 1
        assert levels[0][0].id == "root"

    def test_parent_dependency_added_to_reverse_graph(self):
        """Test that parent dependencies are properly added to reverse_graph."""
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")
        root.add_child(child)
        child.add_child(grandchild)
        tree = TaskTree(root)

        resolver = DependencyResolver(tree)

        # Child depends on root (implicit parent dep)
        assert "root" in resolver.get_dependencies("child")
        # Root has child as a dependent
        assert "child" in resolver.get_dependents("root")
        # Child has grandchild as a dependent
        assert "grandchild" in resolver.get_dependents("child")
