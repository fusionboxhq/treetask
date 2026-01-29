"""Serialization for saving and restoring task tree state."""

import json
from dataclasses import asdict
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import TaskNode, TaskTree, TaskFunction
    from .config import TreeTaskConfig


class TreeSerializer:
    """Serialize and deserialize task trees to/from JSON.

    Saves tree structure and node state but NOT task functions (which cannot
    be serialized). When restoring, you must provide a task registry mapping
    node IDs to their task functions.

    Example:
        >>> # Save tree state
        >>> json_str = TreeSerializer.tree_to_json(tree)
        >>> with open("checkpoint.json", "w") as f:
        ...     f.write(json_str)
        >>>
        >>> # Later, restore and continue
        >>> task_registry = {
        ...     "fetch": fetch_data,
        ...     "process": process_data,
        ... }
        >>> with open("checkpoint.json") as f:
        ...     json_str = f.read()
        >>> tree = TreeSerializer.tree_from_json(json_str, task_registry)
        >>> executor = AsyncExecutor(tree, skip_completed=True)
        >>> await executor.run()
    """

    VERSION = "1.0"

    @staticmethod
    def _is_json_serializable(value: Any) -> bool:
        """Check if a value can be JSON serialized."""
        try:
            json.dumps(value)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def node_to_dict(node: "TaskNode") -> dict[str, Any]:
        """Convert a TaskNode to a serializable dictionary.

        Args:
            node: The node to serialize.

        Returns:
            Dictionary representation of the node.
        """
        # Serialize result only if it's JSON-compatible
        result = node.result if TreeSerializer._is_json_serializable(node.result) else None

        # Serialize data, filtering out non-serializable values
        data = {}
        for key, value in node.data.items():
            if TreeSerializer._is_json_serializable(value):
                data[key] = value

        return {
            "id": node.id,
            "name": node.name,
            "status": node.status,
            "data": data,
            "progress": list(node.progress) if node.progress else None,
            "retry_count": node.retry_count,
            "error": node.error,
            "parallel": node.parallel,
            "start_time": node.start_time,
            "end_time": node.end_time,
            "timeout": node.timeout,
            "max_retries": node.max_retries,
            "depends_on": list(node.depends_on) if node.depends_on else [],
            "result": result,
            "children": [TreeSerializer.node_to_dict(c) for c in node.children],
            # NOT serialized: task_fn, skip_condition, run_condition, retry_strategy
        }

    @staticmethod
    def config_to_dict(config: "TreeTaskConfig") -> dict[str, Any]:
        """Convert TreeTaskConfig to a serializable dictionary.

        Args:
            config: The config to serialize.

        Returns:
            Dictionary representation of serializable config fields.
        """
        return {
            "default_max_depth": config.default_max_depth,
            "final_max_depth": config.final_max_depth,
            "refresh_interval": config.refresh_interval,
            "icons": dict(config.icons),
            "tree_chars": dict(config.tree_chars),
            "default_parallel": config.default_parallel,
            "max_retries": config.max_retries,
            "global_timeout": getattr(config, "global_timeout", None),
            "default_task_timeout": getattr(config, "default_task_timeout", None),
            "max_concurrency": getattr(config, "max_concurrency", None),
        }

    @staticmethod
    def tree_to_dict(tree: "TaskTree") -> dict[str, Any]:
        """Convert a TaskTree to a serializable dictionary.

        Args:
            tree: The tree to serialize.

        Returns:
            Dictionary representation of the tree.
        """
        return {
            "version": TreeSerializer.VERSION,
            "root": TreeSerializer.node_to_dict(tree.root),
            "config": TreeSerializer.config_to_dict(tree.config),
        }

    @staticmethod
    def tree_to_json(tree: "TaskTree", indent: int = 2) -> str:
        """Serialize a TaskTree to a JSON string.

        Args:
            tree: The tree to serialize.
            indent: JSON indentation level.

        Returns:
            JSON string representation.
        """
        return json.dumps(TreeSerializer.tree_to_dict(tree), indent=indent)

    @staticmethod
    def dict_to_node(
        data: dict[str, Any],
        task_registry: Optional[Dict[str, "TaskFunction"]] = None,
        condition_registry: Optional[Dict[str, Callable]] = None,
    ) -> "TaskNode":
        """Convert a dictionary back to a TaskNode.

        Args:
            data: Dictionary representation of a node.
            task_registry: Mapping of node IDs to task functions.
            condition_registry: Mapping of node IDs to condition functions.

        Returns:
            Reconstructed TaskNode.
        """
        from .core import TaskNode

        task_registry = task_registry or {}
        condition_registry = condition_registry or {}

        node = TaskNode(
            id=data["id"],
            name=data["name"],
            status=data.get("status", "pending"),
            data=data.get("data", {}),
            progress=tuple(data["progress"]) if data.get("progress") else None,
            retry_count=data.get("retry_count", 0),
            error=data.get("error"),
            parallel=data.get("parallel", True),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            timeout=data.get("timeout"),
            max_retries=data.get("max_retries"),
            depends_on=data.get("depends_on", []),
            result=data.get("result"),
            task_fn=task_registry.get(data["id"]),
            skip_condition=condition_registry.get(f"{data['id']}_skip"),
            run_condition=condition_registry.get(f"{data['id']}_run"),
        )

        # Recursively reconstruct children
        for child_data in data.get("children", []):
            child = TreeSerializer.dict_to_node(
                child_data, task_registry, condition_registry
            )
            node.add_child(child)

        return node

    @staticmethod
    def dict_to_config(data: dict[str, Any]) -> "TreeTaskConfig":
        """Convert a dictionary to TreeTaskConfig.

        Args:
            data: Dictionary representation of config.

        Returns:
            Reconstructed TreeTaskConfig.
        """
        from .config import TreeTaskConfig

        return TreeTaskConfig(
            default_max_depth=data.get("default_max_depth", 2),
            final_max_depth=data.get("final_max_depth", 3),
            refresh_interval=data.get("refresh_interval", 0.1),
            icons=data.get("icons", {}),
            tree_chars=data.get("tree_chars", {}),
            default_parallel=data.get("default_parallel", True),
            max_retries=data.get("max_retries", 3),
        )

    @staticmethod
    def tree_from_dict(
        data: dict[str, Any],
        task_registry: Optional[Dict[str, "TaskFunction"]] = None,
        condition_registry: Optional[Dict[str, Callable]] = None,
    ) -> "TaskTree":
        """Convert a dictionary to a TaskTree.

        Args:
            data: Dictionary representation of a tree.
            task_registry: Mapping of node IDs to task functions.
            condition_registry: Mapping of node IDs to condition functions.

        Returns:
            Reconstructed TaskTree.
        """
        from .core import TaskTree

        root = TreeSerializer.dict_to_node(
            data["root"], task_registry, condition_registry
        )
        config = TreeSerializer.dict_to_config(data.get("config", {}))
        return TaskTree(root, config)

    @staticmethod
    def tree_from_json(
        json_str: str,
        task_registry: Optional[Dict[str, "TaskFunction"]] = None,
        condition_registry: Optional[Dict[str, Callable]] = None,
    ) -> "TaskTree":
        """Deserialize a TaskTree from a JSON string.

        Args:
            json_str: JSON string representation.
            task_registry: Mapping of node IDs to task functions.
            condition_registry: Mapping of node IDs to condition functions.

        Returns:
            Reconstructed TaskTree.
        """
        data = json.loads(json_str)
        return TreeSerializer.tree_from_dict(data, task_registry, condition_registry)

    @staticmethod
    def save_to_file(tree: "TaskTree", filepath: str) -> None:
        """Save a TaskTree to a JSON file.

        Args:
            tree: The tree to save.
            filepath: Path to the output file.
        """
        with open(filepath, "w") as f:
            f.write(TreeSerializer.tree_to_json(tree))

    @staticmethod
    def load_from_file(
        filepath: str,
        task_registry: Optional[Dict[str, "TaskFunction"]] = None,
        condition_registry: Optional[Dict[str, Callable]] = None,
    ) -> "TaskTree":
        """Load a TaskTree from a JSON file.

        Args:
            filepath: Path to the input file.
            task_registry: Mapping of node IDs to task functions.
            condition_registry: Mapping of node IDs to condition functions.

        Returns:
            Reconstructed TaskTree.
        """
        with open(filepath, "r") as f:
            return TreeSerializer.tree_from_json(
                f.read(), task_registry, condition_registry
            )


def create_task_registry(*tasks: tuple[str, "TaskFunction"]) -> Dict[str, "TaskFunction"]:
    """Helper to create a task registry from (id, function) pairs.

    Args:
        *tasks: Tuples of (node_id, task_function).

    Returns:
        Task registry dictionary.

    Example:
        >>> registry = create_task_registry(
        ...     ("fetch", fetch_data),
        ...     ("process", process_data),
        ...     ("save", save_results),
        ... )
    """
    return {task_id: func for task_id, func in tasks}
