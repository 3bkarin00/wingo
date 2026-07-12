"""Rib construction (plan.md §8.7): plane ∩ inner volume, lightening-hole
cutout as a 2D face op, then thickened about the rib plane's Y station.

Rib planes (auto + forced at device edges and break stations) already exist
from P3 (backend/geometry/reference.py's build_rib_planes) — this module
consumes them, it doesn't place them.

CONSTRUCTION, per rib plane:
  1. Section `hollow_interior` (build_sandwich_body's cavity solid) at the
     plane via BRepAlgoAPI_Section (same route cove_profile.py's
     section_points already uses) — gives the rib's boundary EDGES.
  2. Wire.assembleEdges stitches them into one closed wire; walked with
     BRepTools_WireExplorer (NOT edge.startPoint() blindly — individual
     edges in an assembled wire can be REVERSED, and naively pulling
     start points scrambles the polygon; WireExplorer's CurrentVertex()
     respects orientation) into an ORDERED point list, rebuilt as a clean
     Wire.makePolygon — the same reliable primitive build_section_wire
     uses everywhere else in this codebase. This "rebuild as clean
     polygon" step was empirically necessary: the raw assembleEdges wire
     (hundreds of small edges straight from the boolean-result section)
     is measurably fragile for the offset2D/extrudeLinear calls below
     (docs/r0_findings/p06.md's ribs addendum has the full R0 trail).
  3. Thickened about the plane by extruding a SINGLE full-thickness prism
     from the wire translated by -rib_mm/2 (not two half-thickness prisms
     fused at the plane — that hit the same F4-style tangent-boundary
     fragility booleans.py's fuzzy tolerance exists to avoid elsewhere).
  4. If lightening holes are enabled: offset2D(-margin_mm, kind=
     "intersection") insets the wire (same route iml.py/cove_profile.py
     already use — margin_mm is GUARANTEED by construction, no separate
     circle-fitting algorithm; the schema (`LighteningHoles`: `enabled`,
     `margin_mm` only) doesn't ask for more than one hole per rib). The
     hole is cut with an OVERSIZED prism (3x rib_mm) + fuzzy_cut — same
     "generously oversized cutting tool + fuzzy boolean" pattern te_cut.py's
     aft boxes and cove_profile's arcs already use, not extrudeLinear's own
     inner-wire parameter (empirically fragile on this wire — same addendum).
  5. VERIFIED, not assumed: exactly one solid, valid, watertight. If the
     hole cut fails this (empirically: an 8mm margin genuinely does not
     fit some rib stations on tests/configs/edge/high_taper.yaml's 10:1
     taper — areas down to ~100mm² near the tip), falls back to the SOLID
     slab (no hole) for that one station and logs it — the same graceful-
     degradation-over-crash posture iml.py's own aft self-clip already
     established for this project (ramps to solid laminate rather than
     erroring when a feature doesn't locally fit).

NOT the F1-banned "shell/thicken a curved skin" — this extrudes a FLAT
planar face along its own normal, a categorically different (and much
simpler/more robust) OCC operation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_cut
from backend.geometry.loft import is_watertight
from backend.schema.models import Config


@dataclass
class Rib:
    y_mm: float
    solid: cq.Shape
    has_hole: bool
    area_mm2: float


@dataclass
class RibSet:
    ribs: list[Rib] = field(default_factory=list)
    # Plane outside the body's span, OR the cross-section isn't one simple
    # closed loop (e.g. disconnected pieces at a device-window edge).
    skipped_no_section: list[float] = field(default_factory=list)
    fallback_solid: list[float] = field(default_factory=list)  # hole didn't fit, built solid instead


def rib_thickness_mm(config: Config) -> float:
    """Same provisional ply-thickness lookup as face_sheet_thickness_mm
    (backend/geometry/iml.py) and validators.py — a materials DB
    supersedes all these call sites at once in P1+/D17."""
    ply_thickness = tolerances.PLY_THICKNESS_MM_PROVISIONAL[config.ribs.construction.material]
    return config.ribs.construction.plies * ply_thickness


def _ordered_wire_from_section(solid: cq.Shape, plane: cq.Plane) -> cq.Wire | None:
    """BRepAlgoAPI_Section -> assembleEdges -> WireExplorer-ordered points ->
    clean Wire.makePolygon (module docstring). None if the plane misses the
    solid or the section isn't a single closed loop."""
    pln = gp_Pln(gp_Pnt(*plane.origin.toTuple()), gp_Dir(*plane.zDir.toTuple()))
    op = BRepAlgoAPI_Section(solid.wrapped, pln)
    op.Build()
    if not op.IsDone():
        return None
    sec_shape = cq.Shape.cast(op.Shape())
    edges = sec_shape.Edges()
    if not edges:
        return None
    try:
        # A rib plane at/near a device-window edge can section a
        # hollow_interior whose cross-section isn't one simple loop
        # (e.g. disconnected pieces either side of the cove/false-spar
        # boundary) — assembleEdges raises StdFail_NotDone outright in
        # that case rather than returning something to IsClosed()-check.
        raw_wire = cq.Wire.assembleEdges(edges)
    except Exception:
        return None
    if not raw_wire.IsClosed():
        return None

    explorer = BRepTools_WireExplorer(raw_wire.wrapped)
    pts = []
    while explorer.More():
        p = BRep_Tool.Pnt_s(explorer.CurrentVertex())
        pts.append(cq.Vector(p.X(), p.Y(), p.Z()))
        explorer.Next()
    if len(pts) < 3:
        return None
    return cq.Wire.makePolygon(pts, close=True)


