"""Reference geometry (plan.md §8.4).

Builds spar ruled surfaces, rib planes (auto + forced), hinge axes, and
hardpoint locations before any boolean cuts are made.

Hinge axis height is DERIVED, not read straight off the camber line
(ADR-003): hinge_xc still fixes the chordwise (X) position, but the
vertical (Z) position is fit by least squares to the TRUE equidistant-
from-skin height sampled at many stations, replacing the old 2-point
camber-line-ARITHMETIC-MEAN placement. Those are NOT the same point in
general — the midpoint of zu(xc)/zl(xc) only coincides with the point
equidistant from the upper/lower skin CURVES when the skin is locally flat
there; for real cambered/curved skin (and worse, under spanwise twist,
which rotates the whole section including that mismatch) they diverge,
which is exactly the source of the per-station Ru != Rl asymmetry that
used to fire the two-arc CS-nose construction branch (see cove_profile.py,
docs/decisions/ADR-003).
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq
import numpy as np

from backend.geometry.sections import PlacedSection, interp_station, place_section, le_and_z_offset
from backend.schema.models import Config
from backend.airfoils.resample import split_surfaces, interp_surface

# Sample density for the least-squares hinge-axis-height fit — an algorithmic
# parameter (not a physical tolerance, so it lives here rather than
# tolerances.py, matching te_cut.py's own N_STATIONS pattern). The fit is
# pure numpy (a bisection + polyfit per station), no OCC boolean, so a
# density matching N_STATIONS costs milliseconds.
AXIS_HEIGHT_FIT_STATIONS = 24


@dataclass
class ReferenceGeometry:
    spar_surfaces: dict[str, cq.Shell]
    rib_planes: list[cq.Plane]
    hinge_axes: dict[str, cq.Edge]  # straight lines
    hardpoints: list[cq.Vector]


def _get_canonical_points_at_xc(pts: np.ndarray, xc: float) -> tuple[float, float, float]:
    """Return (upper_z, lower_z, camber_z) at chord fraction xc."""
    upper, lower = split_surfaces(pts)
    zu = float(interp_surface(np.array([xc]), upper)[0])
    zl = float(interp_surface(np.array([xc]), lower)[0])
    return zu, zl, (zu + zl) / 2.0


def _nearest_dist_to_polyline(point: np.ndarray, polyline: np.ndarray) -> float:
    """Min distance from a 2D point to a 2D polyline, via vectorized
    point-to-segment distance over every segment (exact for the piecewise-
    linear canonical airfoil curves this module already works in)."""
    a, b = polyline[:-1], polyline[1:]
    ab = b - a
    ab_len2 = np.sum(ab * ab, axis=1)
    ab_len2 = np.where(ab_len2 < 1e-12, 1e-12, ab_len2)
    t = np.clip(np.sum((point - a) * ab, axis=1) / ab_len2, 0.0, 1.0)
    proj = a + t[:, None] * ab
    return float(np.min(np.linalg.norm(point - proj, axis=1)))


def _equidistant_z_canonical(pts: np.ndarray, xc: float) -> float:
    """The z (canonical unit-chord space) on the vertical line x=xc where
    distance to the upper surface equals distance to the lower surface —
    the TRUE geometric equidistant point (see module docstring for why this
    differs from the arithmetic mean of zu(xc)/zl(xc)).

    Bisection: f(z) = dist_to_upper(z) - dist_to_lower(z) is negative near
    the upper surface (z=zu) and positive near the lower (z=zl); monotonic
    for a well-behaved single-valued airfoil surface (every vendored/
    generated airfoil in this project). 60 iterations gives 2^-60 resolution
    on the bracket, far below kernel tolerance."""
    upper, lower = split_surfaces(pts)
    zu = float(interp_surface(np.array([xc]), upper)[0])
    zl = float(interp_surface(np.array([xc]), lower)[0])

    def f(z: float) -> float:
        p = np.array([xc, z])
        return _nearest_dist_to_polyline(p, upper) - _nearest_dist_to_polyline(p, lower)

    lo, hi = zl, zu
    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        # Bracket failed (degenerate/near-zero-thickness section) — fall
        # back to the arithmetic mean; the downstream least-squares-residual
        # / tangency-error validation (te_cut.py) still catches a station
        # that's genuinely bad, rather than this helper raising blind.
        return (zu + zl) / 2.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        f_mid = f(mid)
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def derive_hinge_axis(
    config: Config, span_start_frac: float, span_end_frac: float, xc_start: float, xc_end: float,
) -> tuple[cq.Vector, cq.Vector, np.ndarray]:
    """Derived-axis-height hinge line (ADR-003). hinge_xc stays the user
    parameter — X position is deterministic, linear in y_frac, exactly as
    before. The Z position is DERIVED: sample the true equidistant height
    (_equidistant_z_canonical) at AXIS_HEIGHT_FIT_STATIONS stations across
    the span, then fit a straight line (least squares) through them — a
    straight line is required by convention (docs/conventions.md §5), and
    the true equidistant height is not itself a straight line in general
    (camber/twist/taper all vary it nonlinearly with span), so a least-
    squares fit is the closest straight-line approximation, not a re-
    derivation of the exact curve.

    Returns (p1, p2, residuals_mm): the fitted axis endpoints at
    span_start_frac/span_end_frac, and the per-sample-station |true_z -
    fitted_z| residuals (for logging + the tangency-error validation this
    feeds in te_cut.py — never hidden, per ADR-003)."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm

    y_fracs = np.linspace(span_start_frac, span_end_frac, AXIS_HEIGHT_FIT_STATIONS)
    y_mm = y_fracs * half_span_mm
    span = span_end_frac - span_start_frac
    xcs = xc_start + (y_fracs - span_start_frac) / span * (xc_end - xc_start) if span > 0 else np.full_like(y_fracs, xc_start)

    x_world = np.empty(AXIS_HEIGHT_FIT_STATIONS)
    z_true = np.empty(AXIS_HEIGHT_FIT_STATIONS)
    for i in range(AXIS_HEIGHT_FIT_STATIONS):
        chord, twist, pts = interp_station(config, float(y_fracs[i]), config.airfoils.resample_points, te_min_mm)
        z_canonical = _equidistant_z_canonical(pts, float(xcs[i]))
        le_x, z_base = le_and_z_offset(config, float(y_fracs[i]), half_span_mm)
        placed = place_section(
            np.array([[xcs[i], z_canonical]]), chord, twist, config.planform.twist_axis_xc,
            y_mm=y_mm[i], le_x_mm=le_x, z_base_mm=z_base,
        )
        x_world[i] = placed[0][0]
        z_true[i] = placed[0][2]

    z_m, z_b = np.polyfit(y_mm, z_true, deg=1)
    z_fit = z_m * y_mm + z_b
    residuals_mm = np.abs(z_true - z_fit)

    # X is already exactly linear in y_frac for a single-segment span (see
    # module docstring); fit anyway so float noise can't produce a non-
    # straight axis, using the same least-squares machinery as Z.
    x_m, x_b = np.polyfit(y_mm, x_world, deg=1)
    p1 = cq.Vector(x_m * y_mm[0] + x_b, y_mm[0], z_m * y_mm[0] + z_b)
    p2 = cq.Vector(x_m * y_mm[-1] + x_b, y_mm[-1], z_m * y_mm[-1] + z_b)
    return p1, p2, residuals_mm


