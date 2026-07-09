"""Sandwich-skin IML construction (plan.md §8.7), CLEAN-SPAN ONLY.

IML by **2D per-station offset + second loft + subtract** — never OCC
shell/thicken (F1). R0-probed before any of this was written
(docs/r0_findings/p06.md, scripts/r0_probes/probe_ocp_offset.py):
`cq.Wire.offset2D(-distance, kind="intersection")` is the real,
confirmed-working API.

The critical fact that R0 established: a SINGLE whole-loop offset by distance
`d` shrinks local (upper-to-lower) wall thickness by `2d`, not `d` — both
walls move inward simultaneously in one pass. `backend/schema/validators.py`'s
FROZEN P0 check compares `stack_mm = core.thickness_mm + 2*face_sheet_mm`
(ONE core factor) against local thickness, so the ONLY offset sequence whose
total consumption exactly equals `stack_mm` — and is therefore safe for every
config P0 already accepts, with no change to tolerances.py — is:

    face_sheet_IML = OML_wire.offset2D(-face_mm)         # consumes 2*face_mm
    hollow_IML     = face_sheet_IML.offset2D(-core_mm/2)  # consumes 2*(core_mm/2) = core_mm
    # total = 2*face_mm + core_mm == stack_mm, exactly

Verified both analytically and empirically against te_half_twisted_moderate.yaml's
real (tightest-margin, frozen-gate) numbers in the R0 probe.

EVERY layer is restricted to the actual body: face sheet = body − face_IML
(body-derived by construction), core = (face_IML − hollow_IML) ∩ body — the
explicit ∩ body exists because the raw face_IML/hollow_IML band knows nothing
about device cuts and would otherwise sail uncut through a control-surface
pocket (a real defect caught visually in the dev viewer the first time the
band was rendered without it).

UPPER/LOWER SPLIT: molded-composite reality is an upper and a lower mold
half; the skin layers are therefore delivered as separate upper/lower shells
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

DELIBERATE SCOPE LIMIT (tracked, not silent): the per-station offsets use the
ORIGINAL airfoil sections. Near a TE device window the wing/CS's ACTUAL outer
boundary is the cove/nose arc (backend/geometry/cove_profile.py), not the
plain airfoil skin, so the sandwich layers in that spanwise band treat the
cove lip as if the uncut airfoil were still present. Nose/cove-arc-based
sandwich fidelity and the false-spar closing wall at the cut face are an
explicit follow-on, not implemented here. Trust `build_sandwich_body`'s
output only away from an enabled device's spanwise window.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import fuzzy_common, fuzzy_cut
from backend.geometry.loft import build_section_wire
from backend.geometry.sections import PlacedSection
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
    face_sheet_iml_solid: cq.Solid
    hollow_iml_solid: cq.Solid
    parting_solid: cq.Solid  # below-camber prism, shared by every body's split
    timings_s: dict = field(default_factory=dict)


@dataclass
class SandwichBody:
    """Per-body sandwich layers. face_sheet_shell/core_shell are the full
    body-restricted rings (kept so a gate can assert the upper/lower pair
    exactly partitions each ring); the four upper/lower shapes are the actual
    deliverable (one skin per mold half, plan.md §8.9 / D5)."""

    face_sheet_shell: cq.Shape
    core_shell: cq.Shape
    face_sheet_upper: cq.Shape
    face_sheet_lower: cq.Shape
    core_upper: cq.Shape
    core_lower: cq.Shape
    hollow_interior: cq.Shape | None  # None when skipped (include_hollow_interior=False)
    timings_s: dict = field(default_factory=dict)


def _offset_wire(wire: cq.Wire, distance_mm: float) -> cq.Wire:
    result = wire.offset2D(-distance_mm, kind="intersection")
    return result[0] if isinstance(result, list) else result


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
    """Per-station chained offset (face_mm, then core_mm/2 — see module
    docstring) + ruled loft, over the FULL section list exactly as the OML
    itself is lofted (loft.py's build_section_wire, same per-station points),
    plus the below-camber parting prism for the upper/lower split — clean-span
    construction, see module docstring for the device-region limitation."""
    face_mm = face_sheet_thickness_mm(config)
    core_mm = config.skin.core.thickness_mm
    timings: dict = {}

    t0 = time.perf_counter()
    face_sheet_wires, hollow_wires = [], []
    for sec in sections:
        outer_wire = build_section_wire(sec.points)
        face_wire = _offset_wire(outer_wire, face_mm)
        hollow_wire = _offset_wire(face_wire, core_mm / 2.0)
        face_sheet_wires.append(face_wire)
        hollow_wires.append(hollow_wire)
    timings["offset_wires_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_sheet_iml_solid = cq.Solid.makeLoft(face_sheet_wires, ruled=True)
    hollow_iml_solid = cq.Solid.makeLoft(hollow_wires, ruled=True)
    timings["lofts_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    parting_wires = [build_section_wire(_parting_polygon(sec)) for sec in sections]
    parting_solid = cq.Solid.makeLoft(parting_wires, ruled=True)
    timings["parting_solid_s"] = time.perf_counter() - t0

    return SandwichLofts(
        face_sheet_iml_solid=face_sheet_iml_solid,
        hollow_iml_solid=hollow_iml_solid,
        parting_solid=parting_solid,
        timings_s=timings,
    )


def build_sandwich_body(
    body: cq.Shape, lofts: SandwichLofts, include_hollow_interior: bool = True
) -> SandwichBody:
    """Cuts the per-station lofts (built over the FULL original span) against
    the ACTUAL device-cut body, then splits each ring into upper/lower shells
    with the parting prism. Safe to call on either `wing` or
    `control_surface` from a P4 TeCutResult, PROVIDED the region of interest
    is away from the device's spanwise window (module docstring).

    `include_hollow_interior=False` skips the body ∩ hollow_IML boolean —
    measured as the single most expensive operation in this module (370s on
    te_half_twisted_moderate, ~59% of the pre-split total; see
    docs/known_issues.md) — for callers that only need the shells (e.g. the
    dev viewer export). The P6 pipeline itself always needs it (ribs/spars
    are built inside it), so it defaults to True."""
    timings: dict = {}

    t0 = time.perf_counter()
    face_sheet_shell = fuzzy_cut(body, lofts.face_sheet_iml_solid)
    timings["face_sheet_cut_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_band = fuzzy_cut(lofts.face_sheet_iml_solid, lofts.hollow_iml_solid)
    timings["core_cut_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_shell = fuzzy_common(core_band, body)
    timings["core_body_common_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    face_sheet_lower = fuzzy_common(face_sheet_shell, lofts.parting_solid)
    face_sheet_upper = fuzzy_cut(face_sheet_shell, lofts.parting_solid)
    timings["face_split_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_lower = fuzzy_common(core_shell, lofts.parting_solid)
    core_upper = fuzzy_cut(core_shell, lofts.parting_solid)
    timings["core_split_s"] = time.perf_counter() - t0

    hollow_interior = None
    if include_hollow_interior:
        t0 = time.perf_counter()
        hollow_interior = fuzzy_common(body, lofts.hollow_iml_solid)
        timings["hollow_common_s"] = time.perf_counter() - t0

    return SandwichBody(
        face_sheet_shell=face_sheet_shell,
        core_shell=core_shell,
        face_sheet_upper=face_sheet_upper,
        face_sheet_lower=face_sheet_lower,
        core_upper=core_upper,
        core_lower=core_lower,
        hollow_interior=hollow_interior,
        timings_s=timings,
    )
