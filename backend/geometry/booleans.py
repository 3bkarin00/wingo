"""Shared boolean helpers for the device-cut phases (P4+).

Centralizes the two things every boolean in this tool must do (§0.2 hard
rules): run with an explicit fuzzy value near tangency-prone cuts, and filter
micro-shards afterwards (F3). Mechanics confirmed in docs/r0_findings/p04.md.
"""
from __future__ import annotations

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.GeomAbs import GeomAbs_Cylinder

from backend import tolerances


def _solids(shape: cq.Shape) -> list[cq.Solid]:
    return shape.Solids()


def fuzzy_cut(base: cq.Shape, tool: cq.Shape, fuzzy: float | None = None) -> cq.Shape:
    """base − tool with an explicit fuzzy value (default from tolerances)."""
    op = BRepAlgoAPI_Cut(base.wrapped, tool.wrapped)
    op.SetFuzzyValue(tolerances.BOOLEAN_FUZZY_VALUE_MM if fuzzy is None else fuzzy)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("BRepAlgoAPI_Cut failed")
    return cq.Shape.cast(op.Shape())


def fuzzy_common(a: cq.Shape, b: cq.Shape, fuzzy: float | None = None) -> cq.Shape:
    """a ∩ b (intersection) with an explicit fuzzy value."""
    op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    op.SetFuzzyValue(tolerances.BOOLEAN_FUZZY_VALUE_MM if fuzzy is None else fuzzy)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("BRepAlgoAPI_Common failed")
    return cq.Shape.cast(op.Shape())


def fuzzy_fuse(a: cq.Shape, b: cq.Shape, fuzzy: float | None = None) -> cq.Shape:
    """a ∪ b (union) with an explicit fuzzy value. Callers must give the two
    bodies a genuine positive-volume overlap first — never fuse across an
    exact shared boundary (F4)."""
    op = BRepAlgoAPI_Fuse(a.wrapped, b.wrapped)
    op.SetFuzzyValue(tolerances.BOOLEAN_FUZZY_VALUE_MM if fuzzy is None else fuzzy)
    op.Build()
    if not op.IsDone():
        raise RuntimeError("BRepAlgoAPI_Fuse failed")
    return cq.Shape.cast(op.Shape())


def coaxial_cylinder_radii(
    solid: cq.Shape, axis_dir: np.ndarray, axis_tol: float = 0.02
) -> list[float]:
    """Radii of every cylindrical face of `solid` whose axis is (anti)parallel
    to `axis_dir`. Used for the F4 tangency check: a cove and a nose that share
    a radius (within FACE_TANGENCY_TOLERANCE_MM) are tangent/coincident; the
    deliberate clearance makes their radii distinct."""
    axis_dir = axis_dir / np.linalg.norm(axis_dir)
    radii = []
    for face in solid.Faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        d = surf.Cylinder().Axis().Direction()
        axv = np.array([d.X(), d.Y(), d.Z()])
        if abs(abs(float(np.dot(axv, axis_dir))) - 1.0) < axis_tol:
            radii.append(surf.Cylinder().Radius())
    return radii


def coaxial_cylinder_axis_deviation(
    solid: cq.Shape, axis_point: np.ndarray, axis_dir: np.ndarray, dir_tol: float = 0.02
) -> list[float]:
    """Perpendicular distance from the TRUE axis line (through `axis_point`,
    direction `axis_dir`) to the axis LINE of every cylindrical face of
    `solid` whose own axis direction is (anti)parallel to `axis_dir` within
    `dir_tol`. Unlike coaxial_cylinder_radii (F4: direction-only, used to
    tell two DIFFERENT radii apart), this checks the LINES actually
    coincide, not just that they're parallel — the P7 hinge-hole coaxiality
    check (plan.md: within COAXIALITY_TOLERANCE_MM)."""
    axis_dir = axis_dir / np.linalg.norm(axis_dir)
    deviations = []
    for face in solid.Faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surf.Cylinder()
        d = cyl.Axis().Direction()
        axv = np.array([d.X(), d.Y(), d.Z()])
        if abs(abs(float(np.dot(axv, axis_dir))) - 1.0) > dir_tol:
            continue
        loc = cyl.Axis().Location()
        p = np.array([loc.X(), loc.Y(), loc.Z()])
        w = axis_point - p
        perp = w - np.dot(w, axv) * axv
        deviations.append(float(np.linalg.norm(perp)))
    return deviations


def filter_shards(
    shape: cq.Shape, min_volume: float | None = None
) -> tuple[list[cq.Solid], list[cq.Solid]]:
    """Split a boolean result's solids into (kept, shards) by volume threshold
    (F3). `kept` are real bodies; `shards` are micro-fragments to discard.
    Returned separately so a gate can assert `len(shards) == 0`."""
    threshold = tolerances.SHARD_MIN_VOLUME_MM3 if min_volume is None else min_volume
    kept, shards = [], []
    for solid in _solids(shape):
        (kept if solid.Volume() >= threshold else shards).append(solid)
    return kept, shards
