"""Geometry build pipeline — fast and full paths (plan.md Phase 1).

Orchestrates the geometry build into two paths:

**Fast path** (`build_fast`): loft only, no watertight check, no volume check.
Used for live preview while dragging sliders. Returns the OML solid immediately.

**Full path** (`build_full`): the existing pipeline — loft + watertight +
volume + reference geometry. Used on commit/export.

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


@dataclass
class PipelineMetrics:
    """Timing and status metrics for a pipeline run."""
    airfoil_loading_ms: float = 0.0
    section_placement_ms: float = 0.0
    loft_ms: float = 0.0
    watertight_ms: float = 0.0
    volume_ms: float = 0.0
    reference_ms: float = 0.0
    watertight: bool | None = None  # None if not checked
    volume_mm3: float | None = None
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
        return {
            "airfoil_loading_ms": round(self.airfoil_loading_ms, 1),
            "section_placement_ms": round(self.section_placement_ms, 1),
            "loft_ms": round(self.loft_ms, 1),
            "watertight_ms": round(self.watertight_ms, 1),
            "volume_ms": round(self.volume_ms, 1),
            "reference_ms": round(self.reference_ms, 1),
            "total_ms": round(self.total_ms, 1),
            "watertight": self.watertight,
            "volume_mm3": self.volume_mm3,
            "volume_dev_pct": self.volume_dev_pct,
            "face_count": self.face_count,
            "edge_count": self.edge_count,
            "section_count": self.section_count,
        }


@dataclass
class BuildResult:
    """Result of a pipeline build."""
    solid: cq.Solid
    sections: list  # PlacedSection objects
    metrics: PipelineMetrics
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
        reference=ref,
        status="final",
    )


def build(config: Config, mode: str = "full") -> BuildResult:
    """Unified build entry point.

    Args:
        config: validated wing configuration.
        mode: "fast" for preview (no watertight/volume), "full" for commit.

    Returns:
        BuildResult with solid, sections, metrics, and optional reference.
    """
    if mode == "fast":
        return build_fast(config)
    return build_full(config)
