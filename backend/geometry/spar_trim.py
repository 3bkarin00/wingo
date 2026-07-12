"""Spar-web thickening + trim-to-IML (plan.md §8.7: "Spars trimmed to IML").

P3 (backend/geometry/reference.py's build_spar_surfaces) already builds each
spar as a ZERO-THICKNESS ruled surface from root to tip: per station, a
single line from the lower-skin point to the upper-skin point at the spar's
chordwise location (xc, interpolated root-to-tip). This module thickens
that into a real web solid and trims it to the actual available cavity —
the spar bonds to the surrounding INNER face sheet, so "trimmed to IML"
means intersected with `hollow_interior` (build_sandwich_body's cavity
solid — the same one ribs.py cuts its rib planes from; reused here, not
recomputed).

NOT OCC shell/thicken (F1 is specifically about the wing/CS skin IML, but
the underlying fragility concern applies just as well to thickening a
curved ruled surface in general): instead, per-station canonical
RECTANGLES (web thickness centered on xc, generously oversized vertically
past both zu and zl — SPAR_HEIGHT_OVERSIZE_CHORD_FRAC below, same
"generously oversized cutting/building volume" convention as
false_spar.py's _WALL_HALF_HEIGHT_CHORD_FRAC and te_cut.py's aft boxes) are
lofted (ruled=True, the same primitive every other body in this project
uses) into a "spar blank" solid, THEN intersected with `hollow_interior` —
the trimming boolean does the actual work of stopping the web exactly at
the inner face sheet boundary, so the oversize amount only needs to
generously exceed the true structural height, not predict it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import fuzzy_common
from backend.geometry.loft import build_section_wire
from backend.geometry.reference import get_canonical_points_at_xc, le_and_z_offset
from backend.geometry.sections import PlacedSection, interp_station, place_section
from backend.schema.models import Config

# How far past the true zu/zl the per-station rectangle extends (fraction
# of local chord) before trimming against hollow_interior — purely a
# construction safety margin (never appears in the trimmed result, the
# boolean stops the web at the real cavity boundary), same role as
# false_spar.py's _WALL_HALF_HEIGHT_CHORD_FRAC.
SPAR_HEIGHT_OVERSIZE_CHORD_FRAC = 0.15


@dataclass
class TrimmedSpar:
    name: str
    solid: cq.Shape
    web_thickness_mm: float
    timings_s: dict = field(default_factory=dict)


def spar_web_thickness_mm(config: Config, spar_name: str) -> float:
    """Same provisional ply-thickness lookup as face_sheet_thickness_mm
    (iml.py) and rib_thickness_mm (ribs.py)."""
    spar = next(s for s in config.spars if s.name == spar_name)
    ply_thickness = tolerances.PLY_THICKNESS_MM_PROVISIONAL[spar.web.material]
    return spar.web.plies * ply_thickness


def _spar_blank(
    config: Config, sections: list[PlacedSection], xc_root: float, xc_tip: float, thickness_mm: float
) -> cq.Solid:
    """Per-station rectangle (chordwise width = thickness_mm centered on the
    interpolated xc, vertical extent oversized past zu/zl) lofted ruled=True
    — same construction style as every other per-station body in this
    project (never OCC shell/thicken)."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm
    resample_points = config.airfoils.resample_points

    wires = []
    for sec in sections:
        xc = xc_root + sec.y_frac * (xc_tip - xc_root)
        chord, twist, pts = interp_station(config, sec.y_frac, resample_points, te_min_mm)
        zu, zl, _ = get_canonical_points_at_xc(pts, xc)
        oversize = SPAR_HEIGHT_OVERSIZE_CHORD_FRAC
        half_width_frac = (thickness_mm / 2.0) / chord

        corners = np.array([
            [xc - half_width_frac, zl - oversize],
            [xc + half_width_frac, zl - oversize],
            [xc + half_width_frac, zu + oversize],
            [xc - half_width_frac, zu + oversize],
        ])
        le_x, z_base = le_and_z_offset(config, sec.y_frac, half_span_mm)
        placed = place_section(
            corners, chord, twist, config.planform.twist_axis_xc,
            y_mm=sec.y_mm, le_x_mm=le_x, z_base_mm=z_base,
        )
        wires.append(build_section_wire(placed))

    return cq.Solid.makeLoft(wires, ruled=True)


def build_trimmed_spars(
    config: Config, sections: list[PlacedSection], hollow_interior: cq.Shape
) -> list[TrimmedSpar]:
    """One thickened, IML-trimmed web per config.spars entry."""
    import time

    result = []
    for spar in config.spars:
        t0 = time.perf_counter()
        thickness_mm = spar_web_thickness_mm(config, spar.name)
        blank = _spar_blank(config, sections, spar.xc_root, spar.xc_tip, thickness_mm)
        timings = {"blank_s": time.perf_counter() - t0}

        t0 = time.perf_counter()
        trimmed = fuzzy_common(blank, hollow_interior)
        timings["trim_s"] = time.perf_counter() - t0

        result.append(TrimmedSpar(
            name=spar.name, solid=trimmed, web_thickness_mm=thickness_mm, timings_s=timings,
        ))
    return result
