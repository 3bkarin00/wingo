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
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_cut
from backend.geometry.loft import is_watertight
from backend.geometry.pi_joints import offset_skin_segments
from backend.geometry.spars import footprints_at
from backend.schema.models import Config


@dataclass
class Rib:
    y_mm: float
    solid: cq.Shape
    has_hole: bool
    area_mm2: float
    # The rib's own centerline face (the built — i.e. π-offset, D24 —
    # outline wire, filled; a rib is flat by construction) — plan.md §8.7's
    # midsurface requirement for this body is already free once the solid
    # is built; see backend/geometry/midsurface.py.
    midsurface_face: cq.Face
    # ORIGINAL (pre-π-offset) ordered section polygon points — the cavity-
    # boundary contact curve pi_joints.build_pi_preforms sweeps its preform
    # bodies along (the π paths live on the true IML, not the offset edge).
    outline_pts: "np.ndarray | None" = None
    # D25: matched tab bond faces (§8.8 centroid registry, recorded by
    # interlock.tab_bond_registry at cut time, matched against the finished
    # rib) — empty when no crossing on this rib is interlocked.
    tab_bond_faces: dict = field(default_factory=dict)


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


def _ordered_points_from_section(solid: cq.Shape, plane: cq.Plane) -> "np.ndarray | None":
    """BRepAlgoAPI_Section -> assembleEdges -> WireExplorer-ordered points
    (module docstring). None if the plane misses the solid or the section
    isn't a single closed loop. Returns the ordered (N,3) polygon points —
    callers build the clean Wire.makePolygon themselves (the π-joint rib
    offset, D24, needs the raw points BEFORE any wire is built)."""
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
        pts.append([p.X(), p.Y(), p.Z()])
        explorer.Next()
    if len(pts) < 3:
        return None
    return np.array(pts)


def _polygon_wire(pts: np.ndarray) -> cq.Wire:
    return cq.Wire.makePolygon([cq.Vector(*p) for p in pts], close=True)


def _rib_slab(wire: cq.Wire, thickness_mm: float, normal: cq.Vector) -> cq.Solid:
    """One full-thickness prism from `wire` shifted -thickness/2 along
    `normal` — NOT two half-thickness prisms fused at the plane (that hit
    F4-style tangent-boundary fragility, module docstring)."""
    shifted = wire.translate(normal.multiply(-thickness_mm / 2))
    return cq.Solid.extrudeLinear(shifted, [], normal.multiply(thickness_mm))


def _lightening_hole_cut(
    config: Config, slab: cq.Solid, wire: cq.Wire, thickness_mm: float, normal: cq.Vector,
    margin_mm: float, y_mm: float, rib_index: int,
) -> cq.Shape | None:
    """The verified hole cut (module docstring steps 4-5). None if the
    offset/cut doesn't produce a clean single solid — caller falls back to
    the solid slab.

    D25 keep-out (found empirically, docs/r0_findings/p06_ext.md): before
    cutting, every INTERLOCKED crossing's tab region (interlock.
    crossing_protect_wire) is subtracted from the cutting TOOL, not the
    slab — the hole's own offset boundary can otherwise slice straight
    through the gap between two adjacent tabs and fragment a tab's bond
    wall, which the centroid registry correctly hard-fails on. Zero effect
    when no interlocked crossing exists at this rib (byte-identical to
    pre-D25 behavior)."""
    offset_result = wire.offset2D(-margin_mm, kind="intersection")
    inner = offset_result[0] if isinstance(offset_result, list) else offset_result
    if not inner.IsClosed():
        return None
    shifted_inner = inner.translate(normal.multiply(-thickness_mm))
    hole_tool = cq.Solid.extrudeLinear(shifted_inner, [], normal.multiply(3 * thickness_mm))

    from backend.geometry.interlock import crossing_protect_wire, interlock_active

    for fp in footprints_at(config, y_mm, 0.0):
        spar = next(s for s in config.spars if s.name == fp.spar_name)
        if not interlock_active(config, spar, rib_index, y_mm, thickness_mm):
            continue
        protect_wire = crossing_protect_wire(config, spar, fp)
        shifted_protect = protect_wire.translate(normal.multiply(-1.5 * thickness_mm))
        protect_tool = cq.Solid.extrudeLinear(shifted_protect, [], normal.multiply(3 * thickness_mm))
        hole_tool = fuzzy_cut(hole_tool, protect_tool)

    cut = fuzzy_cut(slab, hole_tool)
    solids, shards = filter_shards(cut, min_volume=1e-6)
    if len(solids) != 1 or not cut.isValid() or not is_watertight(solids[0]):
        return None
    return cut


