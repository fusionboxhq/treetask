"""Tests for tree serialization."""

import json
import pytest
from treetask.core import TaskNode, TaskTree
from treetask.config import TreeTaskConfig
from treetask.serialization import TreeSerializer, create_task_registry


async def dummy_task(node):
    return {"result": "done"}


class TestTreeSerializer:
    def test_node_to_dict(self):
        node = TaskNode(
            id="test",
            name="Test Node",
            status="done",
            data={"key": "value"},
            progress=(5, 10),
            retry_count=1,
            parallel=True,
        )

        result = TreeSerializer.node_to_dict(node)

        assert result["id"] == "test"
        assert result["name"] == "Test Node"
        assert result["status"] == "done"
        assert result["data"] == {"key": "value"}
        assert result["progress"] == [5, 10]
        assert result["retry_count"] == 1
        assert result["parallel"] is True
        assert result["children"] == []

    def test_node_to_dict_with_children(self):
        parent = TaskNode(id="parent", name="Parent")
        child1 = TaskNode(id="child1", name="Child 1")
        child2 = TaskNode(id="child2", name="Child 2")
        parent.add_child(child1)
        parent.add_child(child2)

        result = TreeSerializer.node_to_dict(parent)

        assert len(result["children"]) == 2
        assert result["children"][0]["id"] == "child1"
        assert result["children"][1]["id"] == "child2"

    def test_node_to_dict_filters_non_serializable_data(self):
        node = TaskNode(
            id="test",
            name="Test",
            data={
                "serializable": "value",
                "function": lambda x: x,  # Not serializable
            },
        )

        result = TreeSerializer.node_to_dict(node)

        assert result["data"] == {"serializable": "value"}

    def test_tree_to_dict(self):
        root = TaskNode(id="root", name="Root")
        child = TaskNode(id="child", name="Child")
        root.add_child(child)
        tree = TaskTree(root)

        result = TreeSerializer.tree_to_dict(tree)

        assert result["version"] == "1.0"
        assert result["root"]["id"] == "root"
        assert len(result["root"]["children"]) == 1

    def test_tree_to_json(self):
        root = TaskNode(id="root", name="Root")
        tree = TaskTree(root)

        json_str = TreeSerializer.tree_to_json(tree)
        parsed = json.loads(json_str)

        assert parsed["root"]["id"] == "root"

    def test_dict_to_node(self):
        data = {
            "id": "test",
            "name": "Test Node",
            "status": "done",
            "data": {"key": "value"},
            "progress": [5, 10],
            "retry_count": 1,
            "parallel": True,
            "children": [],
        }

        node = TreeSerializer.dict_to_node(data)

        assert node.id == "test"
        assert node.name == "Test Node"
        assert node.status == "done"
        assert node.data == {"key": "value"}
        assert node.progress == (5, 10)
        assert node.retry_count == 1
        assert node.parallel is True

    def test_dict_to_node_with_task_registry(self):
        data = {
            "id": "test",
            "name": "Test",
            "children": [],
        }

        registry = {"test": dummy_task}
        node = TreeSerializer.dict_to_node(data, task_registry=registry)

        assert node.task_fn is dummy_task

    def test_dict_to_node_with_children(self):
        data = {
            "id": "parent",
            "name": "Parent",
            "children": [
                {"id": "child1", "name": "Child 1", "children": []},
                {"id": "child2", "name": "Child 2", "children": []},
            ],
        }

        node = TreeSerializer.dict_to_node(data)

        assert len(node.children) == 2
        assert node.children[0].id == "child1"
        assert node.children[1].id == "child2"
        assert node.children[0].parent is node

    def test_tree_from_json(self):
        json_str = '''
        {
            "version": "1.0",
            "root": {
                "id": "root",
                "name": "Root",
                "status": "done",
                "children": [
                    {"id": "child", "name": "Child", "children": []}
                ]
            },
            "config": {}
        }
        '''

        tree = TreeSerializer.tree_from_json(json_str)

        assert tree.root.id == "root"
        assert tree.root.status == "done"
        assert len(tree.root.children) == 1
        assert tree.find("child") is not None

    def test_roundtrip(self):
        # Create a tree
        root = TaskNode(id="root", name="Root", status="done")
        child1 = TaskNode(
            id="child1",
            name="Child 1",
            status="done",
            data={"value": 42},
            progress=(10, 10),
        )
        child2 = TaskNode(id="child2", name="Child 2", status="failed", error="Test error")
        root.add_child(child1)
        root.add_child(child2)
        tree = TaskTree(root)

        # Serialize
        json_str = TreeSerializer.tree_to_json(tree)

        # Deserialize
        restored = TreeSerializer.tree_from_json(json_str)

        # Verify
        assert restored.root.id == "root"
        assert restored.root.status == "done"
        assert len(restored.root.children) == 2

        c1 = restored.find("child1")
        assert c1.data == {"value": 42}
        assert c1.progress == (10, 10)

        c2 = restored.find("child2")
        assert c2.status == "failed"
        assert c2.error == "Test error"


class TestCreateTaskRegistry:
    def test_creates_registry(self):
        async def task1(node):
            pass

        async def task2(node):
            pass

        registry = create_task_registry(
            ("id1", task1),
            ("id2", task2),
        )

        assert registry["id1"] is task1
        assert registry["id2"] is task2

    def test_empty_registry(self):
        registry = create_task_registry()
        assert registry == {}