def build_spar_surfaces(config: Config, sections: list[PlacedSection]) -> dict[str, cq.Shell]:
    """Build a ruled surface shell for each spar from root to tip."""
    spars = {}
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm

    for spar in config.spars:
        faces = []
        prev_edge = None
        for sec in sections:
            xc = spar.xc_root + sec.y_frac * (spar.xc_tip - spar.xc_root)
            chord, twist, pts = interp_station(config, sec.y_frac, config.airfoils.resample_points, te_min_mm)
            zu, zl, _ = _get_canonical_points_at_xc(pts, xc)
            
            canonical_pts = np.array([[xc, zl], [xc, zu]])
            le_x, z_base = le_and_z_offset(config, sec.y_frac, half_span_mm)
            placed = place_section(
                canonical_pts, chord, twist, config.planform.twist_axis_xc,
                y_mm=sec.y_mm, le_x_mm=le_x, z_base_mm=z_base
            )
            
            p1 = cq.Vector(*placed[0])
            p2 = cq.Vector(*placed[1])
            edge = cq.Edge.makeLine(p1, p2)
            
            if prev_edge is not None:
                faces.append(cq.Face.makeRuledSurface(prev_edge, edge))
            prev_edge = edge
            
        spars[spar.name] = cq.Shell.makeShell(faces)
    return spars


