"""D24 π-joint rib/skin bonding (plan.md §8.7 step 7b — WP2b).

Two halves, matching the recipe:

1. RIB OUTLINE MODIFICATION (`offset_skin_segments`, consumed by ribs.py):
   the rib's skin-contact segments — the upper and lower runs of the cavity
   section polygon, identified by chordwise position with
   PI_SKIN_END_MARGIN_FRAC left untouched at the LE/TE closures — are moved
   inward WITHIN the rib plane by (PI_BASE_THICKNESS_MM + PI_BOND_GAP_MM),
   along each point's local inward boundary normal. The polygon stays
   closed; the two small step edges where an offset run meets an untouched
   closure segment are exactly the recipe's "offset segments joined to the
   untouched fore/aft segments".

2. π PREFORM BODIES (`build_pi_preforms`): per rib, the ORIGINAL
   skin-contact chains (still on the cavity boundary/IML) are offset inward
   along the LOCAL IML SURFACE NORMAL by PI_BOND_GAP_MM (the adhesive
   line) — the per-point projection+normal technique
   probe_offset_curve_surface.py verified — then trimmed clear of every
   spar crossing (footprint x-interval + PI_SPAR_CLEARANCE_MM, from
   spars.spar_footprint, the same single source the rib cutouts use). Each
   surviving path segment becomes ONE preform body: the π cross-section
   (base + two legs) is placed at sampled frames along the path (tangent =
   path tangent, depth axis = local IML normal, spanwise axis = the rib
   plane normal ±Y) and lofted ruled=True.

   DELIBERATE DEVIATION from the recipe's "three swept boxes and union":
   the π section is a single simply-connected 12-corner polygon, so ONE
   loft produces the identical solid with zero fuse booleans — no F4
   tangency risk at the base↔leg junctions (which WOULD be exact shared
   boundaries if built as three boxes), no shard filtering, ~3x fewer
   lofts. Geometry is unchanged; only the construction is simpler.
   Recorded in changelog.md.

   Bond-gap guarantee BY CONSTRUCTION (the extension gate's test_slot_fit
   measures this): each leg's inner face sits at
   ±(rib_thickness/2 + PI_BOND_GAP_MM) from the rib midplane, so the
   leg↔rib face distance is exactly PI_BOND_GAP_MM; the base's skin-side
   face sits PI_BOND_GAP_MM off the IML along the local normal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.face_registry import FaceRegistry
from backend.geometry.spars import _local_cavity_normal, footprints_at
from backend.schema.models import Config


@dataclass
class PiSegment:
    """One π preform body (one trimmed path segment on one skin side)."""
    rib_y_mm: float
    side: str  # "upper" | "lower"
    solid: cq.Shape
    n_frames: int
    # Named bond faces (§8.8 centroid registry): the two leg inner faces —
    # RIB<y>_PI_<side><k>_LEG_BOND_{IN,OUT}board — recorded at creation and
    # matched immediately (a π body is a pure loft, no boolean ever touches
    # it, so the match is exact by construction; routing through the
    # registry anyway keeps one mechanism for every bond face).
    bond_faces: dict = field(default_factory=dict)


@dataclass
class PiSet:
    segments: list[PiSegment] = field(default_factory=list)
    # Path segments too short to carry a preform (fewer than 2 sample
    # points after spar trimming) — logged, not an error.
    skipped_short: list[tuple[float, str]] = field(default_factory=list)


def rib_skin_offset_mm() -> float:
    """How far ribs.py pulls the skin-contact segments inward (recipe:
    base thickness + bond gap, so base AND adhesive fit between rib edge
    and skin)."""
    return tolerances.PI_BASE_THICKNESS_MM + tolerances.PI_BOND_GAP_MM


def _split_skin_chains(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify the rib section polygon's points into upper-skin and
    lower-skin runs (boolean masks) by chordwise window + side of the local
    mid-height. `pts` is (N,3) ordered around the closed polygon (constant
    Y). Returns (upper_mask, lower_mask, inward_normals) where
    inward_normals[i] is the 2D (X,Z) inward boundary normal at point i."""
    x, z = pts[:, 0], pts[:, 2]
    x_min, x_max = x.min(), x.max()
    margin = tolerances.PI_SKIN_END_MARGIN_FRAC * (x_max - x_min)
    in_window = (x > x_min + margin) & (x < x_max - margin)
    z_mid = (z.max() + z.min()) / 2.0
    upper = in_window & (z >= z_mid)
    lower = in_window & (z < z_mid)

    # Local inward normal per point: perpendicular to the central-difference
    # tangent, oriented toward the polygon centroid.
    n_pts = len(pts)
    centroid = pts.mean(axis=0)
    normals = np.zeros((n_pts, 3))
    for i in range(n_pts):
        tang = pts[(i + 1) % n_pts] - pts[i - 1]
        nv = np.array([-tang[2], 0.0, tang[0]])  # rotate tangent 90° in the X-Z plane
        norm = np.linalg.norm(nv)
        if norm < 1e-12:
            nv = centroid - pts[i]
            norm = np.linalg.norm(nv)
        nv = nv / norm
        if np.dot(nv, centroid - pts[i]) < 0:
            nv = -nv
        normals[i] = nv
    return upper, lower, normals