def _rib_slab(wire: cq.Wire, thickness_mm: float, normal: cq.Vector) -> cq.Solid:
    """One full-thickness prism from `wire` shifted -thickness/2 along
    `normal` — NOT two half-thickness prisms fused at the plane (that hit
    F4-style tangent-boundary fragility, module docstring)."""
    shifted = wire.translate(normal.multiply(-thickness_mm / 2))
    return cq.Solid.extrudeLinear(shifted, [], normal.multiply(thickness_mm))


def _lightening_hole_cut(
    slab: cq.Solid, wire: cq.Wire, thickness_mm: float, normal: cq.Vector, margin_mm: float
) -> cq.Shape | None:
    """The verified hole cut (module docstring steps 4-5). None if the
    offset/cut doesn't produce a clean single solid — caller falls back to
    the solid slab."""
    offset_result = wire.offset2D(-margin_mm, kind="intersection")
    inner = offset_result[0] if isinstance(offset_result, list) else offset_result
    if not inner.IsClosed():
        return None
    shifted_inner = inner.translate(normal.multiply(-thickness_mm))
    hole_tool = cq.Solid.extrudeLinear(shifted_inner, [], normal.multiply(3 * thickness_mm))
    cut = fuzzy_cut(slab, hole_tool)
    solids, shards = filter_shards(cut, min_volume=1e-6)
    if len(solids) != 1 or not cut.isValid() or not is_watertight(solids[0]):
        return None
    return cut


def build_ribs(
    config: Config, hollow_interior: cq.Shape, planes: list[cq.Plane]
) -> RibSet:
    """One rib per plane in `planes` (backend/geometry/reference.py's
    build_rib_planes output), cut from `hollow_interior`
    (build_sandwich_body's cavity solid — the rib bonds to the surrounding
    inner face sheet at its perimeter by construction, since that IS the
    hollow interior's own boundary)."""
    thickness_mm = rib_thickness_mm(config)
    margin_mm = config.ribs.lightening_holes.margin_mm if config.ribs.lightening_holes.enabled else 0.0

    result = RibSet()
    for plane in planes:
        y = plane.origin.y
        wire = _ordered_wire_from_section(hollow_interior, plane)
        if wire is None:
            result.skipped_no_section.append(y)
            continue

        normal = plane.zDir
        slab = _rib_slab(wire, thickness_mm, normal)

        rib_shape: cq.Shape = slab
        has_hole = False
        if margin_mm > 0:
            cut = _lightening_hole_cut(slab, wire, thickness_mm, normal, margin_mm)
            if cut is not None:
                rib_shape = cut
                has_hole = True
            else:
                result.fallback_solid.append(y)

        solids, _shards = filter_shards(rib_shape, min_volume=1e-6)
        area_mm2 = solids[0].Volume() / thickness_mm if solids else 0.0
        result.ribs.append(Rib(y_mm=y, solid=rib_shape, has_hole=has_hole, area_mm2=area_mm2))

    return result
