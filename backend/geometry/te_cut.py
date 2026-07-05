"""Trailing-edge control-surface cut (plan.md §8.5).

Separates the OML into a fixed wing and a movable TE control surface using two
nested cylinders about the (tilted) hinge axis plus an aft half-space box —
the construction derived in docs/r0_findings/p04.md, which conserves volume by
construction and keeps the nose/cove clearance non-tangent (F4).

  CS   = OML ∩ (nose_cyl ∪ aft_box_cs)      [rounded nose + aft body, inset]
  wing = OML − cove_cyl − aft_box_wing      [fixed structure with a cove recess]
  gap  = OML − wing − CS                     [radial clearance + spanwise/chord gaps]

CS ⊆ (removed-from-wing region), so wing ∩ CS = ∅ and
vol(wing)+vol(CS)+vol(gap) = vol(OML). Shards from the booleans are filtered
(F3). Scoped to half-wing (mirror:false) configs so exactly 2 bodies result.
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq
import numpy as np

from backend.geometry.booleans import filter_shards, fuzzy_common, fuzzy_cut
from backend.geometry.reference import build_hinge_axes
from backend.geometry.sections import interp_station
from backend.airfoils.resample import split_surfaces, interp_surface
from backend.schema.models import Config

# Nose radius as a fraction of the min local half-thickness at the hinge, so
# the rounded nose stays comfortably inside the OML skins (r0_findings/p04.md).
_NOSE_RADIUS_FRACTION = 0.6


@dataclass
class TeCutResult:
    wing: cq.Solid
    control_surface: cq.Solid
    gap_volume_mm3: float
    nose_radius_mm: float
    cove_radius_mm: float
    hinge_dir: np.ndarray  # unit hinge-axis direction (for the F4 tangency check)
    n_wing_bodies: int  # real solids (post shard filter) — plan wants exactly 1
    n_cs_bodies: int
    shards: list  # solids filtered out (F3); gate asserts this is empty


def _vec(a: np.ndarray) -> cq.Vector:
    return cq.Vector(float(a[0]), float(a[1]), float(a[2]))


def _hinge_frame(config: Config):
    """(p_start, p_end, h, a, u, axis_len). h = hinge-axis unit dir; a =
    chordwise-aft unit dir (global +X projected ⟂ h); u = h × a."""
    axis = build_hinge_axes(config)["te"]
    p0 = np.array([axis.startPoint().x, axis.startPoint().y, axis.startPoint().z])
    p1 = np.array([axis.endPoint().x, axis.endPoint().y, axis.endPoint().z])
    h = p1 - p0
    axis_len = float(np.linalg.norm(h))
    h = h / axis_len
    x_global = np.array([1.0, 0.0, 0.0])
    a = x_global - np.dot(x_global, h) * h
    a = a / np.linalg.norm(a)
    u = np.cross(h, a)
    u = u / np.linalg.norm(u)
    return p0, p1, h, a, u, axis_len


def _min_half_thickness_at_hinge(config: Config) -> float:
    """Minimum local half-thickness (mm) at the hinge chord fraction over the
    control-surface span — caps the nose/cove radii."""
    te = config.te_surface
    te_min = config.airfoils.te_min_thickness_mm
    worst = np.inf
    for i in range(9):
        frac = te.span_start_frac + (te.span_end_frac - te.span_start_frac) * i / 8.0
        xc = te.hinge_xc_start + (te.hinge_xc_end - te.hinge_xc_start) * (
            (frac - te.span_start_frac) / (te.span_end_frac - te.span_start_frac)
        )
        chord, _, pts = interp_station(config, frac, config.airfoils.resample_points, te_min)
        upper, lower = split_surfaces(pts)
        zu = float(interp_surface(np.array([xc]), upper)[0])
        zl = float(interp_surface(np.array([xc]), lower)[0])
        worst = min(worst, (zu - zl) / 2.0 * chord)
    return float(worst)


def _aft_box(hinge_mid: np.ndarray, a: np.ndarray, u: np.ndarray,
             length: float, height: float, span: float, aft_offset: float) -> cq.Solid:
    """Box on the +a side of the hinge-axis plane. Local frame x=a (aft),
    z=u (up), y along the span; extends x∈[aft_offset, aft_offset+length],
    centered over `span` in y and over `height` in z."""
    plane = cq.Plane(origin=_vec(hinge_mid), xDir=_vec(a), normal=_vec(u))
    box = (
        cq.Workplane(plane)
        .transformed(offset=cq.Vector(aft_offset, 0, 0))
        .box(length, span, height, centered=(False, True, True))
    )
    return box.val()


def cut_te_surface(config: Config, oml: cq.Solid) -> TeCutResult:
    te = config.te_surface
    if te is None or not te.enabled:
        raise ValueError("config has no enabled te_surface")

    p0, p1, h, a, u, axis_len = _hinge_frame(config)
    hinge_mid = (p0 + p1) / 2.0
    gap = te.gap_mm

    half_thk = _min_half_thickness_at_hinge(config)
    r_nose = _NOSE_RADIUS_FRACTION * half_thk
    r_cove = r_nose + gap
    if r_cove >= half_thk:
        raise ValueError(
            f"cove radius {r_cove:.2f} mm >= local half-thickness {half_thk:.2f} mm — "
            f"gap_mm={gap} too large for this section at the hinge"
        )

    box_len = 3.0 * max(s.chord_mm for s in config.planform.stations)
    box_h = box_len  # generously covers full airfoil thickness

    # Wing-removal tools: full device span [p0, p1], aft plane at the hinge.
    cove_cyl = cq.Solid.makeCylinder(r_cove, axis_len, _vec(p0), _vec(h))
    aft_box_wing = _aft_box(hinge_mid, a, u, box_len, box_h, axis_len, 0.0)

    # CS tools: inset span [p0+gap, p1-gap]; aft plane pushed back by gap_mm so
    # the upper/lower skins get a real chordwise gap (not a tangent contact).
    inset_span = axis_len - 2 * gap
    nose_cyl = cq.Solid.makeCylinder(r_nose, inset_span, _vec(p0 + h * gap), _vec(h))
    aft_box_cs = _aft_box(hinge_mid, a, u, box_len, box_h, inset_span, gap)

    # Bodies.
    wing_shape = fuzzy_cut(fuzzy_cut(oml, cove_cyl), aft_box_wing)
    cs_region = nose_cyl.fuse(aft_box_cs)
    cs_shape = fuzzy_common(oml, cs_region)

    wing_solids, wing_shards = filter_shards(wing_shape)
    cs_solids, cs_shards = filter_shards(cs_shape)

    wing_solids.sort(key=lambda s: s.Volume(), reverse=True)
    cs_solids.sort(key=lambda s: s.Volume(), reverse=True)
    wing = wing_solids[0]
    cs = cs_solids[0]

    gap_volume = oml.Volume() - wing.Volume() - cs.Volume()
    return TeCutResult(
        wing=wing,
        control_surface=cs,
        gap_volume_mm3=gap_volume,
        nose_radius_mm=r_nose,
        cove_radius_mm=r_cove,
        hinge_dir=h,
        n_wing_bodies=len(wing_solids),
        n_cs_bodies=len(cs_solids),
        shards=wing_shards + cs_shards,
    )
