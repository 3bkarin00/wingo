"""Geometry node — the basic unit of the dependency graph.

Each node:
- Has a unique id
- Tracks its inputs (other node ids or raw config values)
- Tracks its outputs (computed geometry)
- Can build() its output from inputs
- Can invalidate() when inputs change

Usage:
    wing = WingNode("wing")
    wing.add_input("config_hash", config_hash)
    wing.add_input("airfoil_naca2412", airfoil_node)
    ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class NodeState(Enum):
    """Lifecycle state of a geometry node."""
    CLEAN = "clean"          # output is valid
    DIRTY = "dirty"          # inputs changed, need rebuild
    BUILDING = "building"    # currently being rebuilt (for cycle detection)
    ERROR = "error"          # build failed


@dataclass
class GeometryNode:
    """A single node in the dependency graph.

    Attributes:
        id: unique identifier (e.g. "wing", "station_0", "loft").
        build_fn: callable that computes output from inputs.
        inputs: set of node ids or input keys this node depends on.
        output: the computed result (set after build()).
        state: current lifecycle state.
        error: error message if build failed.
    """
    id: str
    build_fn: Callable[["GeometryNode"], Any] | None = None
    inputs: set[str] = field(default_factory=set)
    output: Any = None
    state: NodeState = NodeState.CLEAN
    error: str | None = None
    _input_values: dict[str, Any] = field(default_factory=dict)

    def add_input(self, key: str, value: Any) -> None:
        """Add a raw input value (not a node dependency)."""
        self.inputs.add(key)
        self._input_values[key] = value
        self._mark_dirty()

    def add_dependency(self, node_id: str) -> None:
        """Declare a dependency on another node."""
        self.inputs.add(node_id)

    def _mark_dirty(self) -> None:
        """Mark this node and all dependents as dirty."""
        if self.state == NodeState.CLEAN:
            self.state = NodeState.DIRTY

    def build(self) -> Any:
        """Execute the build function and return the output.

        Raises:
            RuntimeError: if build_fn is not set or build fails.
        """
        if self.build_fn is None:
            raise RuntimeError(f"No build_fn set for node '{self.id}'")

        self.state = NodeState.BUILDING
        try:
            self.output = self.build_fn()
            self.state = NodeState.CLEAN
            self.error = None
            return self.output
        except Exception as e:
            self.state = NodeState.ERROR
            self.error = str(e)
            raise

    def invalidate(self, changed_inputs: set[str] | None = None) -> list[str]:
        """Invalidate this node and return all downstream nodes that need rebuild.

        Args:
            changed_inputs: specific input keys that changed (if known).

        Returns:
            List of node ids that are now dirty (including this one).
        """
        if changed_inputs is None:
            self._mark_dirty()
        else:
            # Only mark dirty if changed inputs are relevant
            if changed_inputs & self.inputs:
                self._mark_dirty()

        # Propagate to dependents (handled by graph level)
        return [self.id]

    def needs_rebuild(self) -> bool:
        """Check if this node needs rebuilding."""
        return self.state != NodeState.CLEAN

    def __repr__(self) -> str:
        return f"Node({self.id}, state={self.state.value})"
