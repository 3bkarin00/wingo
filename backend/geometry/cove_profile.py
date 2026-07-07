"""Per-station cove/nose arc construction (§8.5, refined — docs/decisions/ADR-002).

Sections a solid with a plane PERPENDICULAR to the hinge axis (not a Y-normal
plane — they differ under sweep/dihedral), finds the "normal foot" (nearest
point) on the upper/lower skin from the hinge-axis point C, and builds the
CS-nose / wing-cove profiles as arcs centered on C. An arc through C's nearest
point to a curve is tangent to that curve there by construction (the
nearest-point vector is always ⟂ the curve's tangent) — this is the tangency
mechanism the plan calls for, not a solved/iterated constraint.

Every profile is returned as a dense ordered point polygon (not OCC arc/spline
edges) so it can be lofted with the same polygon-wire + ruled=True approach
already proven for the OML (docs/r0_findings/p02.md) — the "axis-centered"
property is then exact by direct computation, not an OCC-arc approximation.

PERFORMANCE NOTE: sectioning the OML with `BRepAlgoAPI_Section` (below, kept
as documented ground truth) costs ~5s per call against the OML's ~200-facet
ruled-polygon surface — prohibitive for the 24-48 stations a real cut needs.
Since the OML is a RULED loft between polygon wires (P2's own construction
decision, r0_findings/p02.md), a cross-section is exactly a per-vertex
line-plane intersection between the two bracketing input sections — that IS
the mathematical definition of a ruled surface, not an approximation of one.
`analytic_section_points` computes this directly in vectorized numpy
(~0.4ms). Cross-checked against `section_points` (the real OCC boolean) on a
live station: Ru/Rl agreed to <0.06 mm and the tangency-deviation metric
agreed to within a fraction of a degree — see docs/r0_findings/p04.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from backend import tolerances
from backend.geometry.sections import PlacedSection

_SECTION_SAMPLES_PER_EDGE = 40
_ANALYTIC_UPSAMPLE = 8  # extra interpolated points per polygon edge (tangent accuracy)


@dataclass
class StationFeet:
    """Normal-foot geometry at one station, in the (a, u) frame local to C."""

    C: np.ndarray
    Ru: float
    Rl: float
    angle_u: float  # angle of Pu in the local (a, u) frame, radians
    angle_l: float  # angle of Pl
    tangent_dev_deg: float  # measured C->foot vs skin-tangent deviation from 90°


def section_points(shape: cq.Shape, C: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Sample the cross-section of `shape` by the plane through C, normal h,
    into a dense (N, 3) point cloud."""
    pln = gp_Pln(gp_Pnt(*C), gp_Dir(*h))
    op = BRepAlgoAPI_Section(shape.wrapped, pln)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("BRepAlgoAPI_Section failed")
    sec_shape = cq.Shape.cast(op.Shape())
    pts = []
    for edge in sec_shape.Edges():
        adaptor = BRepAdaptor_Curve(edge.wrapped)
        t0, t1 = adaptor.FirstParameter(), adaptor.LastParameter()
        for i in range(_SECTION_SAMPLES_PER_EDGE):
            t = t0 + (t1 - t0) * i / (_SECTION_SAMPLES_PER_EDGE - 1)
            v = adaptor.Value(t)
            pts.append([v.X(), v.Y(), v.Z()])
    if not pts:
        raise RuntimeError("empty section — plane did not intersect the shape")
    return np.array(pts)


