"""Multi-resolution geometry — different quality levels for preview vs export.

Three quality levels:
- LOW (preview): 51-point airfoils, 10 stations, simple tessellation
- MEDIUM (interactive): 127-point airfoils, all stations, moderate tessellation
- HIGH (export): 199-point airfoils, all stations, accurate tessellation

The speedup comes from using fewer points in the loft:
- 51-point airfoil vs 199-point: 74% fewer vertices per station
- Loft scales O(N*M) where N=stations, M=points per station
- 51/199 = 26% of the work for the loft

Usage:
    from backend.geometry.multires import build_at_quality

    # Fast preview
    result = build_at_quality(config, quality="low")

    # High-quality export
    result = build_at_quality(config, quality="high")
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq
import numpy as np

from backend.geometry.loft import (
    build_oml,
    build_oml_smooth,
    build_wing_assembly,
    is_watertight,
    analytic_volume_estimate,
)
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

# Resolution presets: (airfoil_points, tessellation_tolerance_mm)
QUALITY_PRESETS = {
    "low": (51, 0.5),    # Preview: fast, ~26% of high-res work
    "medium": (127, 0.1),  # Interactive: balanced
    "high": (199, 0.05),   # Export: full quality
}


@dataclass
class MultiResResult:
    """Result of a multi-resolution geometry build."""
    solid: cq.Solid
    quality: str
    airfoil_points: int
    metrics: dict
    watertight: bool | None = None
    volume: float | None = None
    face_count: int | None = None
    edge_count: int | None = None
    pieces: dict[str, cq.Solid] | None = None  # 4-piece assembly


def build_at_quality(
    config: Config,
    quality: str = "high",
    resample_override: int | None = None,
) -> MultiResResult:
    """Build geometry at a specific quality level.

    Args:
        config: validated wing configuration.
        quality: "low", "medium", or "high".
        resample_override: force specific airfoil point count.

    Returns:
        MultiResResult with solid, quality level, and metrics.
    """
    import time

    if quality not in QUALITY_PRESETS:
        raise ValueError(f"Unknown quality: {quality}. Use {list(QUALITY_PRESETS.keys())}")

    preset = QUALITY_PRESETS[quality]
    resample_points = resample_override or preset[0]

    metrics = {}

    # Build sections at this resolution
    t0 = time.perf_counter()
    sections = build_planform_sections(config, resample_points=resample_points)
    metrics["sections_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # Build ruled polygon loft (fast, robust — used by all gates)
    t0 = time.perf_counter()
    solid = build_oml(sections, config.planform.mirror)
    metrics["loft_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # Watertight check (full path only)
    watertight = None
    volume = None
    if quality == "high":
        t0 = time.perf_counter()
        watertight = is_watertight(solid)
        metrics["watertight_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        t0 = time.perf_counter()
        vol = solid.Volume()
        estimate = analytic_volume_estimate(sections, config.planform.mirror)
        metrics["volume_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        metrics["volume_mm3"] = round(vol, 1)
        volume = vol

    metrics["quality"] = quality
    metrics["airfoil_points"] = resample_points
    metrics["station_count"] = len(sections)
    metrics["face_count"] = len(solid.Faces())
    metrics["edge_count"] = len(solid.Edges())
    metrics["total_ms"] = round(sum(v for k, v in metrics.items() if k.endswith("_ms")), 1)

    # Build 4-piece assembly (production quality, always built)
    pieces = None
    if quality == "high":
        t0 = time.perf_counter()
        pieces = build_wing_assembly(sections, config.planform.mirror)
        metrics["assembly_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    return MultiResResult(
        solid=solid,
        quality=quality,
        airfoil_points=resample_points,
        metrics=metrics,
        watertight=watertight,
        volume=volume,
        pieces=pieces,
    )


def build_preview(config: Config) -> MultiResResult:
    """Build low-resolution preview for interactive editing."""
    return build_at_quality(config, quality="low")


def build_export(config: Config) -> MultiResResult:
    """Build high-resolution geometry for export."""
    return build_at_quality(config, quality="high")
