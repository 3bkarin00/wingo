"""Per-station cove/nose SINGLE-arc construction (§8.5, refined —
docs/decisions/ADR-002, ADR-003).

Sections a solid with a plane PERPENDICULAR to the hinge axis (not a Y-normal
plane — they differ under sweep/dihedral/twist), finds the "normal foot"
(nearest point) on the upper/lower skin from the hinge-axis point C, and
builds the CS-nose / wing-cove profiles as arcs centered on C. An arc through
C's nearest point to a curve is tangent to that curve there by construction
(the nearest-point vector is always ⟂ the curve's tangent) — this is the
tangency mechanism the plan calls for, not a solved/iterated constraint.

ADR-003 deleted the old two-arc + Hermite-blend branch: on any twisted
config the two-arc branch fired at nearly every station (camber + a straight
hinge axis reliably produce Ru != Rl once the axis is off the true
equidistant height), and the G1-only blend at the junction is tangent- but
not curvature-continuous — a real, visible "lump" in the rendered nose, not
a rendering artifact (confirmed via a tessellation-tolerance rule-out and a
discrete curvature-angle proxy along the raw construction points — see
docs/r0_findings/p04.md). The fix is at the ROOT: backend/geometry/
reference.py now DERIVES the hinge axis height by least-squares fit to the
true equidistant point at many stations (rather than a straight line between
2 arithmetic camber-line means), which keeps Ru≈Rl close enough that a
SINGLE arc at R=(Ru+Rl)/2 is a good approximation everywhere — validated by
mean_radius_tangency_err_deg() at construction time (backend/geometry/
te_cut.py), which REJECTS a config outright if any station's residual
exceeds NOSE_TANGENCY_MAX_DEG rather than silently degrading the shape.

Every profile is returned as a dense ordered point polygon (not OCC arc/spline
edges) so it can be lofted with the same polygon-wire + ruled=True approach
already proven for the OML (docs/r0_findings/p02.md) — the "axis-centered"
property is then exact by direct computation, not an OCC-arc approximation.
Deliberately NOT a literal OCC circular edge (cq.Edge.makeCircle): mixing a
true circular edge with the straight aft-closing edges in one wire, then
ruled-lofting THAT across stations, is unverified behavior this project has
no R0 probe for (never invent an API) and would risk exactly the kind of
loft-surface unpredictability the dense-polygon approach was chosen to avoid
in the first place (r0_findings/p02.md). "Single arc, constant curvature" is
instead verified on the REAL BUILT SOLID by checking constant radius-from-
axis on a live OCC section (test_nose_is_single_arc, test_p04_te_cut.py) —
the same rigor, without the new boundary risk.

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

    @property
    def R(self) -> float:
        """Single-arc mean radius (ADR-003) — the CS nose and wing cove at
        this station both derive from this one value."""
        return (self.Ru + self.Rl) / 2.0


def mean_radius_tangency_err_deg(feet: StationFeet) -> float:
    """How far the single mean-radius arc (R=(Ru+Rl)/2) deviates from the
    TRUE per-side radius, expressed as an angle. arctan(|R-Ru|/Ru), not an
    arccos-based formulation: arccos has an infinite derivative at ratio=1,
    so it over-reports even a ~0.001mm mismatch as several tenths of a
    degree (measured directly — see docs/r0_findings/p04.md); arctan is
    well-behaved near zero and scales close to linearly with the real
    mismatch for the small angles this construction operates in."""
    R = feet.R
    err_u = np.degrees(np.arctan(abs(R - feet.Ru) / feet.Ru))
    err_l = np.degrees(np.arctan(abs(R - feet.Rl) / feet.Rl))
    return float(max(err_u, err_l))


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


def _forward_sweep_angles(angle_l: float, angle_u: float, n: int, extension_rad: float = 0.0) -> np.ndarray:
    """Angles from angle_l to angle_u sweeping through the FORWARD side (±π,
    i.e. -a / leading-edge direction) rather than the short way through 0
    (aft, toward the hinge). Pu/Pl sit above/below C, so angle_u > angle_l
    always holds for a real airfoil section; sweeping to angle_u - 2π and
    decreasing guarantees the pass through -π (≡ π).

    extension_rad > 0 extends the sweep PAST both true feet by that many
    radians (anti-unporting angular overlap, ADR-003 addendum A): the sweep
    decreases from angle_l to (angle_u - 2π), so extending past angle_l
    (the start) means starting at a HIGHER angle, and extending past
    angle_u (the end, in the -2π-shifted frame) means ending LOWER."""
    target = angle_u - 2 * np.pi if angle_u > angle_l else angle_u
    return np.linspace(angle_l + extension_rad, target - extension_rad, n)


def _to_3d(C: np.ndarray, a: np.ndarray, u: np.ndarray, local_xy: np.ndarray) -> np.ndarray:
    return C + np.outer(local_xy[:, 0], a) + np.outer(local_xy[:, 1], u)


def _overlap_extension_rad(max_deflection_deg: float, overlap_margin_deg: float) -> float:
    """Anti-unporting angular overlap (ADR-003 addendum A): the nose arc
    must not stop at Pu/Pl — standard control-surface practice extends it
    beyond each tangent point by (max_deflection_deg + a margin) so the
    curved nose still overlaps the fixed wing's cove lips at full
    deflection and never rotates out of the cove ("unporting")."""
    return np.radians(max_deflection_deg + overlap_margin_deg)


def build_nose_arc_points(
    feet: StationFeet, a: np.ndarray, u: np.ndarray,
    max_deflection_deg: float, overlap_margin_deg: float = tolerances.OVERLAP_MARGIN_DEG,
    n: int = 48,
) -> np.ndarray:
    """CS-nose forward contour (open polyline, 3D): a SINGLE arc centered on
    C, constant radius R=(Ru+Rl)/2 (ADR-003 — the two-arc/Hermite-blend
    branch is deleted entirely; ANY residual asymmetry is bounded by
    config-time validation in te_cut.py, not patched here with a blend).
    Extended beyond the true tangent points Pu/Pl by the anti-unporting
    angular overlap so the nose still overlaps the wing cove at full
    deflection."""
    extension = _overlap_extension_rad(max_deflection_deg, overlap_margin_deg)
    angles = _forward_sweep_angles(feet.angle_l, feet.angle_u, n, extension)
    local = feet.R * np.column_stack([np.cos(angles), np.sin(angles)])
    return _to_3d(feet.C, a, u, local)


def build_cove_arc_points(
    feet: StationFeet, a: np.ndarray, u: np.ndarray,
    max_deflection_deg: float, overlap_margin_deg: float = tolerances.OVERLAP_MARGIN_DEG,
    n: int = 48, extra_radius_mm: float = 0.0,
) -> np.ndarray:
    """Wing-cove forward contour (open polyline, 3D): a single concave arc
    centered on the SAME C, radius R + COVE_CLEARANCE_MM (never tangent to
    the nose — see tolerances.py), swept over the SAME extended angular
    range as the nose arc so the cove fully contains it at every deflection
    angle up to max_deflection_deg (anti-unporting, ADR-003 addendum A).

    `extra_radius_mm` grows the arc CONCENTRICALLY (same C, same angular
    sweep) — used by backend/geometry/te_cut.py's `build_cove_offset_region`
    to build the cove-following sandwich-layer boundaries iml.py needs
    inside the device window (0.0 = the true cove surface itself, the
    default every existing call site relies on)."""
    r_cove = feet.R + tolerances.COVE_CLEARANCE_MM + extra_radius_mm
    extension = _overlap_extension_rad(max_deflection_deg, overlap_margin_deg)
    angles = _forward_sweep_angles(feet.angle_l, feet.angle_u, n, extension)
    local = r_cove * np.column_stack([np.cos(angles), np.sin(angles)])
    return _to_3d(feet.C, a, u, local)
