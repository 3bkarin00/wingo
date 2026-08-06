"""Wing dependency graph — wires geometry nodes together for incremental rebuild.

Builds a DAG where:
- config_hash → station nodes (each station depends on airfoil + config params)
- station nodes → loft node
- loft node → watertight/volume/reference nodes

When a station parameter changes (e.g. chord_mm), only that station and
downstream nodes (loft, watertight) are rebuilt — root airfoil, other
stations, and unrelated geometry are untouched.

Usage:
    graph = WingDependencyGraph(config)
    result = graph.build_full()  # full rebuild
    result = graph.build_fast()  # preview (skip watertight)

    # Incremental: change one station parameter
    graph.nodes["station_5"].add_input("chord_mm", new_chord)
    dirty = graph.invalidate("station_5")
    rebuilt = graph.rebuild_all()
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import cadquery as cq
import numpy as np

from backend.core.dependency import DependencyGraph
from backend.core.node import GeometryNode, NodeState
from backend.geometry.airfoil_resolver import resolve_airfoil
from backend.geometry.cache import cache
from backend.geometry.loft import build_oml, is_watertight, analytic_volume_estimate
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import (
    PlacedSection,
    build_planform_sections,
    interp_station,
    le_and_z_offset,
    place_section,
    unit_chord_area,
)
from backend.schema.models import Config


class WingDependencyGraph:
    """Dependency graph for a wing geometry build.

    Nodes:
        config_hash: raw config hash (root)
        airfoil_<name>: resolved airfoil points
        station_<i>: placed section at station i
        loft: OML solid
        watertight: bool
        volume: float
        reference: ReferenceGeometry

    When a station parameter changes, only that station and downstream
    nodes are rebuilt.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.graph = DependencyGraph()
        self._config_hash = self._compute_config_hash(config)
        self._build_nodes()

    def _compute_config_hash(self, config: Config) -> str:
        """Compute a hash of the config for cache invalidation."""
        config_dict = json.loads(config.model_dump_json())
        return hashlib.sha256(json.dumps(config_dict, sort_keys=True).encode()).hexdigest()[:16]

    def _build_nodes(self) -> None:
        """Build all geometry nodes and wire up dependencies."""
        # Root: config hash
        config_node = GeometryNode(id="config_hash", build_fn=lambda self: self._config_hash)
        self.graph.add_node(config_node)

        # Airfoil nodes: one per unique airfoil name in stations
        unique_airfoils = sorted({s.airfoil for s in self.config.planform.stations})
        for airfoil_name in unique_airfoils:
            af_id = f"airfoil_{airfoil_name}"
            af_node = GeometryNode(
                id=af_id,
                build_fn=lambda self, name=airfoil_name: self._build_airfoil(name),
            )
            af_node.add_input("resample_points", self.config.airfoils.resample_points)
            af_node.add_input("te_thickness_frac", self.config.airfoils.te_min_thickness_mm)
            self.graph.add_node(af_node)
            self.graph.add_edge("config_hash", af_id)

        # Station nodes: one per station
        for i, station in enumerate(self.config.planform.stations):
            station_id = f"station_{i}"
            station_node = GeometryNode(
                id=station_id,
                build_fn=lambda self, idx=i: self._build_station(idx),
            )
            # Each station depends on its airfoil
            af_id = f"airfoil_{station.airfoil}"
            station_node.add_dependency(af_id)
            # Also depends on config params
            station_node.add_input("y_frac", station.y_frac)
            station_node.add_input("chord_mm", station.chord_mm)
            station_node.add_input("twist_deg", station.twist_deg)
            station_node.add_input("mirror", self.config.planform.mirror)
            self.graph.add_node(station_node)
            self.graph.add_edge(af_id, station_id)

        # Loft node: depends on all stations
        loft_node = GeometryNode(
            id="loft",
            build_fn=lambda self: self._build_loft(),
        )
        for i in range(len(self.config.planform.stations)):
            loft_node.add_dependency(f"station_{i}")
        self.graph.add_node(loft_node)
        self.graph.add_edge("config_hash", "loft")

        # Watertight node: depends on loft
        watertight_node = GeometryNode(
            id="watertight",
            build_fn=lambda self: self._build_watertight(),
        )
        watertight_node.add_dependency("loft")
        self.graph.add_node(watertight_node)

        # Volume node: depends on loft
        volume_node = GeometryNode(
            id="volume",
            build_fn=lambda self: self._build_volume(),
        )
        volume_node.add_dependency("loft")
        self.graph.add_node(volume_node)

        # Reference node: depends on config and stations
        ref_node = GeometryNode(
            id="reference",
            build_fn=lambda self: self._build_reference(),
        )
        ref_node.add_dependency("config_hash")
        for i in range(len(self.config.planform.stations)):
            ref_node.add_dependency(f"station_{i}")
        self.graph.add_node(ref_node)

    def _build_airfoil(self, name: str) -> np.ndarray:
        """Build a resolved airfoil from cache or compute."""
        return resolve_airfoil(
            name,
            self.config.airfoils.resample_points,
            self.config.airfoils.te_min_thickness_mm / (self.config.planform.stations[0].chord_mm if self.config.planform.stations else 300.0),
        )

    def _build_station(self, index: int) -> PlacedSection:
        """Build a single placed section from its station config."""
        station = self.config.planform.stations[index]
        half_span = self.config.planform.span_mm / 2.0 if self.config.planform.mirror else self.config.planform.span_mm
        te_min_mm = self.config.airfoils.te_min_thickness_mm

        chord, twist, pts = interp_station(
            self.config, station.y_frac,
            self.config.airfoils.resample_points, te_min_mm
        )
        le_x, z_base = le_and_z_offset(
            self.config, station.y_frac, half_span
        )
        placed = place_section(
            pts, chord, twist, self.config.planform.twist_axis_xc,
            y_mm=station.y_frac * half_span, le_x_mm=le_x, z_base_mm=z_base,
        )
        return PlacedSection(
            station.y_frac * half_span,
            station.y_frac,
            chord,
            twist,
            placed,
            unit_chord_area(pts),
        )

    def _build_loft(self) -> cq.Solid:
        """Build the OML loft from all station nodes."""
        sections = []
        for i in range(len(self.config.planform.stations)):
            node = self.graph.nodes[f"station_{i}"]
            if node.output is None:
                raise RuntimeError(f"Station {i} not built")
            sections.append(node.output)
        return build_oml(sections, self.config.planform.mirror)

    def _build_watertight(self) -> bool:
        """Check watertightness of the loft."""
        loft_node = self.graph.nodes["loft"]
        return is_watertight(loft_node.output)

    def _build_volume(self) -> dict[str, float]:
        """Compute volume and analytic estimate."""
        loft_node = self.graph.nodes["loft"]
        sections = []
        for i in range(len(self.config.planform.stations)):
            sections.append(self.graph.nodes[f"station_{i}"].output)
        vol = loft_node.output.Volume()
        estimate = analytic_volume_estimate(sections, self.config.planform.mirror)
        dev = abs(vol - estimate) / estimate * 100
        return {"volume": vol, "estimate": estimate, "dev_pct": dev}

    def _build_reference(self) -> Any:
        """Build reference geometry."""
        sections = []
        for i in range(len(self.config.planform.stations)):
            sections.append(self.graph.nodes[f"station_{i}"].output)
        return build_reference_geometry(self.config, sections)

    def build_fast(self) -> dict[str, Any]:
        """Fast path: build up to loft (no watertight, no volume, no reference)."""
        # Invalidate everything
        self.graph.invalidate("config_hash")
        dirty = self.graph.get_dirty_nodes()
        order = self.graph.topological_order(dirty)

        results = {}
        for node_id in order:
            node = self.graph.nodes[node_id]
            if node.needs_rebuild():
                node.build()
                results[node_id] = node.output

        return {
            "solid": results.get("loft"),
            "sections": [self.graph.nodes[f"station_{i}"].output
                        for i in range(len(self.config.planform.stations))],
            "status": "preview",
        }

    def build_full(self) -> dict[str, Any]:
        """Full path: build everything including watertight/volume/reference."""
        # Invalidate everything
        self.graph.invalidate("config_hash")
        dirty = self.graph.get_dirty_nodes()
        order = self.graph.topological_order(dirty)

        results = {}
        for node_id in order:
            node = self.graph.nodes[node_id]
            if node.needs_rebuild():
                node.build()
                results[node_id] = node.output

        return {
            "solid": results.get("loft"),
            "sections": [self.graph.nodes[f"station_{i}"].output
                        for i in range(len(self.config.planform.stations))],
            "watertight": results.get("watertight"),
            "volume": results.get("volume"),
            "reference": results.get("reference"),
            "status": "final",
        }

    def update_station(self, station_index: int, **kwargs: Any) -> dict[str, Any]:
        """Update a single station parameter and rebuild only affected nodes.

        Args:
            station_index: which station to update.
            **kwargs: parameters to change (chord_mm, twist_deg, y_frac, etc.)

        Returns:
            Rebuilt geometry (loft + downstream).
        """
        station_id = f"station_{station_index}"
        if station_id not in self.graph.nodes:
            raise ValueError(f"Station {station_index} not found")

        station = self.config.planform.stations[station_index]
        for key, value in kwargs.items():
            setattr(station, key, value)

        # Invalidate this station and downstream
        dirty = self.graph.invalidate(station_id)
        order = self.graph.topological_order(dirty)

        results = {}
        for node_id in order:
            node = self.graph.nodes[node_id]
            if node.needs_rebuild():
                node.build()
                results[node_id] = node.output

        return {
            "solid": results.get("loft"),
            "dirty_nodes": dirty,
            "rebuilt": list(results.keys()),
            "status": "incremental",
        }

    def stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        return {
            "graph": self.graph.stats(),
            "nodes": {nid: str(node) for nid, node in self.graph.nodes.items()},
        }