def offset_skin_segments(pts: np.ndarray) -> np.ndarray:
    """The rib-outline modification (module docstring 1): returns a copy of
    the ordered polygon points with the skin-contact runs moved inward by
    rib_skin_offset_mm() along each point's local inward boundary normal."""
    upper, lower, normals = _split_skin_chains(pts)
    moved = pts.copy()
    d = rib_skin_offset_mm()
    mask = upper | lower
    moved[mask] = pts[mask] + d * normals[mask]
    return moved


def _spar_x_exclusions(config: Config, y_mm: float) -> list[tuple[float, float]]:
    """Chordwise (global X) intervals to trim out of the π paths at this
    rib: each spar footprint's placed X extent + PI_SPAR_CLEARANCE_MM."""
    out = []
    for fp in footprints_at(config, y_mm, 0.0):
        xs = []
        for part in fp.parts:
            bb = part.wire.BoundingBox()
            xs.extend([bb.xmin, bb.xmax])
        out.append((min(xs) - tolerances.PI_SPAR_CLEARANCE_MM,
                    max(xs) + tolerances.PI_SPAR_CLEARANCE_MM))
    return out


def _trimmed_runs(chain: np.ndarray, exclusions: list[tuple[float, float]]) -> list[np.ndarray]:
    """Split an x-sorted point chain into maximal runs whose points fall
    outside every exclusion interval."""
    keep = np.ones(len(chain), dtype=bool)
    for lo, hi in exclusions:
        keep &= ~((chain[:, 0] >= lo) & (chain[:, 0] <= hi))
    runs, current = [], []
    for p, k in zip(chain, keep):
        if k:
            current.append(p)
        elif current:
            runs.append(np.array(current))
            current = []
    if current:
        runs.append(np.array(current))
    return runs


def _pi_profile_corners(rib_thickness_mm: float) -> list[tuple[float, float]]:
    """π cross-section polygon in frame coordinates (u = spanwise from the
    rib midplane, d = depth from the IML point along the inward normal).
    Single simply-connected polygon (module docstring's deliberate
    deviation)."""
    gap = tolerances.PI_BOND_GAP_MM
    base_t = tolerances.PI_BASE_THICKNESS_MM
    leg_t = tolerances.PI_LEG_THICKNESS_MM
    leg_h = tolerances.PI_LEG_HEIGHT_MM
    leg_in = rib_thickness_mm / 2.0 + gap
    leg_out = leg_in + leg_t
    b = leg_out + tolerances.PI_BASE_SHOULDER_MM  # base half-width (derived, always > leg_out)
    d0, d1, d2 = gap, gap + base_t, gap + base_t + leg_h
    return [
        (-b, d0), (b, d0), (b, d1),
        (leg_out, d1), (leg_out, d2), (leg_in, d2), (leg_in, d1),
        (-leg_in, d1), (-leg_in, d2), (-leg_out, d2), (-leg_out, d1),
        (-b, d1),
    ]