def analytic_section_points(
    sections: list[PlacedSection], C: np.ndarray, h: np.ndarray
) -> np.ndarray:
    """Exact cross-section of the ruled OML loft by the plane through C,
    normal h — computed analytically (see module docstring) instead of the
    ~5s-per-call OCC boolean. Sections must be the SAME half-span list
    `build_planform_sections` produced for the OML this is sectioning
    (scoped to mirror:false configs, matching the existing device-config
    scoping in docs/r0_findings/p04.md)."""
    ys = np.array([s.y_mm for s in sections])
    k = int(np.searchsorted(ys, C[1], side="right") - 1)
    k = max(0, min(k, len(sections) - 2))
    P0, P1 = sections[k].points, sections[k + 1].points  # (N, 3), same N & order

    denom = (P1 - P0) @ h
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    t = np.clip(((C - P0) @ h) / denom, 0.0, 1.0)
    verts = P0 + t[:, None] * (P1 - P0)

    # Upsample each polygon edge by linear interpolation (still exact for a
    # ruled/polygon surface) so the tangency-deviation estimate downstream
    # has a dense enough local neighborhood — see module docstring benchmark.
    j = np.arange(_ANALYTIC_UPSAMPLE) / _ANALYTIC_UPSAMPLE
    a_pts = verts
    b_pts = np.roll(verts, -1, axis=0)
    dense = (a_pts[:, None, :] + j[None, :, None] * (b_pts - a_pts)[:, None, :]).reshape(-1, 3)
    return dense


def find_station_feet(pts: np.ndarray, C: np.ndarray, a: np.ndarray, u: np.ndarray) -> StationFeet:
    """Normal feet of C on the upper (u>0 side) and lower (u<0 side) skin
    curves within a section point cloud, plus a numerical tangency check."""
    rel = pts - C
    side = rel @ u
    upper = pts[side > 0]
    lower = pts[side < 0]
    if len(upper) < 3 or len(lower) < 3:
        raise RuntimeError("section split produced too few upper/lower points")

    du = np.linalg.norm(upper - C, axis=1)
    dl = np.linalg.norm(lower - C, axis=1)
    iu, il = int(np.argmin(du)), int(np.argmin(dl))
    Pu, Ru = upper[iu], float(du[iu])
    Pl, Rl = lower[il], float(dl[il])

    def local_angle(P: np.ndarray) -> float:
        d = P - C
        return float(np.arctan2(np.dot(d, u), np.dot(d, a)))

    def tangent_deviation_deg(cloud: np.ndarray, idx: int, foot: np.ndarray) -> float:
        order = np.argsort(np.linalg.norm(cloud - foot, axis=1))
        neighbors = cloud[order[1:4]]
        tangent = neighbors[-1] - neighbors[0]
        norm = np.linalg.norm(tangent)
        if norm < 1e-9:
            return 0.0
        tangent /= norm
        radial = (foot - C) / np.linalg.norm(foot - C)
        cos_angle = abs(np.clip(np.dot(tangent, radial), -1.0, 1.0))
        return abs(90.0 - np.degrees(np.arccos(cos_angle)))

    dev_u = tangent_deviation_deg(upper, iu, Pu)
    dev_l = tangent_deviation_deg(lower, il, Pl)

    return StationFeet(
        C=C, Ru=Ru, Rl=Rl,
        angle_u=local_angle(Pu), angle_l=local_angle(Pl),
        tangent_dev_deg=max(dev_u, dev_l),
    )


def _forward_sweep_angles(angle_l: float, angle_u: float, n: int) -> np.ndarray:
    """Angles from angle_l to angle_u sweeping through the FORWARD side (±π,
    i.e. -a / leading-edge direction) rather than the short way through 0
    (aft, toward the hinge). Pu/Pl sit above/below C, so angle_u > angle_l
    always holds for a real airfoil section; sweeping to angle_u - 2π and
    decreasing guarantees the pass through -π (≡ π)."""
    target = angle_u - 2 * np.pi if angle_u > angle_l else angle_u
    return np.linspace(angle_l, target, n)


def _to_3d(C: np.ndarray, a: np.ndarray, u: np.ndarray, local_xy: np.ndarray) -> np.ndarray:
    return C + np.outer(local_xy[:, 0], a) + np.outer(local_xy[:, 1], u)


