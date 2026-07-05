"""Reference geometry (plan.md §8.4).

Builds spar ruled surfaces, rib planes (auto + forced), hinge axes, and
hardpoint locations before any boolean cuts are made.
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq
import numpy as np

from backend.geometry.sections import PlacedSection, interp_station, place_section, le_and_z_offset
from backend.schema.models import Config
from backend.airfoils.resample import split_surfaces, interp_surface


@dataclass
class ReferenceGeometry:
    spar_surfaces: dict[str, cq.Shell]
    rib_planes: list[cq.Plane]
    hinge_axes: dict[str, cq.Edge]  # straight lines
    hardpoints: list[cq.Vector]


def _get_canonical_points_at_xc(pts: np.ndarray, xc: float) -> tuple[float, float, float]:
    """Return (upper_z, lower_z, camber_z) at chord fraction xc."""
    upper, lower = split_surfaces(pts)
    zu = float(interp_surface(np.array([xc]), upper)[0])
    zl = float(interp_surface(np.array([xc]), lower)[0])
    return zu, zl, (zu + zl) / 2.0


def build_spar_surfaces(config: Config, sections: list[PlacedSection]) -> dict[str, cq.Shell]:
    """Build a ruled surface shell for each spar from root to tip."""
    spars = {}
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm

    for spar in config.spars:
        faces = []
        prev_edge = None
        for sec in sections:
            xc = spar.xc_root + sec.y_frac * (spar.xc_tip - spar.xc_root)
            chord, twist, pts = interp_station(config, sec.y_frac, config.airfoils.resample_points, te_min_mm)
            zu, zl, _ = _get_canonical_points_at_xc(pts, xc)
            
            canonical_pts = np.array([[xc, zl], [xc, zu]])
            le_x, z_base = le_and_z_offset(config, sec.y_frac, half_span_mm)
            placed = place_section(
                canonical_pts, chord, twist, config.planform.twist_axis_xc,
                y_mm=sec.y_mm, le_x_mm=le_x, z_base_mm=z_base
            )
            
            p1 = cq.Vector(*placed[0])
            p2 = cq.Vector(*placed[1])
            edge = cq.Edge.makeLine(p1, p2)
            
            if prev_edge is not None:
                faces.append(cq.Face.makeRuledSurface(prev_edge, edge))
            prev_edge = edge
            
        spars[spar.name] = cq.Shell.makeShell(faces)
    return spars


def build_rib_planes(config: Config) -> list[cq.Plane]:
    """Rib planes (auto + forced at device edges and break stations)."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    
    forced_fracs = {0.0, 1.0}
    for seg in config.planform.segments:
        forced_fracs.add(seg.y_end_frac)
        
    if config.te_surface and config.te_surface.enabled:
        forced_fracs.add(config.te_surface.span_start_frac)
        forced_fracs.add(config.te_surface.span_end_frac)
        
    if config.le_droop and config.le_droop.enabled:
        forced_fracs.add(config.le_droop.span_start_frac)
        forced_fracs.add(config.le_droop.span_end_frac)
        
    forced_fracs = sorted(list(forced_fracs))
    remaining = config.ribs.count - len(forced_fracs)
    if remaining < 0:
        raise ValueError(
            f"ribs.count={config.ribs.count} is fewer than the "
            f"{len(forced_fracs)} forced rib planes required at segment "
            f"boundaries and device edges {forced_fracs}"
        )

    if remaining > 0:
        gaps = np.diff(forced_fracs)
        alloc = np.round(remaining * gaps / sum(gaps)).astype(int)
        while sum(alloc) < remaining:
            alloc[np.argmax(gaps - alloc * sum(gaps)/remaining)] += 1
        while sum(alloc) > remaining:
            alloc[np.argmax(alloc)] -= 1
            
        all_fracs = []
        for i in range(len(forced_fracs) - 1):
            all_fracs.append(forced_fracs[i])
            if alloc[i] > 0:
                step = (forced_fracs[i+1] - forced_fracs[i]) / (alloc[i] + 1)
                for j in range(1, alloc[i] + 1):
                    all_fracs.append(forced_fracs[i] + j * step)
        all_fracs.append(forced_fracs[-1])
    else:
        all_fracs = forced_fracs
        
    planes = []
    for f in all_fracs:
        y = f * half_span_mm
        planes.append(cq.Plane(origin=(0, y, 0), xDir=(1, 0, 0), normal=(0, 1, 0)))
    return planes


def build_hinge_axes(config: Config) -> dict[str, cq.Edge]:
    """TE/LE hinge axes (straight, containment-sampled)."""
    axes = {}
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm
    
    def _get_hinge_point(y_frac: float, xc: float) -> cq.Vector:
        chord, twist, pts = interp_station(config, y_frac, config.airfoils.resample_points, te_min_mm)
        _, _, zc = _get_canonical_points_at_xc(pts, xc)
        canonical_pts = np.array([[xc, zc]])
        le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
        placed = place_section(
            canonical_pts, chord, twist, config.planform.twist_axis_xc,
            y_mm=y_frac * half_span_mm, le_x_mm=le_x, z_base_mm=z_base
        )
        return cq.Vector(*placed[0])

    if config.te_surface and config.te_surface.enabled:
        p1 = _get_hinge_point(config.te_surface.span_start_frac, config.te_surface.hinge_xc_start)
        p2 = _get_hinge_point(config.te_surface.span_end_frac, config.te_surface.hinge_xc_end)
        axes["te"] = cq.Edge.makeLine(p1, p2)
        
    if config.le_droop and config.le_droop.enabled:
        p1 = _get_hinge_point(config.le_droop.span_start_frac, config.le_droop.hinge_xc_start)
        p2 = _get_hinge_point(config.le_droop.span_end_frac, config.le_droop.hinge_xc_end)
        axes["le"] = cq.Edge.makeLine(p1, p2)
        
    return axes


def build_hardpoints(config: Config) -> list[cq.Vector]:
    """Fuselage attachment hardpoints."""
    pts = []
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm
    
    for bolt in config.hardpoints.fuselage_attachment.bolts:
        y_frac = bolt.y_mm / half_span_mm
        chord, twist, _pts = interp_station(config, y_frac, config.airfoils.resample_points, te_min_mm)
        _, _, zc = _get_canonical_points_at_xc(_pts, bolt.x_c)
        canonical_pts = np.array([[bolt.x_c, zc]])
        le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
        placed = place_section(
            canonical_pts, chord, twist, config.planform.twist_axis_xc,
            y_mm=bolt.y_mm, le_x_mm=le_x, z_base_mm=z_base
        )
        pts.append(cq.Vector(*placed[0]))
    return pts


def build_reference_geometry(config: Config, sections: list[PlacedSection]) -> ReferenceGeometry:
    return ReferenceGeometry(
        spar_surfaces=build_spar_surfaces(config, sections),
        rib_planes=build_rib_planes(config),
        hinge_axes=build_hinge_axes(config),
        hardpoints=build_hardpoints(config),
    )
