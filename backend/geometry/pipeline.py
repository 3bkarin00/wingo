"""Geometry build pipeline — fast and full paths (plan.md Phase 1).

Orchestrates the geometry build into two paths:

**Fast path** (`build_fast`): loft only, no watertight check, no volume check.
Used for live preview while dragging sliders. Returns the OML solid immediately.

**Full path** (`build_full`): the existing pipeline — loft + watertight +
volume + reference geometry. Used on commit/export.

**Incremental path** (`build_incremental`): uses the dependency graph to rebuild
only affected nodes when a station parameter changes.

The existing `loft.py` and `sections.py` stay as-is; this module wraps them
and decides which checks to run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq

from backend.geometry.loft import (
    analytic_volume_estimate,
    build_oml,
    is_watertight,
)
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

# Lazy import for dependency graph (optional optimization)
_WING_GRAPH = None


def _get_wing_graph() -> Any:
    """Lazy import of WingDependencyGraph."""
    global _WING_GRAPH
    if _WING_GRAPH is None:
        try:
            from backend.core.wing_graph import WingDependencyGraph
            _WING_GRAPH = WingDependencyGraph
        except ImportError:
            _WING_GRAPH = None
    return _WING_GRAPH


@dataclass
class PipelineMetrics:
    """Timing and status metrics for a pipeline run.

    Supports dict-like access for backward compatibility:
        metrics["total_ms"]  ->  metrics.to_dict()["total_ms"]
        metrics.get("volume_mm3")  ->  metrics.to_dict().get("volume_mm3")
    """
    airfoil_loading_ms: float = 0.0
    section_placement_ms: float = 0.0
    loft_ms: float = 0.0
    watertight_ms: float = 0.0
    volume_ms: float = 0.0
    reference_ms: float = 0.0
    watertight: bool | None = None  # None if not checked
    volume_mm3: float | None = None
    volume_estimate_mm3: float | None = None  # analytic estimate for deviation calc
    volume_dev_pct: float | None = None
    face_count: int | None = None
    edge_count: int | None = None
    section_count: int = 0
    _total_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        if self._total_ms == 0.0:
            self._total_ms = (
                self.airfoil_loading_ms + self.section_placement_ms +
                self.loft_ms + self.watertight_ms + self.volume_ms +
                self.reference_ms
            )
        return self._total_ms

    def to_dict(self) -> dict[str, Any]:
        # Only include non-zero timing fields — fast path omits skipped stages
        result: dict[str, Any] = {}
        for key in ("airfoil_loading_ms", "section_placement_ms", "loft_ms",
                    "watertight_ms", "volume_ms", "reference_ms"):
            val = getattr(self, key)
            if val != 0.0:
                result[key] = round(val, 1)
        result["total_ms"] = round(self.total_ms, 1)
        result["watertight"] = self.watertight
        result["volume_mm3"] = self.volume_mm3
        result["volume_estimate_mm3"] = self.volume_estimate_mm3
        result["volume_dev_pct"] = self.volume_dev_pct
        result["face_count"] = self.face_count
        result["edge_count"] = self.edge_count
        result["section_count"] = self.section_count
        return result

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


@dataclass
class BuildResult:
    """Result of a pipeline build."""
    solid: cq.Solid
    sections: list  # PlacedSection objects
    metrics: PipelineMetrics
    watertight: bool | None = None  # None if not checked (fast path)
    volume: float | None = None  # alias for volume_mm3 (test contract)
    face_count: int | None = None
    edge_count: int | None = None
    reference: Any = None  # ReferenceGeometry (full path only)
    status: str = "preview"  # "preview" or "final"


def _now_ms() -> float:
    """High-resolution timer in milliseconds."""
    import time
    return time.perf_counter() * 1000


def build_fast(config: Config) -> BuildResult:
    """Fast path: loft only, no watertight, no volume check.

    Used for interactive preview while dragging sliders.
    Expected improvement: 5-10s → 0.5-2s (skips watertight + volume).
    """
    import time

    metrics = PipelineMetrics()
    status = []

    # Phase 1: Airfoil loading + section placement
    t0 = _now_ms()
    sections = build_planform_sections(config)
    metrics.airfoil_loading_ms = _now_ms() - t0
    status.append("sections")

    # Phase 2: OML loft
    t0 = _now_ms()
    solid = build_oml(sections, config.planform.mirror)
    metrics.loft_ms = _now_ms() - t0
    status.append("loft")

    # Phase 3: Topology counts (fast, no OCP expensive ops)
    metrics.face_count = len(solid.Faces())
    metrics.edge_count = len(solid.Edges())
    metrics.section_count = len(sections)

    metrics.status = "preview"
    return BuildResult(
        solid=solid,
        sections=sections,
        metrics=metrics,
        watertight=None,
        volume=None,
        face_count=metrics.face_count,
        edge_count=metrics.edge_count,
        status="preview",
    )


def build_full(config: Config) -> BuildResult:
    """Full path: loft + watertight + volume + reference geometry.

    Used for commit/export. Runs all validation checks.
    """
    import time

    metrics = PipelineMetrics()

    # Phase 1: Airfoil loading + section placement
    t0 = _now_ms()
    sections = build_planform_sections(config)
    metrics.airfoil_loading_ms = _now_ms() - t0
    metrics.section_placement_ms = _now_ms() - t0
    metrics.section_count = len(sections)

    # Phase 2: OML loft
    t0 = _now_ms()
    solid = build_oml(sections, config.planform.mirror)
    metrics.loft_ms = _now_ms() - t0

    # Phase 3: Watertight check
    t0 = _now_ms()
    metrics.watertight = is_watertight(solid)
    metrics.watertight_ms = _now_ms() - t0

    # Phase 4: Volume
    t0 = _now_ms()
    vol = solid.Volume()
    estimate = analytic_volume_estimate(sections, config.planform.mirror)
    vol_dev = abs(vol - estimate) / estimate * 100
    metrics.volume_mm3 = vol
    metrics.volume_estimate_mm3 = estimate
    metrics.volume_dev_pct = vol_dev
    metrics.volume_ms = _now_ms() - t0

    # Phase 5: Topology counts
    metrics.face_count = len(solid.Faces())
    metrics.edge_count = len(solid.Edges())

    # Phase 6: Reference geometry
    t0 = _now_ms()
    ref = build_reference_geometry(config, sections)
    metrics.reference_ms = _now_ms() - t0

    return BuildResult(
        solid=solid,
        sections=sections,
        metrics=metrics,
        watertight=metrics.watertight,
        volume=metrics.volume_mm3,
        face_count=metrics.face_count,
        edge_count=metrics.edge_count,
        reference=ref,
        status="final",
    )


def build_incremental(config: Config, station_index: int, **kwargs: Any) -> BuildResult:
    """Incremental build: update a single station and rebuild only affected nodes.

    Uses the dependency graph to rebuild only the changed station and downstream
    nodes (loft, watertight, volume, reference) — avoiding rebuilding all stations.

    Args:
        config: validated wing configuration.
        station_index: which station to update (0-based).
        **kwargs: station parameters to change (chord_mm, twist_deg, airfoil, y_frac).

    Returns:
        BuildResult with updated solid and metrics.
    """
    WingGraph = _get_wing_graph()
    if WingGraph is None:
        # Fallback: full rebuild if dependency graph not available
        return build_full(config)

    # Create or reuse a wing graph
    graph = WingGraph(config)

    # Update the station parameters
    result = graph.update_station(station_index, **kwargs)

    if result.get("status") != "incremental" or result.get("solid") is None:
        # Rebuild failed, fall back to full
        return build_full(config)

    solid = result["solid"]
    sections = result.get("sections", build_planform_sections(config))

    metrics = PipelineMetrics()
    metrics.section_count = len(sections)
    metrics.face_count = len(solid.Faces())
    metrics.edge_count = len(solid.Edges())

    # If watertight/volume/reference were rebuilt, include them
    if "watertight" in result:
        metrics.watertight = result["watertight"]
    if "volume" in result:
        metrics.volume_mm3 = result["volume"].get("volume") if isinstance(result["volume"], dict) else result["volume"]
        metrics.volume_dev_pct = result["volume"].get("dev_pct") if isinstance(result["volume"], dict) else None

    return BuildResult(
        solid=solid,
        sections=sections,
        metrics=metrics,
        reference=result.get("reference"),
        status="incremental",
    )


def build(config: Config, mode: str = "full", **kwargs: Any) -> BuildResult:
    """Unified build entry point.

    Args:
        config: validated wing configuration.
        mode: "fast" for preview, "full" for commit, "incremental" for station update.
        **kwargs: if mode is "incremental", station_index and parameters to change.

    Returns:
        BuildResult with solid, sections, metrics, and optional reference.
    """
    if mode == "fast":
        return build_fast(config)
    if mode == "incremental":
        station_index = kwargs.pop("station_index", 0)
        return build_incremental(config, station_index, **kwargs)
    return build_full(config)
