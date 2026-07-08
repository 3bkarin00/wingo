"""Sandwich-skin IML construction (plan.md §8.7), CLEAN-SPAN ONLY.

IML by **2D per-station offset + second loft + subtract** — never OCC
shell/thicken (F1, docs/known_issues.md has no entry here only because this
project never attempts the banned operation in the first place). R0-probed
before any of this was written (docs/r0_findings/p06.md,
scripts/r0_probes/probe_ocp_offset.py): `cq.Wire.offset2D(-distance,
kind="intersection")` is the real, confirmed-working API.

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

DELIBERATE SCOPE LIMIT (tracked, not silent): this module offsets the
ORIGINAL per-station airfoil sections (`build_planform_sections`'s own
output) — the same sections the OML itself is lofted from. Near a TE device
window, the wing/control_surface bodies' ACTUAL outer boundary is the
cove/nose arc (backend/geometry/cove_profile.py), not the plain airfoil skin,
so cutting these lofts against a body there produces INCORRECT sandwich
geometry (it treats the cut/cove region as if the original, uncut airfoil
were still present). Nose/cove-arc-based sandwich fidelity and the
false-spar closing wall plan.md calls for at the cut face are an explicit
follow-on, not implemented here. Callers should only trust
`build_sandwich_body`'s output away from an enabled device's spanwise window.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq

from backend import tolerances
from backend.geometry.booleans import fuzzy_common, fuzzy_cut
from backend.geometry.loft import build_section_wire
from backend.geometry.sections import PlacedSection
from backend.schema.models import Config


@dataclass
class SandwichLofts:
    face_sheet_iml_solid: cq.Solid
    hollow_iml_solid: cq.Solid
    timings_s: dict = field(default_factory=dict)


@dataclass
class SandwichBody:
    face_sheet_shell: cq.Shape
    core_shell: cq.Shape
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


def build_sandwich_lofts(config: Config, sections: list[PlacedSection]) -> SandwichLofts:
    """Per-station chained offset (face_mm, then core_mm/2 — see module
    docstring) + ruled loft, over the FULL section list exactly as the OML
    itself is lofted (loft.py's build_section_wire, same per-station
    points) — clean-span construction, see module docstring for the device-
    region limitation."""
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

    return SandwichLofts(
        face_sheet_iml_solid=face_sheet_iml_solid,
        hollow_iml_solid=hollow_iml_solid,
        timings_s=timings,
    )


def build_sandwich_body(
    body: cq.Shape, lofts: SandwichLofts, include_hollow_interior: bool = True
) -> SandwichBody:
    """Cuts the per-station lofts (built over the FULL original span) against
    the ACTUAL device-cut body — the boolean naturally restricts each layer
    to wherever `body` really has material, so this is safe to call on
    either `wing` or `control_surface` from a P4 TeCutResult, PROVIDED the
    query point/region is away from the device's spanwise window (module
    docstring).

    `include_hollow_interior=False` skips the body ∩ hollow_IML boolean —
    measured as the single most expensive operation in this module (370s on
    te_half_twisted_moderate, ~59% of the total; see docs/known_issues.md) —
    for callers that only need the two shells (e.g. the dev viewer export).
    The P6 pipeline itself always needs it (ribs/spars are built inside it),
    so it defaults to True."""
    timings: dict = {}

    t0 = time.perf_counter()
    face_sheet_shell = fuzzy_cut(body, lofts.face_sheet_iml_solid)
    timings["face_sheet_cut_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    core_shell = fuzzy_cut(lofts.face_sheet_iml_solid, lofts.hollow_iml_solid)
    timings["core_cut_s"] = time.perf_counter() - t0

    hollow_interior = None
    if include_hollow_interior:
        t0 = time.perf_counter()
        hollow_interior = fuzzy_common(body, lofts.hollow_iml_solid)
        timings["hollow_common_s"] = time.perf_counter() - t0

    return SandwichBody(
        face_sheet_shell=face_sheet_shell,
        core_shell=core_shell,
        hollow_interior=hollow_interior,
        timings_s=timings,
    )