def _spar_cutouts(
    config: Config, rib_shape: cq.Shape, y_mm: float, thickness_mm: float,
    normal: cq.Vector, rib_index: int,
) -> "tuple[cq.Shape, dict]":
    """D23 shape-dependent spar cutouts (plan.md §8.7 step 7b): one
    generously-oversized prism per footprint part (spars.spar_footprint —
    the single source shared with D25's interlock slots), clearance grown in
    canonical space by the footprint function itself, cut with the same
    "oversized tool + fuzzy boolean" pattern as the lightening hole above.
    A full-height web cutout legitimately SPLITS the rib into fore/aft
    solids (each piece still bonds to the skin) — multiple kept solids are
    a valid outcome here.

    D25: at an interlocked crossing (web-bearing spar shape + interlock
    enabled + no per-rib override) the WEB part's plain prism is replaced by
    interlock.rib_cut_tool's notched tool, so the rib keeps its tabs; cap
    parts and every non-interlocked crossing use the plain prism unchanged
    (box/tube stay byte-identical to pre-D25 by never entering the
    interlock path at all)."""
    from backend.geometry.face_registry import FaceRegistry
    from backend.geometry.interlock import interlock_active, rib_cut_tool, tab_bond_registry

    registry = FaceRegistry()
    spars_by_name = {s.name: s for s in config.spars}
    for fp in footprints_at(config, y_mm, tolerances.SPAR_RIB_CUTOUT_CLEARANCE_MM):
        spar = spars_by_name[fp.spar_name]
        interlocked = interlock_active(config, spar, rib_index, y_mm, thickness_mm)
        for part in fp.parts:
            if interlocked and part.kind == "web":
                tool = rib_cut_tool(
                    config, spar, fp, part.wire, normal, thickness_mm,
                    tolerances.SPAR_RIB_CUTOUT_CLEARANCE_MM,
                )
                tab_bond_registry(
                    config, spar, fp, thickness_mm,
                    tolerances.SPAR_RIB_CUTOUT_CLEARANCE_MM, registry,
                )
            else:
                shifted = part.wire.translate(normal.multiply(-1.5 * thickness_mm))
                tool = cq.Solid.extrudeLinear(shifted, [], normal.multiply(3 * thickness_mm))
            rib_shape = fuzzy_cut(rib_shape, tool)
    # Match recorded tab faces against the FINISHED rib (hard failure inside
    # match if a later cut ate one) — empty registry matches to {}.
    return rib_shape, registry.match(rib_shape)


def build_ribs(
    config: Config, hollow_interior: cq.Shape, planes: list[cq.Plane]
) -> RibSet:
    """One rib per plane in `planes` (backend/geometry/reference.py's
    build_rib_planes output), cut from `hollow_interior`
    (build_sandwich_body's cavity solid — the rib bonds to the surrounding
    inner face sheet at its perimeter by construction, since that IS the
    hollow interior's own boundary). Spar cutouts (D23) are applied last,
    after the lightening hole."""
    thickness_mm = rib_thickness_mm(config)
    margin_mm = config.ribs.lightening_holes.margin_mm if config.ribs.lightening_holes.enabled else 0.0

    result = RibSet()
    for rib_index, plane in enumerate(planes):
        y = plane.origin.y
        outline_pts = _ordered_points_from_section(hollow_interior, plane)
        if outline_pts is None:
            result.skipped_no_section.append(y)
            continue

        # D24: skin-contact segments pulled inward by base+bond-gap BEFORE
        # any wire/solid is built (pi_joints module docstring, part 1).
        wire = _polygon_wire(offset_skin_segments(outline_pts))

        normal = plane.zDir
        slab = _rib_slab(wire, thickness_mm, normal)

        rib_shape: cq.Shape = slab
        has_hole = False
        if margin_mm > 0:
            cut = _lightening_hole_cut(config, slab, wire, thickness_mm, normal, margin_mm, y, rib_index)
            if cut is not None:
                rib_shape = cut
                has_hole = True
            else:
                result.fallback_solid.append(y)

        rib_shape, tab_bond_faces = _spar_cutouts(
            config, rib_shape, y, thickness_mm, normal, rib_index,
        )

        solids, _shards = filter_shards(rib_shape, min_volume=1e-6)
        area_mm2 = sum(s.Volume() for s in solids) / thickness_mm if solids else 0.0
        midsurface_face = cq.Face.makeFromWires(wire)
        result.ribs.append(Rib(
            y_mm=y, solid=rib_shape, has_hole=has_hole, area_mm2=area_mm2,
            midsurface_face=midsurface_face, outline_pts=outline_pts,
            tab_bond_faces=tab_bond_faces,
        ))

    return result
