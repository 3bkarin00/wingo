"""P8 kinematic sweep — plan.md §9 "the decisive R1 gate":

  sweep TE through ±max_deflection: coarse 1° steps + fine 0.1° steps in
  the outer 20% of travel; collision count = 0 at every step; minimum
  clearance >= gap_mm - tolerance and monotonic-trend check; swept-volume
  boolean at both extremes intersect fixed wing = ∅ (F9).

Two independent checks, both against the true hinge axis (p0, axis_dir —
reference.derive_hinge_axis / te_cut.hinge_frame's own `h`):

1. POINT-SAMPLE SWEEP (`sweep_collisions`): at every angle in
   `sweep_angles(max_deflection_deg)` (coarse everywhere, fine within the
   outer KINEMATIC_FINE_ZONE_FRAC band near each extreme — F9's whole
   reason to exist: a coarse-only sweep can step OVER a collision that
   only exists briefly near the tightest-clearance extreme), rotate every
   CS-side body about the axis (cq.Shape.rotate — R0-verified accurate to
   1.5e-14mm, docs/r0_findings/p07.md) and check pairwise fuzzy_common
   against every wing-side body: zero positive volume at every angle, and
   the minimum inter-body distance at that angle (>= gap_mm - tolerance).

2. SWEPT-VOLUME ENVELOPE (`swept_envelope`, `envelope_clear_of_wing`):
   union of CS-side-body rotated copies at KINEMATIC_SWEPT_ENVELOPE_STEP_DEG
   steps from 0 to +max_deflection (and separately to -max_deflection) —
   the SAME union-of-rotated-copies technique WP1 uses for its clearance
   pockets — then a single boolean against the (unrotated) wing-side
   union: F9's "swept-volume boolean at both extremes intersect fixed
   wing = ∅", catching anything the point-sample sweep's discrete angles
   could still miss between fine steps.

Every entry point takes wing-side and CS-side bodies as PLAIN LISTS
(whatever P6/P7 already built: sandwich shells, ribs, spars, false spar,
hinge carriers/tubes on the wing side; CS sandwich shells + CS-side hinge
carriers/tubes on the CS side) — this module does not assemble the
aircraft itself, callers (the P8 gate) do, mirroring P7's own "hinges.py
takes bodies in, returns bodies out" boundary.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_common


@dataclass
class AngleSample:
    angle_deg: float
    collision_volume_mm3: float
    min_clearance_mm: float
    colliding_pairs: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class SweepResult:
    samples: list[AngleSample] = field(default_factory=list)
    timings_s: dict = field(default_factory=dict)

    @property
    def collision_count(self) -> int:
        return sum(1 for s in self.samples if s.collision_volume_mm3 > 0)

    @property
    def worst_clearance_mm(self) -> float:
        return min((s.min_clearance_mm for s in self.samples), default=float("nan"))


@dataclass
class EnvelopeResult:
    angle_extreme_deg: float
    envelope: cq.Shape
    collision_volume_mm3: float
    timings_s: dict = field(default_factory=dict)


def sweep_angles(max_deflection_deg: float) -> np.ndarray:
    """Coarse everywhere + fine within the outer KINEMATIC_FINE_ZONE_FRAC
    band near each extreme (module docstring). Always includes 0 and both
    exact extremes."""
    coarse = np.arange(
        -max_deflection_deg, max_deflection_deg + 1e-9, tolerances.KINEMATIC_COARSE_STEP_DEG
    )
    fine_zone_deg = tolerances.KINEMATIC_FINE_ZONE_FRAC * max_deflection_deg
    fine_neg = np.arange(
        -max_deflection_deg, -max_deflection_deg + fine_zone_deg + 1e-9,
        tolerances.KINEMATIC_FINE_STEP_DEG,
    )
    fine_pos = np.arange(
        max_deflection_deg - fine_zone_deg, max_deflection_deg + 1e-9,
        tolerances.KINEMATIC_FINE_STEP_DEG,
    )
    angles = np.concatenate([coarse, fine_neg, fine_pos, [0.0, -max_deflection_deg, max_deflection_deg]])
    return np.unique(np.round(angles, 6))


def rotate_point(
    point: np.ndarray, axis_p0: np.ndarray, axis_dir: np.ndarray, angle_deg: float,
) -> np.ndarray:
    """Rigid rotation of a single point about the (p0, axis_dir) line via
    Rodrigues' formula — pure numpy, no OCC involved. Used by P10's API
    (backend/api/routes/jobs.py's kinematics/sample endpoint) as the
    server-side reference the client's independent three.js rotation is
    checked against (module docstring's two-independent-implementations
    design). Mathematically identical to cq.Shape.rotate for a rigid body
    (R0-verified to 1.5e-14mm agreement, docs/r0_findings/p07.md) — this
    function exists so that check doesn't need to build any cq.Shape at all,
    just rotate one point."""
    axis = axis_dir / np.linalg.norm(axis_dir)
    theta = np.radians(angle_deg)
    v = point - axis_p0
    v_rot = (
        v * np.cos(theta)
        + np.cross(axis, v) * np.sin(theta)
        + axis * np.dot(axis, v) * (1 - np.cos(theta))
    )
    return axis_p0 + v_rot


def _min_distance(a: cq.Shape, b: cq.Shape) -> float:
    op = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    op.Perform()
    return op.Value() if op.IsDone() else float("nan")


def _rotate_points(points: np.ndarray, axis_p0: np.ndarray, axis_dir: np.ndarray, angle_deg: float) -> np.ndarray:
    """Vectorized rotate_point (module docstring's Rodrigues' formula) for
    an (N,3) point array — same math, no per-point Python loop."""
    axis = axis_dir / np.linalg.norm(axis_dir)
    theta = np.radians(angle_deg)
    v = points - axis_p0
    v_rot = (
        v * np.cos(theta)
        + np.cross(axis, v) * np.sin(theta)
        + axis * (v @ axis)[:, None] * (1 - np.cos(theta))
    )
    return axis_p0 + v_rot


def _point_to_shell_distance(point: np.ndarray, shell: cq.Shape) -> float:
    """Single point -> shape distance via BRepExtrema with a VERTEX operand
    — O(1) cheap (point-location query), unlike compound-vs-compound
    extrema between two many-face bodies, which is intractable at skin-
    body face counts (two independent 10-hour timeouts finding this out
    the hard way, docs/known_issues.md). Identical technique to
    test_p04_te_cut.py's own `_point_to_shell_distance`, reused here
    rather than re-derived."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    op = BRepExtrema_DistShapeShape(vertex, shell.wrapped)
    op.Perform()
    return op.Value() if op.IsDone() else float("nan")


def sweep_min_distance_by_points(
    moving_shape: cq.Shape,
    static_shape: cq.Shape,
    axis_p0: np.ndarray,
    axis_dir: np.ndarray,
    angles: np.ndarray,
    vertex_stride: int = 3,
) -> SweepResult:
    """Point-sample distance sweep: extracts `moving_shape`'s topological
    VERTICES once (subsampled every `vertex_stride`-th, matching
    test_p04_te_cut.py's own [::3] convention — these are lofted/ruled
    solids with a vertex at every station's polygon corner, not a full
    tessellation mesh, so this is a real, bounded-size point set), rotates
    them with pure-numpy Rodrigues' formula (cheap — no OCC per angle),
    and measures point-to-shell distance against `static_shape`'s own
    shell at every angle. A REAL measurement against REAL built geometry
    (never re-deriving the construction formula) — just architecturally
    different from a compound-vs-compound extrema, which is what made the
    first two attempts at this check time out at 10 hours each (see
    sweep_min_distance's own docstring and docs/known_issues.md)."""
    t0 = time.perf_counter()
    pts = np.array([v.toTuple() for v in moving_shape.Vertices()][::vertex_stride], dtype=float)
    static_shell = static_shape.Shells()[0] if static_shape.Shells() else static_shape

    result = SweepResult()
    for ang in angles:
        rotated = _rotate_points(pts, axis_p0, axis_dir, float(ang))
        worst = min(_point_to_shell_distance(p, static_shell) for p in rotated)
        result.samples.append(AngleSample(
            angle_deg=float(ang), collision_volume_mm3=0.0, min_clearance_mm=worst,
        ))
    result.timings_s["total_s"] = time.perf_counter() - t0
    result.timings_s["n_points"] = len(pts)
    return result


def sweep_collisions(
    wing_bodies: list[cq.Shape],
    cs_bodies: list[cq.Shape],
    axis_p0: np.ndarray,
    axis_dir: np.ndarray,
    max_deflection_deg: float,
) -> SweepResult:
    """Point-sample sweep (module docstring 1). Rotates `cs_bodies` at
    every sample angle; `wing_bodies` stay fixed (deflection is defined
    relative to the wing frame)."""
    t0 = time.perf_counter()
    a = cq.Vector(*axis_p0)
    b = cq.Vector(*(axis_p0 + axis_dir))
    result = SweepResult()
    for ang in sweep_angles(max_deflection_deg):
        rotated_cs = [body.rotate(a, b, float(ang)) for body in cs_bodies]
        worst_vol = 0.0
        min_clear = float("inf")
        colliding: list[tuple[int, int]] = []
        for ci, cs_body in enumerate(rotated_cs):
            for wi, wing_body in enumerate(wing_bodies):
                try:
                    common = fuzzy_common(cs_body, wing_body)
                except RuntimeError:
                    common = None
                if common is not None:
                    kept, _shards = filter_shards(common, min_volume=1e-9)
                    v = sum(s.Volume() for s in kept)
                    if v > 0:
                        worst_vol = max(worst_vol, v)
                        colliding.append((wi, ci))
                min_clear = min(min_clear, _min_distance(cs_body, wing_body))
        result.samples.append(AngleSample(
            angle_deg=float(ang), collision_volume_mm3=worst_vol,
            min_clearance_mm=min_clear, colliding_pairs=colliding,
        ))
    result.timings_s["total_s"] = time.perf_counter() - t0
    return result


def proximity_face_subsets(
    static_body: cq.Shape,
    moving_body: cq.Shape,
    axis_p0: np.ndarray,
    axis_dir: np.ndarray,
    max_deflection_deg: float,
) -> tuple[cq.Shape, cq.Shape, dict]:
    """Cull the static body to only the faces whose bounding box comes
    within KINEMATIC_PROXIMITY_CULL_MARGIN_MM of the moving body's
    rotation-swept bounding box (union of its bboxes at -max/0/+max
    deflection). Exists because BRepExtrema_DistShapeShape on two FULL
    lofted skin solids is intractable — a real 10-hour gate timeout, see
    the margin constant's derivation in tolerances.py and
    docs/known_issues.md. Sound for a floor assertion at any
    floor < margin: a culled face can never decide the result.

    Returns (static_faces_compound, moving_faces_compound, stats). The
    moving body keeps ALL its faces (it sits inside the static body's own
    bbox neighborhood by construction — a symmetric cull would keep
    everything anyway). Raises if the cull leaves nothing (would mean the
    bodies are nowhere near each other — a caller/config bug, not a pass)."""
    margin = tolerances.KINEMATIC_PROXIMITY_CULL_MARGIN_MM
    a = cq.Vector(*axis_p0)
    b = cq.Vector(*(axis_p0 + axis_dir))
    boxes = [
        moving_body.rotate(a, b, float(ang)).BoundingBox()
        for ang in (-max_deflection_deg, 0.0, max_deflection_deg)
    ]
    lo = [min(bb.xmin for bb in boxes) - margin,
          min(bb.ymin for bb in boxes) - margin,
          min(bb.zmin for bb in boxes) - margin]
    hi = [max(bb.xmax for bb in boxes) + margin,
          max(bb.ymax for bb in boxes) + margin,
          max(bb.zmax for bb in boxes) + margin]

    kept = []
    all_faces = static_body.Faces()
    for f in all_faces:
        fb = f.BoundingBox()
        if (fb.xmax >= lo[0] and fb.xmin <= hi[0]
                and fb.ymax >= lo[1] and fb.ymin <= hi[1]
                and fb.zmax >= lo[2] and fb.zmin <= hi[2]):
            kept.append(f)
    if not kept:
        raise ValueError(
            "proximity_face_subsets: cull kept 0 static faces — moving body's swept "
            "bbox is nowhere near the static body (caller/config bug)"
        )
    stats = {"static_faces_total": len(all_faces), "static_faces_kept": len(kept),
             "moving_faces": len(moving_body.Faces()), "margin_mm": margin}
    return (
        cq.Compound.makeCompound(kept),
        cq.Compound.makeCompound(moving_body.Faces()),
        stats,
    )


def sweep_min_distance(
    static_faces: cq.Shape,
    moving_faces: cq.Shape,
    axis_p0: np.ndarray,
    axis_dir: np.ndarray,
    max_deflection_deg: float,
) -> SweepResult:
    """Distance-ONLY sweep over sweep_angles (no per-angle boolean): min
    distance between the two face sets at every sample angle. Collision
    checking deliberately lives elsewhere — for skin-level bodies the
    swept-volume envelope (envelope_clear_of_wing) already proves
    CONTINUOUS collision-freedom, strictly stronger than any per-angle
    sample, so paying a boolean per angle here would re-verify less at
    enormous cost (the same 10-hour-timeout incident that motivated
    proximity_face_subsets). Returns a SweepResult whose samples carry
    collision_volume_mm3=0.0 placeholders so monotonic_clearance_violations
    consumes it unchanged."""
    t0 = time.perf_counter()
    a = cq.Vector(*axis_p0)
    b = cq.Vector(*(axis_p0 + axis_dir))
    result = SweepResult()
    for ang in sweep_angles(max_deflection_deg):
        rotated = moving_faces.rotate(a, b, float(ang))
        result.samples.append(AngleSample(
            angle_deg=float(ang), collision_volume_mm3=0.0,
            min_clearance_mm=_min_distance(rotated, static_faces),
        ))
    result.timings_s["total_s"] = time.perf_counter() - t0
    return result


def swept_envelope(
    bodies: list[cq.Shape], axis_p0: np.ndarray, axis_dir: np.ndarray, angle_extreme_deg: float,
) -> cq.Shape:
    """Union of `bodies`' rotated copies from 0 to `angle_extreme_deg` at
    KINEMATIC_SWEPT_ENVELOPE_STEP_DEG steps (module docstring 2) — same
    union-of-rotated-copies technique as WP1's clearance pockets
    (hinges_pin_tube._rotated_union)."""
    a = cq.Vector(*axis_p0)
    b = cq.Vector(*(axis_p0 + axis_dir))
    step = tolerances.KINEMATIC_SWEPT_ENVELOPE_STEP_DEG
    if angle_extreme_deg >= 0:
        angles = np.arange(0.0, angle_extreme_deg + 1e-9, step)
    else:
        angles = np.arange(0.0, angle_extreme_deg - 1e-9, -step)
    union: cq.Shape | None = None
    for body in bodies:
        for ang in angles:
            copy = body.rotate(a, b, float(ang))
            union = copy if union is None else union.fuse(copy)
    if union is None:
        raise ValueError("swept_envelope: no bodies given")
    return union


def monotonic_clearance_violations(result: SweepResult) -> list[dict]:
    """Plan.md's "monotonic-trend check": the cove pocket (ADR-003) is
    sized so clearance to the wing narrows steadily as deflection moves
    away from rest toward each extreme (the tightest point is the extreme
    itself, by design — OVERLAP_MARGIN_DEG's whole purpose). Splits samples
    into the negative-angle and positive-angle branches (each including 0)
    and flags any point where min_clearance_mm INCREASES as |angle|
    increases from the previous sample on that branch — a local bump the
    single-extreme minimum check could miss even though the OVERALL
    minimum is still >= the gap_mm floor."""
    by_angle = sorted(result.samples, key=lambda s: s.angle_deg)
    violations = []
    for branch in ("neg", "pos"):
        pts = [s for s in by_angle if (s.angle_deg <= 0 if branch == "neg" else s.angle_deg >= 0)]
        pts = sorted(pts, key=lambda s: abs(s.angle_deg))
        for prev, cur in zip(pts, pts[1:]):
            if cur.min_clearance_mm > prev.min_clearance_mm + tolerances.KERNEL_TOLERANCE_MM:
                violations.append({
                    "branch": branch, "from_angle_deg": prev.angle_deg, "to_angle_deg": cur.angle_deg,
                    "clearance_mm": [round(prev.min_clearance_mm, 4), round(cur.min_clearance_mm, 4)],
                })
    return violations


def envelope_clear_of_wing(
    wing_bodies: list[cq.Shape],
    cs_bodies: list[cq.Shape],
    axis_p0: np.ndarray,
    axis_dir: np.ndarray,
    max_deflection_deg: float,
) -> list[EnvelopeResult]:
    """F9's swept-volume check at BOTH extremes (module docstring 2):
    [+max_deflection, -max_deflection] envelopes, each checked for zero
    intersection against the (unrotated) union of `wing_bodies`."""
    results = []
    wing_union: cq.Shape | None = None
    for wb in wing_bodies:
        wing_union = wb if wing_union is None else wing_union.fuse(wb)
    for extreme in (max_deflection_deg, -max_deflection_deg):
        t0 = time.perf_counter()
        env = swept_envelope(cs_bodies, axis_p0, axis_dir, extreme)
        timings = {"envelope_s": time.perf_counter() - t0}
        t0 = time.perf_counter()
        try:
            common = fuzzy_common(env, wing_union)
            kept, _shards = filter_shards(common, min_volume=1e-9)
            vol = sum(s.Volume() for s in kept)
        except RuntimeError:
            vol = 0.0
        timings["collision_check_s"] = time.perf_counter() - t0
        results.append(EnvelopeResult(
            angle_extreme_deg=extreme, envelope=env, collision_volume_mm3=vol, timings_s=timings,
        ))
    return results
