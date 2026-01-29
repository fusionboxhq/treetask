"""Tests for TreeRenderer."""

from treetask.core import TaskNode, TaskTree
from treetask.config import TreeTaskConfig
from treetask.renderer import TreeRenderer


class TestTreeRenderer:
    def test_render_simple_tree(self):
        root = TaskNode(id="root", name="Root", status="done")
        child = TaskNode(id="child", name="Child", status="done")
        root.add_child(child)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        assert "Root" in output
        assert "Child" in output

    def test_render_with_default_config(self):
        root = TaskNode(id="root", name="Root", status="pending")
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        assert "Root" in output

    def test_render_with_custom_config(self):
        config = TreeTaskConfig(icons={"done": "[OK]", "pending": "[...]"})
        root = TaskNode(id="root", name="Root", status="done")
        tree = TaskTree(root)

        renderer = TreeRenderer(config)
        output = renderer.render(tree)

        assert "[OK]" in output

    def test_render_with_progress(self):
        root = TaskNode(id="root", name="Root", progress=(5, 10))
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        assert "(5/10)" in output

    def test_render_with_max_depth(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        grandchild = TaskNode(id="grandchild", name="Grandchild")
        root.add_child(child)
        child.add_child(grandchild)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree, max_depth=1)

        assert "Root" in output
        assert "Child" in output
        # Should show collapsed indicator
        assert "..." in output or "1 items" in output

    def test_render_with_stats(self):
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="done", progress=(1, 1))
        child2 = TaskNode(id="child2", name="Child 2", status="pending", progress=(0, 1))
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree, show_stats=True)

        assert "Progress:" in output

    def test_render_multiple_children(self):
        root = TaskNode(id="root", name="Root")
        for i in range(3):
            child = TaskNode(id=f"child{i}", name=f"Child {i}")
            root.add_child(child)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        assert "Child 0" in output
        assert "Child 1" in output
        assert "Child 2" in output

    def test_render_nested_tree(self):
        root = TaskNode(id="root", name="Root")
        level1 = TaskNode(id="level1", name="Level 1")
        level2 = TaskNode(id="level2", name="Level 2")
        level3 = TaskNode(id="level3", name="Level 3")
        root.add_child(level1)
        level1.add_child(level2)
        level2.add_child(level3)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        assert "Root" in output
        assert "Level 1" in output
        assert "Level 2" in output
        assert "Level 3" in output

    def test_render_retrying_status(self):
        config = TreeTaskConfig(max_retries=3)
        root = TaskNode(id="root", name="Root", status="retrying", retry_count=2)
        tree = TaskTree(root, config)

        renderer = TreeRenderer(config)
        output = renderer.render(tree)

        assert "2/3" in output  # retry count / max retries

    def test_render_unknown_status(self):
        root = TaskNode(id="root", name="Root", status="unknown_status")
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        # Should show unknown status icon
        assert "Root" in output

    def test_render_node_line(self):
        node = TaskNode(id="test", name="Test Node", status="done")

        renderer = TreeRenderer()
        output = renderer.render_node_line(node)

        assert "Test Node" in output

    def test_render_node_line_with_progress(self):
        node = TaskNode(id="test", name="Test Node", progress=(3, 5))

        renderer = TreeRenderer()
        output = renderer.render_node_line(node)

        assert "Test Node" in output
        assert "(3/5)" in output

    def test_format_stats_all_statuses(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="c1", name="C1", status="done")
        child2 = TaskNode(id="c2", name="C2", status="working")
        child3 = TaskNode(id="c3", name="C3", status="pending")
        child4 = TaskNode(id="c4", name="C4", status="failed")
        root.add_child(child1)
        root.add_child(child2)
        root.add_child(child3)
        root.add_child(child4)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        # Test _format_stats indirectly through render
        stats = tree.get_leaf_stats()
        output = renderer._format_stats(stats)

        assert "Total:" in output

    def test_format_progress_stats_with_total(self):
        renderer = TreeRenderer()
        stats = {"current": 5, "total": 10, "nodes_with_progress": 2}

        output = renderer._format_progress_stats(stats)

        assert "Progress: 5/10" in output
        assert "50%" in output

    def test_format_progress_stats_zero_total(self):
        renderer = TreeRenderer()
        stats = {"current": 0, "total": 0, "nodes_with_progress": 0}

        output = renderer._format_progress_stats(stats)

        assert "Progress: 0/0 (0%)" in output

    def test_tree_chars_structure(self):
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        # Check tree structure characters are present
        assert "├" in output or "└" in output

    def test_render_deep_tree_with_vertical_lines(self):
        """Test rendering a deep tree where vertical lines are used for non-last children."""
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child1_a = TaskNode(id="child1_a", name="Child 1a")
        child2 = TaskNode(id="child2", name="Child 2")
        root.add_child(child1)
        root.add_child(child2)
        child1.add_child(child1_a)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree)

        # Should contain vertical bar for non-last child continuation
        assert "│" in output
        assert "Child 1a" in output

    def test_render_collapsed_at_root_level(self):
        """Test collapsing children when max_depth=0."""
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree, max_depth=0)

        assert "Root" in output
        # Should show collapsed indicator
        assert "..." in output
        assert "2 items" in output

    def test_render_collapsed_nested_children(self):
        """Test collapsing at depth 1 with nested children."""
        root = TaskNode(id="root", name="Root")
        child1 = TaskNode(id="child1", name="Child 1")
        grandchild = TaskNode(id="grandchild", name="Grandchild")
        child1.add_child(grandchild)
        child2 = TaskNode(id="child2", name="Child 2")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree, max_depth=1)

        assert "Root" in output
        assert "Child 1" in output
        assert "Child 2" in output
        # Child 1's children should be collapsed
        assert "..." in output

    def test_render_stats_without_progress_nodes(self):
        """Test render with show_stats when no nodes have progress."""
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(id="child1", name="Child 1", status="done")
        child2 = TaskNode(id="child2", name="Child 2", status="pending")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        renderer = TreeRenderer()
        output = renderer.render(tree, show_stats=True)

        # Should show leaf stats format
        assert "Total:" in output
