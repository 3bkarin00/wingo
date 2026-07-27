"""Midsurface faces (plan.md §8.7: "Midsurface faces constructed here,
alongside the solids — not extracted later"), for the P14 Ansys FEA route
(D15: "Mechanical layered shell sections" — ONE shell per wall, the
face/core/face LAYUP is a shell-section MATERIAL property applied later
with the layup schedule export, not multiple separate midsurface
geometries per layer).

THREE sources, each already has almost everything it needs built:
  - Wing skin: NEW here — per-station offset at stack_mm/2 (half the
    panel's face+core+face thickness) from the OML, lofted as an open
    SHELL (BRepOffsetAPI_ThruSections isSolid=False — the same OCC call
    cq.Solid.makeLoft already uses internally with isSolid=True; verified
    on the real kernel, docs/r0_findings/p06.md's midsurface addendum).
    CLEAN-SPAN ONLY (same scope limit iml.py itself started with): no
    ramp/cove-fidelity correction — an explicit, tracked follow-on, not
    silent, matching every other device-region refinement this phase has
    deferred so far.
  - Ribs: ALREADY built, just not previously exposed — ribs.py's own
    pre-thickening wire IS the rib's midsurface (a rib is flat by
    construction). See ribs.py's Rib.midsurface_face.
  - Spars: ALREADY built in P3 — reference.build_spar_surfaces's
    zero-thickness ruled Shell per spar IS the spar's midsurface exactly
    (spar_trim.py only added thickness+trim on top of it for the solid).

NOT OCC shell/thicken (F1 is about the wing/CS skin's SOLID IML
construction specifically) — this builds an OPEN surface directly via
BRepOffsetAPI_ThruSections, never thickens anything.
"""
from __future__ import annotations

import cadquery as cq
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

from backend.geometry.iml import face_sheet_thickness_mm, offset_wire
from backend.geometry.loft import build_section_wire
from backend.geometry.sections import PlacedSection
from backend.schema.models import Config


def _shell_loft(wires: list[cq.Wire], ruled: bool = True) -> cq.Shape:
    """BRepOffsetAPI_ThruSections with isSolid=False: the lateral surface
    only, no end caps — cq.Solid.makeLoft is the SAME call with
    isSolid=True (its own source comment says so). R0-verified: face
    count and total area exactly match the equivalent solid loft's lateral
    faces (docs/r0_findings/p06.md)."""
    builder = BRepOffsetAPI_ThruSections(False, ruled)
    for w in wires:
        builder.AddWire(w.wrapped)
    builder.Build()
    return cq.Shape.cast(builder.Shape())


def build_skin_midsurface(config: Config, sections: list[PlacedSection]) -> cq.Shape:
    """Wing-skin midsurface: per-station offset at half the panel's total
    stack thickness (face+core+face)/2 from the OML, lofted as an open
    shell. Clean-span only — module docstring."""
    face_mm = face_sheet_thickness_mm(config)
    core_mm = config.skin.core.thickness_mm
    mid_offset_mm = face_mm + core_mm / 2.0

    wires = [offset_wire(build_section_wire(sec.points), mid_offset_mm) for sec in sections]
    return _shell_loft(wires, ruled=True)