def build_nose_arc_points(
    feet: StationFeet, a: np.ndarray, u: np.ndarray, n: int = 48
) -> np.ndarray:
    """CS-nose forward contour from Pl to Pu (open polyline, 3D), arcs
    centered on C. Single blended-radius arc if the feet radii match closely;
    else two true-radius arcs joined by a short Hermite (G1) blend crossing
    the chord line forward of C."""
    angles = _forward_sweep_angles(feet.angle_l, feet.angle_u, n)

    if abs(feet.Ru - feet.Rl) <= tolerances.NOSE_RADII_MATCH_MM:
        # Single arc at the mean radius, blended onto the exact feet at both
        # ends over the outer 10% of the sweep (a "short G1 blend" — the
        # branch's own precondition bounds the correction to <= half the
        # match tolerance).
        r_mean = (feet.Ru + feet.Rl) / 2.0
        t = np.linspace(0.0, 1.0, n)
        blend = np.clip(np.minimum(t, 1 - t) / 0.1, 0.0, 1.0)  # 1 in the middle, ->0 at ends
        r_end = np.where(t < 0.5, feet.Rl, feet.Ru)
        radii = blend * r_mean + (1 - blend) * r_end
    else:
        # Two true-radius arcs + a Hermite blend crossing angle=π (forward of
        # C on the chord line), tangent-matched to each arc at the junction.
        half = n // 2
        blend_frac = 0.25  # fraction of each half given to the Hermite blend
        n_arc = int(half * (1 - blend_frac))

        theta_1, theta_2 = angles[n_arc - 1], angles[n - n_arc]
        p1 = feet.Rl * np.array([np.cos(theta_1), np.sin(theta_1)])
        p2 = feet.Ru * np.array([np.cos(theta_2), np.sin(theta_2)])
        # tangent direction of a circle at angle θ, in the sweep direction.
        dtheta = np.sign(theta_2 - theta_1) or -1.0
        t1 = dtheta * feet.Rl * np.array([-np.sin(theta_1), np.cos(theta_1)])
        t2 = dtheta * feet.Ru * np.array([-np.sin(theta_2), np.cos(theta_2)])
        t1, t2 = t1 / np.linalg.norm(t1), t2 / np.linalg.norm(t2)
        seg_len = np.linalg.norm(p2 - p1)

        # tt sampled on the OPEN interval (0, 1): tt=0/1 would reproduce p1/p2
        # exactly, which local[:n_arc]/local[n-n_arc:] already contribute as
        # their own last/first point — an inclusive endpoint here would give
        # two consecutive identical points (a zero-length polygon edge) at
        # each junction. m is unchanged so the total point count stays n,
        # required for cross-station vertex-count consistency in the loft.
        m = (n - n_arc) - n_arc
        tt = np.linspace(0.0, 1.0, m + 2)[1:-1][:, None]
        h00 = 2 * tt**3 - 3 * tt**2 + 1
        h10 = tt**3 - 2 * tt**2 + tt
        h01 = -2 * tt**3 + 3 * tt**2
        h11 = tt**3 - tt**2
        blend_xy = h00 * p1 + h10 * seg_len * t1 + h01 * p2 + h11 * seg_len * t2

        local = np.empty((n, 2))
        local[:n_arc] = feet.Rl * np.column_stack([np.cos(angles[:n_arc]), np.sin(angles[:n_arc])])
        local[n_arc: n - n_arc] = blend_xy
        local[n - n_arc:] = feet.Ru * np.column_stack([np.cos(angles[n - n_arc:]), np.sin(angles[n - n_arc:])])
        return _to_3d(feet.C, a, u, local)

    local = radii[:, None] * np.column_stack([np.cos(angles), np.sin(angles)])
    return _to_3d(feet.C, a, u, local)


def build_cove_arc_points(
    feet: StationFeet, a: np.ndarray, u: np.ndarray, n: int = 48
) -> np.ndarray:
    """Wing-cove forward contour from Pl' to Pu' (open polyline, 3D): a single
    concave arc centered on the SAME C, radius max(Ru, Rl) + COVE_CLEARANCE_MM
    (never tangent to the nose — see tolerances.py)."""
    r_cove = max(feet.Ru, feet.Rl) + tolerances.COVE_CLEARANCE_MM
    angles = _forward_sweep_angles(feet.angle_l, feet.angle_u, n)
    local = r_cove * np.column_stack([np.cos(angles), np.sin(angles)])
    return _to_3d(feet.C, a, u, local)
