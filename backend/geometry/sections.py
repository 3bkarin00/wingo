"""Section construction & placement (plan.md §8.2).

Each spanwise section = a canonical unit-chord airfoil, scaled by chord,
twisted about the declared twist axis, and placed in the wing frame (X aft,
Y starboard, Z up; origin at center-section root LE — docs/conventions.md)
with per-segment dihedral and sweep accumulated along the span.

Point order (TE→upper→LE→lower→TE, identical count for every section) is
preserved throughout so the downstream loft stays aligned (r0_findings/p02.md).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from backend.geometry.airfoil_resolver import resolve_airfoil
from backend.schema.models import Config


@dataclass
class PlacedSection:
    y_mm: float
    y_frac: float
    chord_mm: float
    twist_deg: float
    points: np.ndarray  # (N, 3) in the wing frame
    area_coeff: float = 0.0  # K = enclosed area of the unit-chord section


def place_section(
    canonical: np.ndarray,
    chord_mm: float,
    twist_deg: float,
    twist_axis_xc: float,
    y_mm: float,
    le_x_mm: float,
    z_base_mm: float,
) -> np.ndarray:
    """Scale → twist about (twist_axis_xc·chord, chord line) → place at
    (le_x, y, z). Returns (N, 3) points. Twist is a rotation in the X-Z plane
    about the spanwise axis through the twist-axis point (positive = nose up)."""
    x = canonical[:, 0] * chord_mm  # LE at 0, TE at +chord (aft)
    z = canonical[:, 1] * chord_mm  # thickness (up)

    x_pivot = twist_axis_xc * chord_mm
    a = math.radians(twist_deg)
    ca, sa = math.cos(a), math.sin(a)
    dx = x - x_pivot
    x_rot = x_pivot + dx * ca - z * sa
    z_rot = dx * sa + z * ca

    X = le_x_mm + x_rot
    Z = z_base_mm + z_rot
    Y = np.full_like(X, y_mm)
    return np.column_stack([X, Y, Z])


def _segment_bounds(config: Config) -> list[tuple[float, float, float, float]]:
    """(start_frac, end_frac, sweep_le_deg, dihedral_deg) per segment."""
    out = []
    start = 0.0
    for seg in config.planform.segments:
        out.append((start, seg.y_end_frac, seg.sweep_le_deg, seg.dihedral_deg))
        start = seg.y_end_frac
    return out


def _le_and_z_offset(config: Config, y_frac: float, half_span_mm: float) -> tuple[float, float]:
    """Accumulate LE sweep (X) and dihedral (Z) offsets up to y_frac, honoring
    per-segment angles (C0 kinks at segment boundaries)."""
    le_x = 0.0
    z = 0.0
    for start, end, sweep_deg, dihedral_deg in _segment_bounds(config):
        if y_frac <= start:
            break
        span_in_seg_mm = (min(y_frac, end) - start) * half_span_mm
        le_x += span_in_seg_mm * math.tan(math.radians(sweep_deg))
        z += span_in_seg_mm * math.tan(math.radians(dihedral_deg))
    return le_x, z


def _interp_station(config: Config, y_frac: float, resample_points: int, te_frac_at: float):
    """Interpolate chord, twist, and airfoil shape at y_frac between the two
    bracketing stations (all canonical arrays share a point count, so a linear
    blend is a valid airfoil morph)."""
    stations = sorted(config.planform.stations, key=lambda s: s.y_frac)
    lo = stations[0]
    hi = stations[-1]
    for i in range(len(stations) - 1):
        if stations[i].y_frac <= y_frac <= stations[i + 1].y_frac:
            lo, hi = stations[i], stations[i + 1]
            break
    span = hi.y_frac - lo.y_frac
    t = 0.0 if span == 0 else (y_frac - lo.y_frac) / span

    chord = lo.chord_mm + t * (hi.chord_mm - lo.chord_mm)
    twist = lo.twist_deg + t * (hi.twist_deg - lo.twist_deg)
    # te fraction at this section's real chord (blunt-TE minimum, D6/F15).
    te_frac = te_frac_at / chord
    pts_lo = resolve_airfoil(lo.airfoil, resample_points, te_frac)
    if hi.airfoil == lo.airfoil or t == 0.0:
        pts = pts_lo
    elif t == 1.0:
        pts = resolve_airfoil(hi.airfoil, resample_points, te_frac)
    else:
        pts_hi = resolve_airfoil(hi.airfoil, resample_points, te_frac)
        pts = (1 - t) * pts_lo + t * pts_hi
    return chord, twist, pts


def build_planform_sections(
    config: Config,
    resample_points: int = 199,
) -> list[PlacedSection]:
    """Build placed half-span sections at every station and segment boundary
    (boundaries carry the dihedral/sweep kinks). Returns sections sorted by y."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm

    # Section y-fractions: all stations + all interior segment boundaries.
    fracs = {s.y_frac for s in config.planform.stations}
    for start, end, _, _ in _segment_bounds(config):
        fracs.add(start)
        fracs.add(end)
    fracs = sorted(f for f in fracs if 0.0 <= f <= 1.0)

    sections: list[PlacedSection] = []
    for f in fracs:
        chord, twist, pts = _interp_station(config, f, resample_points, te_min_mm)
        le_x, z_base = _le_and_z_offset(config, f, half_span_mm)
        placed = place_section(
            pts, chord, twist, config.planform.twist_axis_xc,
            y_mm=f * half_span_mm, le_x_mm=le_x, z_base_mm=z_base,
        )
        sections.append(
            PlacedSection(
                f * half_span_mm, f, chord, twist, placed, unit_chord_area(pts)
            )
        )
    return sections


def unit_chord_area(canonical: np.ndarray) -> float:
    """Enclosed area of a closed unit-chord airfoil (shoelace) — the section
    area coefficient K, used for the analytic volume estimate in the P2 gate."""
    x = canonical[:, 0]
    y = canonical[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
