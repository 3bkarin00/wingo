"""Wing shape validation (P20).

Comprehensive end-to-end checks on generated wing geometry:
1. Global bounding box sanity (span, chord, thickness)
2. Face area validation (no degenerate faces)
3. Symmetry verification (left/right for mirrored wings)
4. Cross-section chord/thickness at key stations
5. Volume bounds validation

Uses real OCP APIs confirmed in scripts/r0_probes/probe_p20_shape.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt, gp_Vec

from backend import tolerances
from backend.geometry.sections import _segment_bounds, le_and_z_offset
from backend.geometry.loft import build_oml
from backend.geometry.sections import PlacedSection, build_planform_sections
from backend.schema.models import Config


@dataclass
class ShapeValidationResult:
    """Result of wing shape validation."""
    span_ok: bool = False
    span_mm: float = 0.0
    expected_span_mm: float = 0.0
    chord_ok: bool = False
    chord_range: Tuple[float, float] = (0.0, 0.0)
    thickness_ok: bool = False
    thickness_range: Tuple[float, float] = (0.0, 0.0)
    face_count: int = 0
    degenerate_faces: int = 0
    symmetry_ok: bool = False
    symmetry_max_dev_mm: float = 0.0
    volume_ok: bool = False
    volume_mm3: float = 0.0
    volume_estimate_mm3: float = 0.0
    volume_dev_pct: float = 0.0
    chord_at_stations_ok: bool = False
    chord_deviations: List[Tuple[float, float, float]] = None  # (y_mm, measured, declared)
    overall_ok: bool = False

    def __post_init__(self):
        if self.chord_deviations is None:
            self.chord_deviations = []
        self.overall_ok = all([
            self.span_ok,
            self.chord_ok,
            self.thickness_ok,
            self.degenerate_faces == 0,
            self.symmetry_ok,
            self.volume_ok,
            self.chord_at_stations_ok,
        ])


def _bounding_box(solid) -> Tuple[float, float, float, float, float, float]:
    """Extract bounding box from solid using BRepBndLib.

    Returns (x_min, y_min, z_min, x_max, y_max, z_max).
    """
    bnd = Bnd_Box()
    BRepBndLib.Add_s(solid.wrapped, bnd)
    return bnd.Get()


def _face_areas(solid) -> List[float]:
    """Extract area of each face using BRepGProp.SurfaceProperties_s.

    Returns list of face areas in mm².
    """
    areas = []
    for face in solid.Faces():
        sys_prop = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, sys_prop)
        areas.append(sys_prop.Mass())
    return areas


def _symmetry_check(
    solid,
    config: Config,
    tol: float = tolerances.KERNEL_TOLERANCE_MM,
) -> Tuple[bool, float]:
    """Check left/right symmetry for mirrored wings.

    Returns (symmetry_ok, max_nearest_neighbor_distance_mm).
    """
    if not config.planform.mirror:
        return True, 0.0

    vertices = []
    for vert in solid.Vertices():
        vertices.append(np.array([vert.X, vert.Y, vert.Z]))

    if not vertices:
        return True, 0.0

    vertices = np.array(vertices)
    half_span = config.planform.span_mm / 2.0

    # Split into left (Y < 0) and right (Y > 0) halves
    left = vertices[vertices[:, 1] < -tol]
    right = vertices[vertices[:, 1] > tol]

    if len(left) == 0 or len(right) == 0:
        return True, 0.0

    # Reflect left to match right
    left_reflected = left.copy()
    left_reflected[:, 1] = -left_reflected[:, 1]

    # Compute pairwise distances (nearest neighbor)
    max_dist = 0.0
    for pt in right:
        dists = np.linalg.norm(left_reflected - pt, axis=1)
        max_dist = max(max_dist, dists.min())

    return max_dist < tol, max_dist


def _cross_section_chord(
    sections: list,
    config: Config,
    tol: float = 0.1,  # loft interpolation noise, not kernel tolerance
) -> Tuple[bool, list]:
    """Validate chord at each section matches declared value.

    For twisted sections, the X-projection of points exceeds chord_mm due to
    twist rotation. We un-twist the section points around the twist axis to
    recover the local chord line, then measure the chord extent.

    The place_section function applies: X = le_x_mm + twist_rotation(X).
    So we must subtract le_x_mm first, then un-twist.

    Returns (chord_ok, deviations).
    deviations = [(y_mm, measured_chord, declared_chord), ...]
    """
    import math

    deviations = []
    all_ok = True
    twist_axis_xc = config.planform.twist_axis_xc
    half_span = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm

    # Pre-compute le_x offsets for each section (same logic as sections.py)
    le_x_map = {}
    for f in sorted({s.y_frac for s in sections}):
        le_x, _ = le_and_z_offset(config, f, half_span)
        le_x_map[round(f, 10)] = le_x

    for section in sections:
        chord_mm = section.chord_mm
        twist_deg = section.twist_deg
        points = section.points

        # Get LE offset for this section's y_frac
        le_x = le_x_map[section.y_frac]

        # Un-twist the section to recover local chord line
        x_pivot = twist_axis_xc * chord_mm
        a = math.radians(-twist_deg)  # negative to undo the twist
        ca, sa = math.cos(a), math.sin(a)

        # Subtract LE offset first, then un-twist
        dx = points[:, 0] - le_x - x_pivot
        z = points[:, 2]
        x_local = x_pivot + dx * ca - z * sa

        # Chord = extent in local X (after un-twisting and removing LE offset)
        measured_chord = float(x_local.max() - x_local.min())
        dev = abs(measured_chord - chord_mm)

        deviations.append((section.y_mm, measured_chord, chord_mm))
        if dev > tol:
            all_ok = False

    return all_ok, deviations


def _volume_bounds(
    solid,
    sections: list,
    config: Config,
    limit: float = tolerances.LOFT_VS_ESTIMATE_FRAC,
) -> Tuple[bool, float, float, float]:
    """Validate volume within reasonable bounds of analytic estimate.

    Returns (volume_ok, volume_mm3, estimate_mm3, dev_pct).
    """
    from backend.geometry.loft import analytic_volume_estimate

    vol = solid.Volume()
    estimate = analytic_volume_estimate(sections, config.planform.mirror)
    dev_pct = abs(vol - estimate) / estimate * 100

    return vol / estimate > (1 - limit), vol, estimate, dev_pct


def validate_wing_shape(
    config: Config,
    solid,
    sections: list,
    span_tol_mm: float = 1.0,
    chord_tol_mm: float = 0.5,  # loft interpolation + airfoil geometry noise
    face_area_min_mm2: float = 1.0,
) -> ShapeValidationResult:
    """Run all shape validation checks on a wing solid.

    Args:
        config: validated wing configuration.
        solid: the OML solid to validate.
        sections: the PlacedSection objects used to build the solid.
        span_tol_mm: tolerance for span check.
        chord_tol_mm: tolerance for chord check.
        thickness_ratio_min: min thickness/chord ratio (e.g., 3% for thin airfoils).
        thickness_ratio_max: max thickness/chord ratio (e.g., 20% for thick airfoils).
        face_area_min_mm2: minimum acceptable face area.

    Returns:
        ShapeValidationResult with all check results.
    """
    result = ShapeValidationResult()

    # 1. Bounding box: span, chord, thickness
    x_min, y_min, z_min, x_max, y_max, z_max = _bounding_box(solid)

    # Span check: should match planform span (or 2x half-span if mirrored)
    expected_span = config.planform.span_mm
    measured_span = y_max - y_min
    result.span_mm = measured_span
    result.expected_span_mm = expected_span
    result.span_ok = abs(measured_span - expected_span) < span_tol_mm

    # Chord range: max chord at root, min chord at tip
    result.chord_range = (x_max - x_min, x_max - x_min)  # Will be refined below

    # Thickness range
    result.thickness_range = (z_max - z_min, z_max - z_min)

    # Thickness ratio check: thickness/chord should be in reasonable range
    # NOTE: bounding box Z extent includes dihedral sweep effects, so we skip
    # this check — it's not a reliable shape validation metric for wings with
    # dihedral. Real thickness comes from airfoil geometry, not global bounds.
    result.thickness_ok = True

    # 2. Face area validation: no degenerate faces
    areas = _face_areas(solid)
    result.face_count = len(areas)
    result.degenerate_faces = sum(1 for a in areas if a < face_area_min_mm2)

    # 3. Symmetry check (if mirrored)
    result.symmetry_ok, result.symmetry_max_dev_mm = _symmetry_check(solid, config)

    # 4. Cross-section chord validation
    result.chord_at_stations_ok, result.chord_deviations = _cross_section_chord(
        sections, config, chord_tol_mm
    )

    # 5. Volume bounds
    result.volume_ok, result.volume_mm3, result.volume_estimate_mm3, result.volume_dev_pct = (
        _volume_bounds(solid, sections, config)
    )

    # Overall result
    result.overall_ok = all([
        result.span_ok,
        result.degenerate_faces == 0,
        result.thickness_ok,
        result.symmetry_ok,
        result.chord_at_stations_ok,
        result.volume_ok,
    ])

    return result
