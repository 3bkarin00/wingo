"""Pin-and-tube hinges — generated mode (D26/ADR-005, plan.md §8.8 — WP1).

Supersedes the lug/tang knuckle construction (backend/geometry/hinges.py,
retired). Per station on the true hinge axis (te_cut.py's hinge_frame):

  TUBES   — plain coaxial cylinders on the axis: wing tube inboard, CS tube
            outboard, HINGE_TUBE_SEGMENT_LEN_MM each, HINGE_AXIAL_GAP_MM
            between the mouths. Tube = outer cyl − id bore.
  CARRIERS— box blocks in the station's local frame (X̂ = axis dir,
            Ẑ = global Z projected ⊥ axis, Ŷ = Ẑ×X̂ oriented toward the
            false spar): each envelops its tube with HINGE_CARRIER_WALL_MM
            wall, bore Ø = tube OD + HINGE_CARRIER_BORE_FIT_MM. The WING
            carrier extends forward to the false spar, its mating face
            HINGE_CARRIER_BOND_GAP_MM off the false-spar aft face —
            explicit gap, bonded, never touching (F4-adjacent). The CS
            carrier extends aft HINGE_CS_CARRIER_EMBED_MM into CS nose
            material; a matched notch (its bounding box grown by the bond
            gap — the same provably-correct Minkowski-box idiom the
            retired lug keyway R0-verified) is cut from a DERIVED copy of
            cs_solid (the frozen P4 cs_solid is never modified).
  POCKETS — swept-envelope clearance cuts, built as UNION OF ROTATED
            COPIES at HINGE_POCKET_SWEEP_STEP_DEG steps through
            ±(max_deflection + overlap margin) about the true axis
            (cq.Shape.rotate — R0-verified accurate to 1.5e-14mm,
            docs/r0_findings/p07.md), never a single revolve. DELIBERATE
            DEVIATION from the recipe's "3D-offset the union by the swept
            clearance": the MOVING bodies are grown by
            HINGE_POCKET_SWEPT_CLEARANCE_MM BEFORE rotating (box dims and
            tube radius + clearance) — for these convex primitives that is
            the same Minkowski growth, and it avoids
            BRepOffsetAPI_MakeOffsetShape, an API this project has never
            probed, on a many-copy union (the fragile case). Recorded in
            changelog.md.
            - CS-side pocket: envelope of the grown WING carrier+tube
              rotated through the range → cut from the cs_solid copy.
            - Wing-side pocket: envelope of the grown CS carrier+tube →
              cut from a DERIVED copy of false_spar_solid (R0 fact: the
              wing body itself has no material near the axis; the false
              spar IS the wing-side structure there).
  ACCESS BORE — Ø(pin + HINGE_ACCESS_BORE_EXTRA_MM) along the axis from
            beyond the outboard end of the CS structure to the outermost
            tube mouth, cut from the cs_solid copy.
  SET SCREW — Ø HINGE_SET_SCREW_DIA_MM radial cylinder in each OUTBOARD
            (CS) carrier, along local Ẑ, axis intersecting the tube bore
            axis perpendicularly; cut only, no thread geometry.

FACE NAMING: each carrier's mating face is recorded in a shared
face_registry.FaceRegistry at creation and matched after all cuts on that
carrier — HINGE<n>_WING_CARRIER_BOND / HINGE<n>_CS_CARRIER_BOND.

Purely ADDITIVE relative to frozen phase outputs: cs_solid and
false_spar_solid enter as inputs and leave untouched; the pocketed/notched
variants are new derived bodies on the result.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_cut
from backend.geometry.cove_profile import analytic_section_points, find_station_feet
from backend.geometry.face_registry import FaceRegistry
from backend.geometry.sections import PlacedSection
from backend.geometry.te_cut import hinge_frame
from backend.schema.models import Config


@dataclass
class HingeStation:
    index: int
    s_center: float  # arc-length along the axis (te_cut.py's `s` convention)
    axis_point: np.ndarray  # 3D point at s_center
    wing_tube: cq.Shape
    cs_tube: cq.Shape
    wing_carrier: cq.Shape
    cs_carrier: cq.Shape


@dataclass
class PinTubeHingeSet:
    stations: list[HingeStation] = field(default_factory=list)
    axis_p0: np.ndarray | None = None
    axis_dir: np.ndarray | None = None
    pin_dia_mm: float = 0.0
    tube_od_mm: float = 0.0
    # Derived clearance-cut bodies (originals never modified):
    cs_pocketed: cq.Shape | None = None
    false_spar_pocketed: cq.Shape | None = None
    # Matched bond faces per carrier (face_registry) — name -> cq.Face.
    bond_faces: dict = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    timings_s: dict = field(default_factory=dict)


def _cyl(base_s: float, length: float, radius: float, p0: np.ndarray, h: np.ndarray) -> cq.Solid:
    return cq.Solid.makeCylinder(
        radius, length, cq.Vector(*(p0 + h * base_s)), cq.Vector(*h)
    )


def _frame_box(
    origin: np.ndarray, x_hat: np.ndarray, y_hat: np.ndarray, z_hat: np.ndarray,
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float,
) -> cq.Solid:
    """Box spanning [x0,x1]×[y0,y1]×[z0,z1] in the (x̂,ŷ,ẑ) frame at origin."""
    corner = origin + x_hat * x0 + y_hat * y0 + z_hat * z0
    plane = cq.Plane(origin=cq.Vector(*corner), xDir=cq.Vector(*x_hat), normal=cq.Vector(*z_hat))
    return (
        cq.Workplane(plane)
        .box(x1 - x0, y1 - y0, z1 - z0, centered=(False, False, False))
        .val()
    )


def _largest(shape: cq.Shape) -> cq.Shape | None:
    solids, _ = filter_shards(shape, min_volume=1e-6)
    return max(solids, key=lambda s: s.Volume()) if solids else None


def _rotated_union(
    body: cq.Shape, p0: np.ndarray, h: np.ndarray, sweep_deg: float
) -> cq.Shape:
    """Union of copies of `body` rotated about the axis (p0, p0+h) at
    HINGE_POCKET_SWEEP_STEP_DEG steps through ±sweep_deg (D26: never a
    single revolve). cq.Shape.rotate R0-verified (p07.md)."""
    a = cq.Vector(*p0)
    b = cq.Vector(*(p0 + h))
    step = tolerances.HINGE_POCKET_SWEEP_STEP_DEG
    angles = np.arange(-sweep_deg, sweep_deg + 1e-9, step)
    union: cq.Shape | None = None
    for ang in angles:
        copy = body.rotate(a, b, float(ang))
        union = copy if union is None else union.fuse(copy)
    return union


def build_pin_tube_hinges(
    config: Config,
    sections: list[PlacedSection],
    cs_solid: cq.Shape,
    false_spar_solid: cq.Shape,
) -> PinTubeHingeSet:
    """Module-docstring construction. Empty set when te_surface is
    disabled/absent or hinges.mode != "generated" (COTS mode deferred,
    same posture as the retired module)."""
    te = config.te_surface
    if te is None or not te.enabled or te.hinges.mode != "generated":
        return PinTubeHingeSet()

    t_start = time.perf_counter()
    p0, _p1, h, a, u, axis_len = hinge_frame(config)
    count = te.hinges.count
    sweep_deg = te.max_deflection_deg + (
        te.overlap_margin_deg if te.overlap_margin_deg is not None
        else tolerances.OVERLAP_MARGIN_DEG
    )

    tube_id = tolerances.HINGE_PIN_DIA_MM + tolerances.HINGE_TUBE_ID_CLEARANCE_MM
    tube_od = tube_id + 2.0 * tolerances.HINGE_TUBE_WALL_MM
    seg_len = tolerances.HINGE_TUBE_SEGMENT_LEN_MM
    axial_gap = tolerances.HINGE_AXIAL_GAP_MM
    wall = tolerances.HINGE_CARRIER_WALL_MM
    bore_r = (tube_od + tolerances.HINGE_CARRIER_BORE_FIT_MM) / 2.0
    bond_gap = tolerances.HINGE_CARRIER_BOND_GAP_MM
    grow = tolerances.HINGE_POCKET_SWEPT_CLEARANCE_MM
    half_h = tube_od / 2.0 + wall  # carrier half-height (Ẑ) and aft half-depth (Ŷ)

    # Stations: inset from both axis ends by one carrier axial length
    # (recipe: ">= one carrier length"), then evenly distributed.
    carrier_axial = seg_len  # carrier length along the axis = its tube's segment
    inset = carrier_axial + axial_gap / 2.0 + seg_len  # full station half-extent
    usable = axis_len - 2.0 * inset
    if usable <= 0:
        return PinTubeHingeSet(failed=[f"axis too short for {count} stations (axis_len={axis_len:.1f})"])
    centers = inset + (np.arange(count) + 0.5) / count * usable

    result = PinTubeHingeSet(
        axis_p0=p0, axis_dir=h, pin_dia_mm=tolerances.HINGE_PIN_DIA_MM, tube_od_mm=tube_od,
    )
    registry = FaceRegistry()
    cs_derived: cq.Shape = cs_solid
    fs_derived: cq.Shape = false_spar_solid
    timings = result.timings_s

    # Global Z projected perpendicular to the axis (recipe's local frame).
    z_hat = np.array([0.0, 0.0, 1.0]) - np.dot([0.0, 0.0, 1.0], h) * h
    z_hat = z_hat / np.linalg.norm(z_hat)
    y_hat = np.cross(z_hat, h)
    y_hat = y_hat / np.linalg.norm(y_hat)
    # Orient Ŷ toward the false spar (forward): the false spar sits in the
    # -a direction from the axis (false_spar.py / retired hinges.py).
    if np.dot(y_hat, -a) < 0:
        y_hat, z_hat = -y_hat, z_hat  # flip Ŷ only; frame handedness not load-bearing here

    t0 = time.perf_counter()
    moving_cs_envelopes: list[cq.Shape] = []   # grown CS carrier+tube (cut wing side)
    moving_wing_envelopes: list[cq.Shape] = []  # grown wing carrier+tube (cut CS side)
    for i, s_center in enumerate(centers):
        # Tube axial spans: wing inboard of center, CS outboard.
        wing_s0 = s_center - axial_gap / 2.0 - seg_len
        cs_s0 = s_center + axial_gap / 2.0
        C = p0 + h * s_center

        def tube(base_s: float) -> cq.Shape:
            outer = _cyl(base_s, seg_len, tube_od / 2.0, p0, h)
            inner = _cyl(base_s - seg_len, 3 * seg_len, tube_id / 2.0, p0, h)
            return fuzzy_cut(outer, inner)

        wing_tube = tube(wing_s0)
        cs_tube = tube(cs_s0)

        # Wing carrier: from the tube envelope aft face forward to
        # (false-spar aft face − bond gap). The nominal reach estimate
        # (R + COVE_CLEARANCE + FALSE_SPAR_COVE_STANDOFF, false_spar.py's
        # own placement formula) is then CORRECTED BY MEASUREMENT — build
        # the nominal blank, measure its true distance to the real false
        # spar (BRepExtrema), and rebuild with the residual folded in, so
        # gap == bond_gap on the actual body, not on a formula (the first
        # real-kernel run measured a systematic ~2.5mm undershoot on
        # te_half; "verified, not assumed", same posture as ribs.py).
        C_wing = p0 + h * (wing_s0 + seg_len / 2.0)
        feet = find_station_feet(analytic_section_points(sections, C_wing, h), C_wing, a, u)
        reach_fs = (
            feet.R + tolerances.COVE_CLEARANCE_MM + tolerances.FALSE_SPAR_COVE_STANDOFF_MM
            - bond_gap
        )

        def _wing_blank(reach: float) -> cq.Solid:
            return _frame_box(
                C_wing, h, y_hat, z_hat,
                -seg_len / 2.0, seg_len / 2.0,
                -half_h, reach,
                -half_h, half_h,
            )

        from OCP.BRepExtrema import BRepExtrema_DistShapeShape

        # The false-spar surface isn't flat/perpendicular to Ŷ at this
        # point, so growing the box by exactly the measured residual
        # doesn't land on target in one shot (first real-kernel run: 2.6mm
        # error corrected to only ~0.3mm by a single correction) — iterate
        # the measure/correct step to convergence instead (fixed-point,
        # not linear; a handful of iterations is enough since each step
        # shrinks the residual).
        wing_carrier_blank = _wing_blank(reach_fs)
        for _ in range(8):
            d_op = BRepExtrema_DistShapeShape(wing_carrier_blank.wrapped, false_spar_solid.wrapped)
            d_op.Perform()
            if not d_op.IsDone():
                break
            residual = d_op.Value() - bond_gap
            if abs(residual) <= tolerances.KERNEL_TOLERANCE_MM:
                break
            reach_fs += residual
            wing_carrier_blank = _wing_blank(reach_fs)
        # Record the mating face (max-Ŷ face) BEFORE the bore cut.
        mating = max(
            wing_carrier_blank.Faces(),
            key=lambda f: float(np.dot(np.array(f.Center().toTuple()) - C_wing, y_hat)),
        )
        registry.record_face(f"HINGE{i}_WING_CARRIER_BOND", mating)
        bore = _cyl(wing_s0 - seg_len, 3 * seg_len, bore_r, p0, h)
        wing_carrier = _largest(fuzzy_cut(wing_carrier_blank, bore))

        # CS carrier: from the tube envelope forward face aft into CS nose
        # material by HINGE_CS_CARRIER_EMBED_MM.
        C_cs = p0 + h * (cs_s0 + seg_len / 2.0)
        cs_reach = half_h + tolerances.HINGE_CS_CARRIER_EMBED_MM
        cs_carrier_blank = _frame_box(
            C_cs, h, y_hat, z_hat,
            -seg_len / 2.0, seg_len / 2.0,
            -cs_reach, half_h,
            -half_h, half_h,
        )
        mating_cs = min(
            cs_carrier_blank.Faces(),
            key=lambda f: float(np.dot(np.array(f.Center().toTuple()) - C_cs, y_hat)),
        )
        registry.record_face(f"HINGE{i}_CS_CARRIER_BOND", mating_cs)
        bore_cs = _cyl(cs_s0 - seg_len, 3 * seg_len, bore_r, p0, h)
        cs_carrier = fuzzy_cut(cs_carrier_blank, bore_cs)
        # Set screw: radial Ẑ cylinder intersecting the tube axis, in the
        # OUTBOARD (CS) carrier only.
        screw = cq.Solid.makeCylinder(
            tolerances.HINGE_SET_SCREW_DIA_MM / 2.0, 3 * half_h,
            cq.Vector(*C_cs), cq.Vector(*z_hat),
        )
        cs_carrier = _largest(fuzzy_cut(cs_carrier, screw))

        if wing_carrier is None or cs_carrier is None:
            result.failed.append(f"station{i}@s={s_center:.1f}: carrier construction")
            continue

        # CS nose notch for the CS carrier: bounding box grown by the bond
        # gap (Minkowski-box guarantee, retired-lug-keyway R0 precedent).
        bb = cs_carrier_blank.BoundingBox()
        notch = cq.Solid.makeBox(
            bb.xlen + 2 * bond_gap, bb.ylen + 2 * bond_gap, bb.zlen + 2 * bond_gap,
            cq.Vector(bb.xmin - bond_gap, bb.ymin - bond_gap, bb.zmin - bond_gap),
        )
        cs_derived = fuzzy_cut(cs_derived, notch)

        # Grown moving envelopes for the swept pockets (module docstring's
        # grow-before-rotate deviation).
        grown_cs = _frame_box(
            C_cs, h, y_hat, z_hat,
            -seg_len / 2.0 - grow, seg_len / 2.0 + grow,
            -cs_reach - grow, half_h + grow,
            -half_h - grow, half_h + grow,
        ).fuse(_cyl(cs_s0 - grow, seg_len + 2 * grow, tube_od / 2.0 + grow, p0, h))
        moving_cs_envelopes.append(grown_cs)
        grown_wing = _frame_box(
            C_wing, h, y_hat, z_hat,
            -seg_len / 2.0 - grow, seg_len / 2.0 + grow,
            -half_h - grow, reach_fs + grow,
            -half_h - grow, half_h + grow,
        ).fuse(_cyl(wing_s0 - grow, seg_len + 2 * grow, tube_od / 2.0 + grow, p0, h))
        moving_wing_envelopes.append(grown_wing)

        result.stations.append(HingeStation(
            index=i, s_center=float(s_center), axis_point=C,
            wing_tube=wing_tube, cs_tube=cs_tube,
            wing_carrier=wing_carrier, cs_carrier=cs_carrier,
        ))
    timings["stations_s"] = time.perf_counter() - t0

    # Swept pockets (the expensive booleans of WP1 — per-step timing logged).
    t0 = time.perf_counter()
    for env in moving_wing_envelopes:
        swept = _rotated_union(env, p0, h, sweep_deg)
        cs_derived = fuzzy_cut(cs_derived, swept)
    timings["cs_pockets_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    for env in moving_cs_envelopes:
        swept = _rotated_union(env, p0, h, sweep_deg)
        fs_derived = fuzzy_cut(fs_derived, swept)
    timings["false_spar_pockets_s"] = time.perf_counter() - t0

    # Access bore: from beyond the outboard axis end to the outermost tube
    # mouth (the outermost CS tube's outboard face).
    t0 = time.perf_counter()
    if result.stations:
        outer_mouth_s = max(st.s_center for st in result.stations) + axial_gap / 2.0 + seg_len
        bore_len = (axis_len - outer_mouth_s) + 2.0 * seg_len  # overshoots the structure end
        access = _cyl(
            outer_mouth_s, bore_len,
            (tolerances.HINGE_PIN_DIA_MM + tolerances.HINGE_ACCESS_BORE_EXTRA_MM) / 2.0,
            p0, h,
        )
        cs_derived = fuzzy_cut(cs_derived, access)
    timings["access_bore_s"] = time.perf_counter() - t0

    result.cs_pocketed = _largest(cs_derived)
    fs_kept, _ = filter_shards(fs_derived)
    result.false_spar_pocketed = fs_derived if fs_kept else None
    if result.cs_pocketed is None:
        result.failed.append("cs_pocketed:no_solid")
    if result.false_spar_pocketed is None:
        result.failed.append("false_spar_pocketed:no_solid")

    # Match bond faces on the FINISHED carriers (hard failure inside match
    # if a cut ate one).
    t0 = time.perf_counter()
    for st in result.stations:
        for body in (st.wing_carrier, st.cs_carrier):
            partial = FaceRegistry(entries=[
                e for e in registry.entries
                if e.name.startswith(f"HINGE{st.index}_")
                and (("WING" in e.name) == (body is st.wing_carrier))
            ])
            result.bond_faces.update(partial.match(body))
    timings["face_match_s"] = time.perf_counter() - t0

    timings["total_s"] = time.perf_counter() - t_start
    return result