def build_rib_planes(config: Config) -> list[cq.Plane]:
    """Rib planes (auto + forced at device edges and break stations)."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    
    forced_fracs = {0.0, 1.0}
    for seg in config.planform.segments:
        forced_fracs.add(seg.y_end_frac)
        
    if config.te_surface and config.te_surface.enabled:
        forced_fracs.add(config.te_surface.span_start_frac)
        forced_fracs.add(config.te_surface.span_end_frac)
        
    if config.le_droop and config.le_droop.enabled:
        forced_fracs.add(config.le_droop.span_start_frac)
        forced_fracs.add(config.le_droop.span_end_frac)
        
    forced_fracs = sorted(list(forced_fracs))
    remaining = config.ribs.count - len(forced_fracs)
    if remaining < 0:
        raise ValueError(
            f"ribs.count={config.ribs.count} is fewer than the "
            f"{len(forced_fracs)} forced rib planes required at segment "
            f"boundaries and device edges {forced_fracs}"
        )

    if remaining > 0:
        gaps = np.diff(forced_fracs)
        alloc = np.round(remaining * gaps / sum(gaps)).astype(int)
        while sum(alloc) < remaining:
            alloc[np.argmax(gaps - alloc * sum(gaps)/remaining)] += 1
        while sum(alloc) > remaining:
            alloc[np.argmax(alloc)] -= 1
            
        all_fracs = []
        for i in range(len(forced_fracs) - 1):
            all_fracs.append(forced_fracs[i])
            if alloc[i] > 0:
                step = (forced_fracs[i+1] - forced_fracs[i]) / (alloc[i] + 1)
                for j in range(1, alloc[i] + 1):
                    all_fracs.append(forced_fracs[i] + j * step)
        all_fracs.append(forced_fracs[-1])
    else:
        all_fracs = forced_fracs
        
    planes = []
    for f in all_fracs:
        y = f * half_span_mm
        planes.append(cq.Plane(origin=(0, y, 0), xDir=(1, 0, 0), normal=(0, 1, 0)))
    return planes


def build_hinge_axes(config: Config) -> dict[str, cq.Edge]:
    """TE/LE hinge axes (straight, containment-sampled, DERIVED height —
    see derive_hinge_axis / module docstring / ADR-003). Discards the
    per-station residuals this convenience wrapper doesn't need; callers
    that need them (the P4 axis-fit validation) call derive_hinge_axis
    directly (backend/geometry/te_cut.py)."""
    axes = {}
    if config.te_surface and config.te_surface.enabled:
        p1, p2, _ = derive_hinge_axis(
            config, config.te_surface.span_start_frac, config.te_surface.span_end_frac,
            config.te_surface.hinge_xc_start, config.te_surface.hinge_xc_end,
        )
        axes["te"] = cq.Edge.makeLine(p1, p2)

    if config.le_droop and config.le_droop.enabled:
        p1, p2, _ = derive_hinge_axis(
            config, config.le_droop.span_start_frac, config.le_droop.span_end_frac,
            config.le_droop.hinge_xc_start, config.le_droop.hinge_xc_end,
        )
        axes["le"] = cq.Edge.makeLine(p1, p2)

    return axes


def build_hardpoints(config: Config) -> list[cq.Vector]:
    """Fuselage attachment hardpoints."""
    pts = []
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm
    
    for bolt in config.hardpoints.fuselage_attachment.bolts:
        y_frac = bolt.y_mm / half_span_mm
        chord, twist, _pts = interp_station(config, y_frac, config.airfoils.resample_points, te_min_mm)
        _, _, zc = _get_canonical_points_at_xc(_pts, bolt.x_c)
        canonical_pts = np.array([[bolt.x_c, zc]])
        le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
        placed = place_section(
            canonical_pts, chord, twist, config.planform.twist_axis_xc,
            y_mm=bolt.y_mm, le_x_mm=le_x, z_base_mm=z_base
        )
        pts.append(cq.Vector(*placed[0]))
    return pts


def build_reference_geometry(config: Config, sections: list[PlacedSection]) -> ReferenceGeometry:
    return ReferenceGeometry(
        spar_surfaces=build_spar_surfaces(config, sections),
        rib_planes=build_rib_planes(config),
        hinge_axes=build_hinge_axes(config),
        hardpoints=build_hardpoints(config),
    )
