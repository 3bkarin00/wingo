"""Gate P06 — Dependency graph (DAG wiring, topological order, cycle detection).

Tests:
1. DependencyGraph creates nodes, edges, and tracks dependencies
2. invalidate() propagates dirty state to all downstream nodes via BFS
3. topological_order() returns valid ordering (dependencies before dependents)
4. Cycle detection raises ValueError
5. GeometryNode builds, invalidates, and tracks state correctly
6. rebuild_all() rebuilds all dirty nodes in order
7. Graph stats are correct
8. Remove node cleans up edges
"""
from __future__ import annotations

import pytest

from backend.core.dependency import DependencyGraph
from backend.core.node import GeometryNode, NodeState


# ── 1. GeometryNode basics ─────────────────────────────────────────────────


def test_node_initial_state():
    """New node starts CLEAN with no output."""
    node = GeometryNode(id="test")
    assert node.state == NodeState.CLEAN
    assert node.output is None
    assert node.error is None


def test_node_build():
    """build() executes build_fn and sets output."""
    node = GeometryNode(id="test", build_fn=lambda: 42)
    result = node.build()
    assert result == 42
    assert node.output == 42
    assert node.state == NodeState.CLEAN


def test_node_build_error():
    """build() sets ERROR state on failure."""
    node = GeometryNode(id="test", build_fn=lambda: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        node.build()
    assert node.state == NodeState.ERROR
    assert node.error is not None


def test_node_add_input():
    """add_input() records value and marks dirty."""
    node = GeometryNode(id="test")
    node.add_input("key", "value")
    assert "key" in node.inputs
    assert node._input_values["key"] == "value"
    assert node.state == NodeState.DIRTY


def test_node_needs_rebuild():
    """needs_rebuild() returns True for DIRTY nodes."""
    node = GeometryNode(id="test")
    assert node.needs_rebuild() is False  # CLEAN
    node.invalidate()
    assert node.needs_rebuild() is True  # DIRTY


def test_node_repr():
    """__repr__ shows id and state."""
    node = GeometryNode(id="wing")
    assert repr(node) == "Node(wing, state=clean)"


# ── 2. DependencyGraph basics ──────────────────────────────────────────────


def test_graph_add_node():
    """add_node() registers node in registry."""
    graph = DependencyGraph()
    node = GeometryNode(id="test")
    graph.add_node(node)
    assert "test" in graph.nodes


def test_graph_add_edge():
    """add_edge() creates forward and reverse mappings."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    graph.add_node(GeometryNode(id="b"))
    graph.add_edge("a", "b")

    assert "b" in graph.dependents["a"]
    assert "a" in graph.dependencies["b"]


def test_graph_remove_node():
    """remove_node() cleans up all edges."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    graph.add_node(GeometryNode(id="b"))
    graph.add_edge("a", "b")

    graph.remove_node("a")
    assert "a" not in graph.nodes
    assert "a" not in graph.dependents
    assert "a" not in graph.dependencies
    assert "b" not in graph.dependents.get("a", set())


# ── 3. Invalidation propagation ────────────────────────────────────────────


def test_invalidate_single_node():
    """invalidate() marks the root node dirty."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    dirty = graph.invalidate("a")
    assert "a" in dirty
    assert graph.nodes["a"].state == NodeState.DIRTY


def test_invalidate_propagates_downstream():
    """invalidate() propagates to all dependents via BFS."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    graph.add_node(GeometryNode(id="b"))
    graph.add_node(GeometryNode(id="c"))
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")

    dirty = graph.invalidate("a")
    assert "a" in dirty
    assert "b" in dirty
    assert "c" in dirty
    assert graph.nodes["a"].state == NodeState.DIRTY
    assert graph.nodes["b"].state == NodeState.DIRTY
    assert graph.nodes["c"].state == NodeState.DIRTY


def test_invalidate_nonexistent_node():
    """invalidate() on unknown node returns empty list."""
    graph = DependencyGraph()
    dirty = graph.invalidate("nonexistent")
    assert dirty == []


def test_invalidate_with_specific_inputs():
    """invalidate() with changed_inputs marks only relevant nodes."""
    graph = DependencyGraph()
    node_a = GeometryNode(id="a")
    node_a.add_input("chord_mm", 300)
    graph.add_node(node_a)

    # Invalidate with matching input
    dirty = graph.invalidate("a", changed_inputs={"chord_mm"})
    assert "a" in dirty

    # Invalidate with non-matching input
    node_b = GeometryNode(id="b")
    graph.add_node(node_b)
    dirty = graph.invalidate("b", changed_inputs={"twist_deg"})
    assert "b" in dirty  # root always added


# ── 4. Topological order ──────────────────────────────────────────────────


def test_topological_order_basic():
    """topological_order() returns dependencies before dependents."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    graph.add_node(GeometryNode(id="b"))
    graph.add_node(GeometryNode(id="c"))
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")

    order = graph.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("b") < order.index("c")


def test_topological_order_convergent():
    """Diamond DAG: a→b, a→c, b→d, c→d — d after both b and c."""
    graph = DependencyGraph()
    for nid in ["a", "b", "c", "d"]:
        graph.add_node(GeometryNode(id=nid))
    graph.add_edge("a", "b")
    graph.add_edge("a", "c")
    graph.add_edge("b", "d")
    graph.add_edge("c", "d")

    order = graph.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_topological_order_detects_cycle():
    """topological_order() raises ValueError on cycle."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    graph.add_node(GeometryNode(id="b"))
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")  # cycle

    with pytest.raises(ValueError, match="Cycle"):
        graph.topological_order()


# ── 5. rebuild_all ─────────────────────────────────────────────────────────


def test_rebuild_all_rebuilds_dirty():
    """rebuild_all() builds all dirty nodes in topological order."""
    graph = DependencyGraph()
    counter = {"count": 0}

    def build_fn():
        counter["count"] += 1
        return counter["count"]

    for nid in ["a", "b", "c"]:
        graph.add_node(GeometryNode(id=nid, build_fn=build_fn))
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")

    # Invalidate all
    graph.invalidate("a")

    results = graph.rebuild_all()
    assert len(results) == 3
    assert counter["count"] == 3


def test_rebuild_all_no_dirty():
    """rebuild_all() returns empty when nothing is dirty."""
    graph = DependencyGraph()
    graph.add_node(GeometryNode(id="a"))
    results = graph.rebuild_all()
    assert results == {}


# ── 6. Graph stats ─────────────────────────────────────────────────────────


def test_graph_stats():
    """stats() returns total_nodes, dirty_nodes, edges."""
    graph = DependencyGraph()
    for nid in ["a", "b", "c"]:
        graph.add_node(GeometryNode(id=nid))
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")

    stats = graph.stats()
    assert stats["total_nodes"] == 3
    assert stats["edges"] == 2
    assert stats["dirty_nodes"] == 0

    graph.invalidate("a")
    stats = graph.stats()
    assert stats["dirty_nodes"] == 3


# ── 7. get_dirty_nodes ─────────────────────────────────────────────────────


def test_get_dirty_nodes():
    """get_dirty_nodes() returns only dirty nodes."""
    graph = DependencyGraph()
    for nid in ["a", "b", "c"]:
        graph.add_node(GeometryNode(id=nid))

    assert graph.get_dirty_nodes() == []

    graph.invalidate("a")
    dirty = graph.get_dirty_nodes()
    assert "a" in dirty


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p06"] = {
        "graph_class": "DependencyGraph",
        "node_class": "GeometryNode",
        "node_state_enum": ["CLEAN", "DIRTY", "BUILDING", "ERROR"],
        "features": [
            "add_node", "add_edge", "remove_node",
            "invalidate", "get_dirty_nodes", "topological_order",
            "rebuild_all", "stats",
        ],
        "cycle_detection": True,
        "description": "Dependency graph — DAG wiring, topological order, cycle detection",
    }
