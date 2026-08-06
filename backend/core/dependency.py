"""Dependency graph — manages nodes and tracks rebuild requirements.

The graph:
- Maintains a registry of all nodes
- Tracks which nodes depend on which (reverse edges)
- When an input changes, marks affected nodes dirty
- Provides topological order for rebuilding
- Detects cycles

Usage:
    graph = DependencyGraph()
    graph.add_node(airfoil_node)
    graph.add_node(station_node)
    station_node.add_dependency("airfoil_naca2412")
    graph.add_edge("airfoil_naca2412", "station_node")
    ...
    # When config changes:
    graph.invalidate("config_hash")
    dirty = graph.get_dirty_nodes()
    for node_id in graph.topological_order(dirty):
        graph.nodes[node_id].build()
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from backend.core.node import GeometryNode, NodeState


class DependencyGraph:
    """Directed acyclic graph (DAG) of geometry nodes.

    Attributes:
        nodes: registry of all nodes by id.
        dependents: reverse mapping — node_id → set of node_ids that depend on it.
        dependencies: forward mapping — node_id → set of node_ids it depends on.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GeometryNode] = {}
        self.dependents: dict[str, set[str]] = defaultdict(set)
        self.dependencies: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node: GeometryNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges."""
        if node_id not in self.nodes:
            return
        # Remove from dependents
        for dep in self.dependents.get(node_id, set()):
            self.dependencies[dep].discard(node_id)
        # Remove from dependencies
        for dep in self.dependencies.get(node_id, set()):
            self.dependents[dep].discard(node_id)
        del self.nodes[node_id]
        self.dependents.pop(node_id, None)
        self.dependencies.pop(node_id, None)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Declare that to_id depends on from_id."""
        self.dependents[from_id].add(to_id)
        self.dependencies[to_id].add(from_id)

    def invalidate(self, root_id: str, changed_inputs: set[str] | None = None) -> list[str]:
        """Invalidate a node and all downstream nodes.

        Uses BFS to find all affected nodes.

        Args:
            root_id: the node that changed.
            changed_inputs: specific input keys that changed.

        Returns:
            List of all dirty node ids (in BFS order).
        """
        if root_id not in self.nodes:
            return []

        dirty = []
        queue = deque([root_id])
        visited = {root_id}

        while queue:
            node_id = queue.popleft()
            node = self.nodes[node_id]
            node.invalidate(changed_inputs)
            dirty.append(node_id)

            # Propagate to dependents
            for dep_id in self.dependents.get(node_id, set()):
                if dep_id not in visited:
                    visited.add(dep_id)
                    queue.append(dep_id)

        return dirty

    def get_dirty_nodes(self) -> list[str]:
        """Get all nodes that need rebuilding."""
        return [nid for nid, node in self.nodes.items() if node.needs_rebuild()]

    def topological_order(self, node_ids: list[str] | None = None) -> list[str]:
        """Return nodes in topological order (dependencies first).

        Args:
            node_ids: subset of nodes to order (default: all).

        Returns:
            List of node ids in topological order.

        Raises:
            ValueError: if there's a cycle in the graph.
        """
        if node_ids is None:
            node_ids = list(self.nodes.keys())

        # Build in-degree map for subset
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        for nid in node_ids:
            for dep in self.dependencies.get(nid, set()):
                if dep in in_degree:
                    in_degree[nid] += 1

        # Kahn's algorithm
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node_id = queue.popleft()
            order.append(node_id)

            for dep in self.dependents.get(node_id, set()):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        if len(order) != len(node_ids):
            raise ValueError("Cycle detected in dependency graph")

        return order

    def rebuild_all(self) -> dict[str, Any]:
        """Rebuild all dirty nodes in topological order.

        Returns:
            Dict of node_id → output for each rebuilt node.
        """
        dirty = self.get_dirty_nodes()
        if not dirty:
            return {}

        order = self.topological_order(dirty)
        results: dict[str, Any] = {}

        for node_id in order:
            node = self.nodes[node_id]
            if node.needs_rebuild():
                try:
                    node.build()
                    results[node_id] = node.output
                except Exception as e:
                    results[node_id] = {"error": str(e)}

        return results

    def stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        return {
            "total_nodes": len(self.nodes),
            "dirty_nodes": len(self.get_dirty_nodes()),
            "edges": sum(len(deps) for deps in self.dependencies.values()),
        }