def _loft_pi_segment(
    run: np.ndarray, cavity_faces: list[cq.Face], rib_thickness_mm: float, y_mm: float,
) -> tuple[cq.Solid, int] | None:
    """One π preform body along `run` (x-sorted points ON the cavity
    boundary at the rib plane). None if the run is too short to loft."""
    n = min(len(run), tolerances.SPAR_CAP_SWEEP_FRAMES)
    if n < 2:
        return None
    idx = np.linspace(0, len(run) - 1, n).round().astype(int)
    pts = run[np.unique(idx)]
    if len(pts) < 2:
        return None

    profile = _pi_profile_corners(rib_thickness_mm)
    y_axis = np.array([0.0, 1.0, 0.0])
    interior_hint = pts.mean(axis=0).copy()

    wires = []
    for i, p in enumerate(pts):
        if i == 0:
            tang = pts[1] - pts[0]
        elif i == len(pts) - 1:
            tang = pts[-1] - pts[-2]
        else:
            tang = pts[i + 1] - pts[i - 1]
        tang = tang / np.linalg.norm(tang)

        # Depth axis: local IML normal, forced into the rib plane (paths lie
        # in the Y=y_mm plane; the projection's tiny Y component would tilt
        # the profile out of plane).
        toward = interior_hint + np.array([0.0, 0.0, -np.sign(p[2] - interior_hint[2])])
        nrm = _local_cavity_normal(cavity_faces, p, toward)
        nrm = nrm - np.dot(nrm, y_axis) * y_axis
        norm = np.linalg.norm(nrm)
        if norm < 1e-9:
            return None
        nrm = nrm / norm

        corners = [
            cq.Vector(*(p + u * y_axis + d * nrm)) for (u, d) in profile
        ]
        wires.append(cq.Wire.makePolygon(corners, close=True))
    return cq.Solid.makeLoft(wires, ruled=True), len(pts)


def build_pi_preforms(
    config: Config, hollow_interior: cq.Shape,
    rib_outlines: list[tuple[float, np.ndarray]], rib_thickness_mm: float,
) -> PiSet:
    """π preform bodies for every rib (module docstring 2). `rib_outlines`
    is [(y_mm, ordered (N,3) section polygon points)] — the ORIGINAL,
    un-offset outlines (ribs.py exposes them on its RibSet), since the π
    paths live on the true cavity boundary, not on the offset rib edge."""
    cavity_faces = hollow_interior.Faces()
    result = PiSet()
    for y_mm, pts in rib_outlines:
        upper, lower, _normals = _split_skin_chains(pts)
        exclusions = _spar_x_exclusions(config, y_mm)
        for side, mask in (("upper", upper), ("lower", lower)):
            chain = pts[mask]
            if len(chain) < 2:
                result.skipped_short.append((y_mm, side))
                continue
            chain = chain[np.argsort(chain[:, 0])]
            for k, run in enumerate(_trimmed_runs(chain, exclusions)):
                lofted = _loft_pi_segment(run, cavity_faces, rib_thickness_mm, y_mm)
                if lofted is None:
                    result.skipped_short.append((y_mm, side))
                    continue
                solid, n_frames = lofted
                # Record + match the two leg inner faces (PiSegment.bond_faces
                # docstring). Leg inner faces are the planar ±Y faces sitting
                # at exactly rib_y ± (rib_t/2 + PI_BOND_GAP_MM).
                leg_in = rib_thickness_mm / 2.0 + tolerances.PI_BOND_GAP_MM
                reg = FaceRegistry()
                for face in solid.Faces():
                    try:
                        n = face.normalAt()
                    except Exception:  # noqa: BLE001
                        continue
                    if abs(abs(n.y) - 1.0) > 1e-6:
                        continue
                    off = face.Center().y - y_mm
                    if abs(abs(off) - leg_in) < 1e-6:
                        board = "IN" if off < 0 else "OUT"
                        reg.record_face(
                            f"RIB{y_mm:.0f}_PI_{side.upper()}{k}_LEG_BOND_{board}", face,
                        )
                result.segments.append(PiSegment(
                    rib_y_mm=y_mm, side=side, solid=solid, n_frames=n_frames,
                    bond_faces=reg.match(solid),
                ))
    return result
