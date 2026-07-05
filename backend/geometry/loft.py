"""Master OML loft (plan.md §8.3).

Builds closed polygon section wires, lofts them into a watertight solid with a
RULED loft, and mirrors to full span. Uses the OCP loft API confirmed in
docs/r0_findings/p02.md, with two design decisions the R0/P2 diagnostics forced:

- **Polygon wires + ruled=True**, not spline wires + ruled=False. A spline
  loft bulges ~3% outward between sections (right at the volume-gate limit) and
  its volume is unstable with section count; a ruled loft over polygon wires
  connects all corresponding section vertices, giving a volume that matches the
  analytic prismatoid to <0.3% and planar facets that are robust for the
  boolean cuts in P4+. (ruled=True with SPLINE wires is wrong — it uses only
  the wires' 2 edge endpoints.)
- IsValid() is necessary but NOT sufficient (a misaligned loft can be valid yet
  geometrically wrong), so the P2 gate pairs watertightness with the volume band.
"""
from __future__ import annotations

import cadquery as cq
import numpy as np
from OCP.BRepCheck import BRepCheck_Analyzer

from backend.geometry.sections import PlacedSection


def build_section_wire(points3d: np.ndarray) -> cq.Wire:
    """Closed polygon wire through ordered (N,3) section points. `close=True`
    adds the final edge from the last point (lower TE) back to the first (upper
    TE), which is the blunt-TE closing edge."""
    verts = [cq.Vector(float(x), float(y), float(z)) for x, y, z in points3d]
    return cq.Wire.makePolygon(verts, forConstruction=False, close=True)


def _mirror_sections(sections: list[PlacedSection]) -> list[np.ndarray]:
    """Full-span ordered list of (N,3) point arrays: the y<0 side is the y>0
    side reflected across the root plane (Y→−Y), point order preserved so loft
    correspondence stays aligned. The root (y≈0) section appears once."""
    positive = [s.points for s in sections]
    mirrored = []
    for s in reversed(sections):
        if abs(s.y_mm) < 1e-9:
            continue  # don't duplicate the root
        refl = s.points.copy()
        refl[:, 1] = -refl[:, 1]
        mirrored.append(refl)
    return mirrored + positive


def _full_span_points(sections: list[PlacedSection], mirror: bool) -> list[np.ndarray]:
    return _mirror_sections(sections) if mirror else [s.points for s in sections]


def build_oml(sections: list[PlacedSection], mirror: bool) -> cq.Solid:
    """Loft the placed sections into a watertight OML solid (ruled, polygon
    wires), mirroring to full span when `mirror` is set."""
    ordered = _full_span_points(sections, mirror)
    wires = [build_section_wire(p) for p in ordered]
    return cq.Solid.makeLoft(wires, ruled=True)


def is_watertight(solid: cq.Solid) -> bool:
    """Watertight = OCC-valid AND every shell is closed (r0_findings/p02.md)."""
    if not BRepCheck_Analyzer(solid.wrapped).IsValid():
        return False
    shells = solid.Shells()
    return len(shells) >= 1 and all(s.wrapped.Closed() for s in shells)


def _polygon_area_3d(points: np.ndarray) -> float:
    """Planar area of a (near-planar) closed 3D polygon = |vector area|."""
    centered = points - points.mean(axis=0)
    cross = np.cross(centered, np.roll(centered, -1, axis=0))
    return 0.5 * float(np.linalg.norm(cross.sum(axis=0)))


def analytic_volume_estimate(
    sections: list[PlacedSection], mirror: bool, substeps: int = 16
) -> float:
    """∫ cross-section-area along the true swept/dihedral span path — the
    independent cross-check for the loft volume (§9 P2, ±3%). Reconstructs the
    same ruled blend the loft builds (linear interpolation of corresponding
    section vertices), so it agrees with a correct loft to <0.3% and DIVERGES
    if the loft mis-corresponds/twists the sections (catching that trap).
    """
    full = _full_span_points(sections, mirror)
    total = 0.0
    for i in range(len(full) - 1):
        p0, p1 = full[i], full[i + 1]
        ds = float(np.linalg.norm(p1.mean(axis=0) - p0.mean(axis=0)))
        t = np.linspace(0.0, 1.0, substeps + 1)
        areas = np.array([_polygon_area_3d((1 - tt) * p0 + tt * p1) for tt in t])
        total += float(np.trapezoid(areas, t)) * ds
    return total
