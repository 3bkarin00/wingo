"""Sandwich-skin IML construction (plan.md §8.7), CLEAN-SPAN ONLY.

IML by **2D per-station offset + second loft + subtract** — never OCC
shell/thicken (F1). R0-probed before any of this was written
(docs/r0_findings/p06.md, scripts/r0_probes/probe_ocp_offset.py and
probe_ocp_offset_3layer.py): `cq.Wire.offset2D(-distance, kind="intersection")`
is the real, confirmed-working API, and a single whole-loop offset by `d`
shrinks local (upper-to-lower) thickness by `2d` — both walls move inward
simultaneously.

THE PANEL IS THREE LAYERS PER WALL — outer face sheet / core / inner face
sheet. (The first implementation delivered only an outer face and a
half-thickness core: it chose its offsets to make the TOTAL two-wall
consumption equal the P0 `stack_mm` formula, which silently deleted the inner
face sheet. Caught by product review.) The correct chain is full-value:

    face_IML   = OML_wire.offset2D(-face_mm)      # outer face sheet, wall = face_mm
    core_IML   = face_IML.offset2D(-core_mm)      # core, wall = core_mm
    hollow_IML = core_IML.offset2D(-face_mm)      # inner face sheet, wall = face_mm

Per-wall consumption = face+core+face = `stack_mm`, exactly the FROZEN P0
per-wall formula (`backend/schema/validators.py`); TOTAL local thickness
consumed is `2*stack_mm`. Where a section is locally thinner than
`2*stack_mm` (aft of ~x/c=0.9 at the tip on several frozen configs) the
innermost offsets SELF-CLIP (`kind="intersection"`): the hollow locally
vanishes and the walls merge into solid laminate — R0-verified to still
produce one valid closed wire per station, valid lofts, shard-free rings and
exact volume conservation (probe_ocp_offset_3layer.py). That aft wall-merge
is a documented consequence of the corrected panel, to be revisited with
ramped drop-offs (D11) and the P6 gate's IML audit.

EVERY layer is restricted to the actual body: the outer face sheet =
body − face_IML (body-derived by construction), core and inner face sheet get
an explicit ∩ body — the raw loft-algebra bands know nothing about device
cuts and would otherwise sail uncut through a control-surface pocket (a real
defect caught visually in the dev viewer the first time the core band was
rendered without it).

UPPER/LOWER SPLIT: molded-composite reality is an upper and a lower mold
half; every layer is therefore delivered as separate upper/lower shells
(and later, separate upper/lower midsurfaces for the Ansys route). The split
uses a "below-camber" prism: per station, the camber polyline — exact by
midpointing paired placed points, since resample.py guarantees upper/lower
share one cosine x-grid with a shared LE and placement is affine — is
extended slightly beyond LE and TE, closed downward well below the section,
and the closed polygons are lofted (ruled, same convention as everything
else). `lower = ring ∩ prism`, `upper = ring − prism`. The prism's camber
surface crosses skin material only near LE/TE and transversally there — no
tangent-face pairs (F4). This is a PROVISIONAL parting definition: the real
mold parting curve (max half-breadth per station) arrives with P15/P16 mold
machinery and supersedes the camber-based split for tooling purposes.

COVE-ARC FIDELITY (wing body only — see remaining scope limit below): the
per-station offsets are still built by 2D-offsetting the ORIGINAL uncut
airfoil sections (unchanged, above). Near an enabled te_surface's device
window the wing's ACTUAL outer boundary there is the cove arc
(backend/geometry/cove_profile.py, cut into `wing` by te_cut.py's
`cove_region`), not the plain airfoil skin — so a raw offset of the uncut
airfoil is either missing entirely or an uncontrolled sliver right where the
cove lip needs a real face_mm/core_mm/face_mm stack (worked through in
detail in docs/r0_findings/p06.md, "Addendum: cove-arc IML fidelity").
`build_sandwich_lofts` fixes this the same way te_cut.py separates OML
construction from the cove cut: it lofts the SAME per-station offset chain
over the full uncut sections as before, then (only when te_surface is
enabled) SUBTRACTS a cove-following wedge from each of the three lofts —
`te_cut.build_cove_offset_region(config, sections, extra_radius_mm=d)`,
the exact same station/arc construction `cove_region` itself uses, just
grown concentrically by `d` (=face_mm, face_mm+core_mm, stack_mm for the
face/core/hollow lofts respectively). Because it's a concentric-arc offset
(not a 2D polygon `offset2D`), there is no self-clip/self-intersection risk
this introduces — `fuzzy_cut` against `body` downstream clips it to whatever
material actually exists, same as the plain clean-span case.

REMAINING SCOPE LIMIT (tracked, not silent): this fixes the WING body only.
The control surface's own nose is bounded by a CONVEX arc at radius R (not
R+COVE_CLEARANCE_MM going outward — the CS nose sits INSIDE that radius), a
mirror-image construction this function does not yet build; CS sandwich
shells are not wired into any export/gate path yet (scripts/export_viewer_data.py
still says so explicitly), so this is deferred, not forgotten.

RAMPED DROP-OFFS (D11, `config.skin.ramp_ratio`): plan.md §8.7 lists 4 ramp
locations — edges, hinge lands, joints, every hardpoint. Only "edges" (the
wingtip) is buildable right now; the other 3 need geometry this tool doesn't
have yet (hinge attachment points arrive with P7, joints with P11, hardware
pockets with P8) — deferred, not silent, same pattern as the CS-nose limit
above. `build_sandwich_lofts` makes `core_mm` a PER-STATION value via
`_ramped_core_mm`: nominal everywhere except within `ramp_ratio*core_mm` of
the tip station, where it tapers linearly to (near) zero — `face_mm` is
UNCHANGED, so the panel becomes solid laminate (face+face, no core) right at
the tip, exactly D11's wording. The root (y=0) is the mirror-continuous
centerline in current half-span R1 scope, not a free edge — not ramped.

A per-station core_mm value alone is NOT sufficient: `cq.Solid.makeLoft(...,
ruled=True)` linearly blends the 2D offset WIRE between consecutive input
stations, so if the nearest declared planform station outboard of the ramp
zone is farther than `ramp_ratio*core_mm` from the tip (the common case —
e.g. a config with only root+tip stations, span in the hundreds of mm, ramp
zone a few mm), the loft smears the taper across that ENTIRE gap instead of
confining it near the tip (caught empirically: a first attempt using the
UNMODIFIED planform station list dropped core_ring volume ~43% on
tests/configs/devices/te_half.yaml, an order of magnitude more than a
tip-only ramp should ever remove — see docs/r0_findings/p06.md).
`_insert_ramp_station` fixes this by inserting one extra station AT the
ramp boundary (y_tip − ramp_len_mm) into a LOCAL COPY of the section list
used for this module's offset/loft AND parting-prism construction — built
via the SAME `interp_station`+`place_section` pipeline
`build_planform_sections` itself uses, so it's geometrically identical to
what a declared station there would have produced. The parting prism MUST
use this same expanded list, not the original: a first attempt kept
`parting_solid` on the original (unexpanded) `sections` while
`face_inner_shell` etc. used the ramp-expanded lofts, and that topology
MISMATCH between the shape being cut and the cutting tool broke
`BRepAlgoAPI_Cut` outright on `tests/configs/edge/high_taper.yaml`'s
extreme 10:1-taper + single-ply-face + thin-core combination — every loft
that gets boolean'd against another must share the same per-station Y
sampling (see docs/r0_findings/p06.md). The OML loft (built earlier, in
loft.py, from the original `sections`) is the one exception — the OML is
untouched by ramping and stays on its original station set.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import fuzzy_common, fuzzy_cut
from backend.geometry.loft import build_section_wire
from backend.geometry.sections import (
    PlacedSection,
    interp_station,
    le_and_z_offset,
    place_section,
    unit_chord_area,
)
from backend.geometry.te_cut import build_cove_offset_region
from backend.schema.models import Config

# Camber-line extension past LE/TE (fraction of local chord) so the parting
# prism fully crosses the skin's LE curve and blunt-TE closing wall instead
# of ending exactly on them (an on-surface endpoint would be an F4-style
# coincidence hazard). Geometric construction parameter, not a physical
# tolerance — lives here like te_cut.py's N_STATIONS, per that precedent.
PARTING_EXTENSION_CHORD_FRAC = 0.05
# How far below the section the parting prism's floor sits (fraction of local
# chord). Anything comfortably below the lowest skin point works; 0.5 chord
# is unambiguous at any twist this tool accepts.
PARTING_FLOOR_DROP_CHORD_FRAC = 0.5


@dataclass
class SandwichLofts:
    # cq.Shape not cq.Solid: when an enabled te_surface triggers the
    # cove-fidelity cut (module docstring), these three are fuzzy_cut
    # results, which may be compounds.
    face_iml_solid: cq.Shape    # inner boundary of the OUTER face sheet
    core_iml_solid: cq.Shape    # inner boundary of the core
    hollow_iml_solid: cq.Shape  # inner boundary of the INNER face sheet = cavity
    parting_solid: cq.Solid     # below-camber prism, shared by every body's split
    timings_s: dict = field(default_factory=dict)


@dataclass
class SandwichBody:
    """Per-body sandwich layers, three per wall (outer face / core / inner
    face). The three full rings are kept so a gate can assert each
    upper/lower pair exactly partitions its ring; the six upper/lower shapes
    are the actual deliverable (one skin per mold half, plan.md §8.9 / D5)."""

    face_outer_shell: cq.Shape
    core_shell: cq.Shape
    face_inner_shell: cq.Shape
    face_outer_upper: cq.Shape
    face_outer_lower: cq.Shape
    core_upper: cq.Shape
    core_lower: cq.Shape
    face_inner_upper: cq.Shape
    face_inner_lower: cq.Shape
    hollow_interior: cq.Shape | None  # None when skipped (include_hollow_interior=False)
    timings_s: dict = field(default_factory=dict)


def offset_wire(wire: cq.Wire, distance_mm: float) -> cq.Wire:
    result = wire.offset2D(-distance_mm, kind="intersection")
    return result[0] if isinstance(result, list) else result


def _ramped_core_mm(y_mm: float, nominal_core_mm: float, ramp_ratio: float, y_tip_mm: float) -> float:
    """D11: taper core thickness to (near) zero within `ramp_ratio*nominal_core_mm`
    of the wingtip station, so the sandwich panel becomes solid laminate
    (face+face, no core — `face_mm` is untouched by this) at a free edge
    instead of terminating in an exposed foam core. Linear ramp; floored at
    `tolerances.RAMP_MIN_CORE_MM` — NOT just to dodge a literal
    zero-distance offset2D call, but because a first attempt at 0.01mm
    (== KERNEL_TOLERANCE_MM exactly) broke real-kernel booleans on
    tests/configs/edge/high_taper.yaml (see that constant's derivation
    comment and docs/r0_findings/p06.md). Root (y=0) is not ramped — see
    module docstring."""
    ramp_len_mm = ramp_ratio * nominal_core_mm
    dist_to_tip_mm = y_tip_mm - y_mm
    if dist_to_tip_mm >= ramp_len_mm:
        return nominal_core_mm
    frac = max(0.0, dist_to_tip_mm / ramp_len_mm)
    return max(tolerances.RAMP_MIN_CORE_MM, nominal_core_mm * frac)


def _insert_ramp_station(
    config: Config, sections: list[PlacedSection], ramp_len_mm: float
) -> list[PlacedSection]:
    """Insert one extra station AT the ramp boundary (y_tip − ramp_len_mm) so
    the ruled loft's per-station core_mm blend is confined to the ramp zone
    instead of smearing across the gap to the nearest declared planform
    station (module docstring — this is the fix for the ~43% core_ring
    volume defect that construction produced before this function existed).
    Built via the same interp_station+place_section pipeline
    build_planform_sections uses, so it's geometrically identical to what a
    declared station there would produce. Returns a NEW list; `sections`
    itself is untouched (the OML, built earlier from the original list, is
    unaffected by ramping — but the parting prism DOES need this expanded
    list too, see module docstring)."""
    ordered = sorted(sections, key=lambda s: s.y_mm)
    y_tip_mm = ordered[-1].y_mm
    y_ramp_mm = y_tip_mm - ramp_len_mm
    # Skip if the ramp boundary coincides with an existing station (avoids a
    # near-zero-length loft segment) or falls at/before the first station
    # (ramp_len_mm >= full span — not this project's expected regime).
    if y_ramp_mm <= ordered[0].y_mm or any(abs(s.y_mm - y_ramp_mm) < 1.0 for s in ordered):
        return ordered

    half_span_mm = y_tip_mm
    y_frac = y_ramp_mm / half_span_mm
    resample_points = config.airfoils.resample_points
    chord, twist, pts = interp_station(config, y_frac, resample_points, config.airfoils.te_min_thickness_mm)
    le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
    placed = place_section(
        pts, chord, twist, config.planform.twist_axis_xc,
        y_mm=y_ramp_mm, le_x_mm=le_x, z_base_mm=z_base,
    )
    new_sec = PlacedSection(y_ramp_mm, y_frac, chord, twist, placed, unit_chord_area(pts))

    result = list(ordered)
    idx = next(i for i, s in enumerate(result) if s.y_mm > y_ramp_mm)
    result.insert(idx, new_sec)
    return result


def face_sheet_thickness_mm(config: Config) -> float:
    """Face-sheet stack thickness (mm) — same provisional ply-thickness
    lookup already used inline by backend/schema/validators.py and
    tests/gates/test_p03_reference.py (not promoted to a shared helper
    there; matched here for the same reason: a materials DB supersedes all
    three call sites at once in P1+/D17, so there's nothing durable to
    abstract yet)."""
    ply_thickness = tolerances.PLY_THICKNESS_MM_PROVISIONAL[config.skin.face_sheet.material]
    return config.skin.face_sheet.plies * ply_thickness


def _camber_polyline(points: np.ndarray) -> np.ndarray:
    """Exact camber polyline (TE→LE, world coords) of one placed section.
    Canonical order is TE→upper→LE→lower→TE with both surfaces on the SAME
    cosine x-grid sharing the LE point (resample.py's documented contract),
    so pts[i] (upper) and pts[N-1-i] (lower) sit at identical chordwise
    position and their midpoint IS the camber point — placement (scale/
    twist/translate) is affine per-point, so midpoints commute with it."""
    mid = (len(points) - 1) // 2
    return (points[: mid + 1] + points[::-1][: mid + 1]) / 2.0


def _parting_polygon(sec: PlacedSection) -> np.ndarray:
    """Closed planar polygon (constant-Y station plane) bounding the region
    BELOW the camber line: extended camber TE→LE on top, a flat floor well
    below the section, vertical-ish sides at the extended endpoints."""
    camber = _camber_polyline(sec.points)
    ext = PARTING_EXTENSION_CHORD_FRAC * sec.chord_mm

    te_dir = camber[0] - camber[1]
    te_dir = te_dir / np.linalg.norm(te_dir)
    le_dir = camber[-1] - camber[-2]
    le_dir = le_dir / np.linalg.norm(le_dir)
    p_te = camber[0] + te_dir * ext
    p_le = camber[-1] + le_dir * ext

    z_floor = float(sec.points[:, 2].min()) - PARTING_FLOOR_DROP_CHORD_FRAC * sec.chord_mm
    y = float(sec.points[0, 1])
    floor_le = np.array([p_le[0], y, z_floor])
    floor_te = np.array([p_te[0], y, z_floor])

    return np.vstack([p_te[None, :], camber, p_le[None, :], floor_le[None, :], floor_te[None, :]])


def build_sandwich_lofts(config: Config, sections: list[PlacedSection]) -> SandwichLofts:
    """Per-station chained full-value offset (face_mm, core_mm, face_mm — see
    module docstring) + ruled loft, over the FULL section list exactly as the
    OML itself is lofted (loft.py's build_section_wire, same per-station
    points), plus the below-camber parting prism for the upper/lower split.
    `core_mm` is per-station (D11 ramped drop-off at the tip — module
    docstring, `_ramped_core_mm`); `face_mm` is constant. When
    `config.te_surface` is enabled, each loft is then cove-fidelity-corrected
    for the wing body (module docstring) — that wedge is sized off the
    NOMINAL core_mm, not the ramped value, so a device window whose outboard
    edge falls inside the tip's ramp zone is an untested interaction (both
    are edge-case corrections; not expected to overlap on any current config,
    not yet verified if it does)."""
    face_mm = face_sheet_thickness_mm(config)
    core_mm = config.skin.core.thickness_mm
    ramp_ratio = config.skin.ramp_ratio
    ramp_len_mm = ramp_ratio * core_mm
    ramp_sections = _insert_ramp_station(config, sections, ramp_len_mm)
    y_tip_mm = ramp_sections[-1].y_mm
    timings: dict = {}

    t0 = time.perf_counter()
    face_wires, core_wires, hollow_wires = [], [], []
    for sec in ramp_sections:
        outer_wire = build_section_wire(sec.points)
        local_core_mm = _ramped_core_mm(sec.y_mm, core_mm, ramp_ratio, y_tip_mm)
        face_wire = offset_wire(outer_wire, face_mm)
        core_wire = offset_wire(face_wire, local_core_mm)
        hollow_wire = offset_wire(core_wire, face_mm)
        face_wires.append(face_wire)
        core_wires.append(core_wire)
        hollow_wires.append(hollow_wire)
    timings["offset_wires_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_iml_solid = cq.Solid.makeLoft(face_wires, ruled=True)
    core_iml_solid = cq.Solid.makeLoft(core_wires, ruled=True)
    hollow_iml_solid = cq.Solid.makeLoft(hollow_wires, ruled=True)
    timings["lofts_s"] = time.perf_counter() - t0

    te = config.te_surface
    if te is not None and te.enabled:
        t0 = time.perf_counter()
        cove_face = build_cove_offset_region(config, sections, face_mm)
        cove_core = build_cove_offset_region(config, sections, face_mm + core_mm)
        cove_hollow = build_cove_offset_region(config, sections, face_mm + core_mm + face_mm)
        face_iml_solid = fuzzy_cut(face_iml_solid, cove_face)
        core_iml_solid = fuzzy_cut(core_iml_solid, cove_core)
        hollow_iml_solid = fuzzy_cut(hollow_iml_solid, cove_hollow)
        timings["cove_fidelity_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    # ramp_sections, not sections: parting_solid gets cut against face/core/
    # hollow downstream (build_sandwich_body) — if it's lofted from a
    # DIFFERENT per-station Y-sampling than they are, that topology mismatch
    # broke BRepAlgoAPI_Cut outright on tests/configs/edge/high_taper.yaml's
    # extreme taper+thin-layer combination (docs/r0_findings/p06.md);
    # keeping every loft on the same station set fixed it.
    parting_wires = [build_section_wire(_parting_polygon(sec)) for sec in ramp_sections]
    parting_solid = cq.Solid.makeLoft(parting_wires, ruled=True)
    timings["parting_solid_s"] = time.perf_counter() - t0

    return SandwichLofts(
        face_iml_solid=face_iml_solid,
        core_iml_solid=core_iml_solid,
        hollow_iml_solid=hollow_iml_solid,
        parting_solid=parting_solid,
        timings_s=timings,
    )


def build_sandwich_body(
    body: cq.Shape, lofts: SandwichLofts, include_hollow_interior: bool = True
) -> SandwichBody:
    """Cuts the per-station lofts (built over the FULL original span) against
    the ACTUAL device-cut body, then splits each of the three rings into
    upper/lower shells with the parting prism. Safe to call on either `wing`
    or `control_surface` from a P4 TeCutResult, PROVIDED the region of
    interest is away from the device's spanwise window (module docstring).

    `include_hollow_interior=False` skips the body ∩ hollow_IML boolean —
    measured among the most expensive operations in this module (~370-670s
    per boolean of this size on the workspace; see docs/known_issues.md) —
    for callers that only need the shells (e.g. the dev viewer export). The
    P6 pipeline itself always needs it (ribs/spars are built inside it), so
    it defaults to True."""
    timings: dict = {}

    t0 = time.perf_counter()
    face_outer_shell = fuzzy_cut(body, lofts.face_iml_solid)
    timings["face_outer_cut_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_band = fuzzy_cut(lofts.face_iml_solid, lofts.core_iml_solid)
    core_shell = fuzzy_common(core_band, body)
    timings["core_ring_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_inner_band = fuzzy_cut(lofts.core_iml_solid, lofts.hollow_iml_solid)
    face_inner_shell = fuzzy_common(face_inner_band, body)
    timings["face_inner_ring_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_outer_lower = fuzzy_common(face_outer_shell, lofts.parting_solid)
    face_outer_upper = fuzzy_cut(face_outer_shell, lofts.parting_solid)
    timings["face_outer_split_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_lower = fuzzy_common(core_shell, lofts.parting_solid)
    core_upper = fuzzy_cut(core_shell, lofts.parting_solid)
    timings["core_split_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_inner_lower = fuzzy_common(face_inner_shell, lofts.parting_solid)
    face_inner_upper = fuzzy_cut(face_inner_shell, lofts.parting_solid)
    timings["face_inner_split_s"] = time.perf_counter() - t0

    hollow_interior = None
    if include_hollow_interior:
        t0 = time.perf_counter()
        hollow_interior = fuzzy_common(body, lofts.hollow_iml_solid)
        timings["hollow_common_s"] = time.perf_counter() - t0

    return SandwichBody(
        face_outer_shell=face_outer_shell,
        core_shell=core_shell,
        face_inner_shell=face_inner_shell,
        face_outer_upper=face_outer_upper,
        face_outer_lower=face_outer_lower,
        core_upper=core_upper,
        core_lower=core_lower,
        face_inner_upper=face_inner_upper,
        face_inner_lower=face_inner_lower,
        hollow_interior=hollow_interior,
        timings_s=timings,
    )
