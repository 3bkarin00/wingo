"""Trailing-edge control-surface cut (plan.md §8.5, refined per-station arc
construction — docs/decisions/ADR-002, docs/r0_findings/p04.md).

Per-station 2D profiles in planes PERPENDICULAR to the (tilted) hinge axis:
the CS nose is one or two arcs centered on the station's hinge-axis point C,
each passing through the "normal foot" on the upper/lower OML skin (tangent
to the skin there by construction — see backend/geometry/cove_profile.py).
The wing cove is a concentric arc at the same C, offset by a fixed
COVE_CLEARANCE_MM — never tangent to the nose, and invariant under rotation
about the axis (i.e. at any deflection angle) by construction. Lofting these
per-station profiles (polygon wires + ruled=True, matching the OML's own
construction, r0_findings/p02.md) gives the nose/cove REGION solids, which
then play the same role P4-v1's cylinders did in the boolean split:

  CS   = OML ∩ (nose_region ∪ aft_box_cs)      [rounded nose + aft body, inset]
  wing = OML − cove_region − aft_box_wing      [fixed structure with a cove]
  gap  = OML − wing − CS

CS ⊆ (removed-from-wing region), so wing ∩ CS = ∅ and volume is conserved by
set algebra (unchanged from P4-v1). Shards are filtered (F3). Scoped to
half-wing (mirror:false) configs so exactly 2 bodies result.

Construction is split into an EXPENSIVE, cacheable half and a CHEAP, always-
fresh half (test-architecture decision, changelog.md/docs/known_issues.md —
full gate runs were being used as a diagnostic loop for construction
questions, at ~minutes per hypothesis):

  build_te_cut_shapes()  ->  the real OCC booleans (lofts + fuzzy_cut/common),
                              timed per stage; this is what tests/geometry_cache.py
                              caches to disk (raw pre-shard-filter shapes, keyed
                              on config content + this module's own source, so
                              a code or config change invalidates automatically)
  finish_te_cut(raw)     ->  filter_shards + sort + gap-volume arithmetic —
                              cheap, ALWAYS recomputed fresh from the (possibly
                              cache-loaded) shapes, never itself cached, so F3
                              and every gate assertion runs on a real value
                              every time, cache hit or miss.
  cut_te_surface()       ->  build + finish, for callers that always want a
                              fresh uncached result (production/worker code,
                              the viewer export script).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_common, fuzzy_cut
from backend.geometry.cove_profile import (
    analytic_section_points,
    build_cove_arc_points,
    build_nose_arc_points,
    find_station_feet,
)
from backend.geometry.reference import build_hinge_axes
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

N_STATIONS = 24  # per-station profiles lofted along the device span

# Every module whose source affects build_te_cut_shapes's output (directly or
# via a function it calls) — the geometry build cache (tests/geometry_cache.py)
# hashes exactly these files alongside the config, so ANY change here silently
# invalidates every cache entry rather than risk a stale brep against new
# code. Update this list whenever the construction gains a new dependency.
GEOMETRY_SOURCE_FILES = [
    "backend/tolerances.py",
    "backend/geometry/reference.py",
    "backend/geometry/sections.py",
    "backend/geometry/cove_profile.py",
    "backend/geometry/booleans.py",
    "backend/geometry/te_cut.py",
]


@dataclass
class TeCutResult:
    wing: cq.Solid
    control_surface: cq.Solid
    gap_volume_mm3: float
    hinge_dir: np.ndarray  # unit hinge-axis direction
    n_wing_bodies: int
    n_cs_bodies: int
    shards: list  # solids filtered out (F3); gate asserts this is empty
    stations: list  # StationFeet at each y_frac (full span, cove), for gate re-verification
    stations_nose: list  # StationFeet at each nose station (gap-inset span)


@dataclass
class TeCutRawShapes:
    """The expensive, cacheable half of the construction: raw boolean outputs
    BEFORE filter_shards runs, plus the cheap per-station data computed along
    the way. `wing_shape`/`cs_shape` are what tests/geometry_cache.py persists
    as .brep; everything else here is fast enough (pure numpy/analytic, no
    OCC boolean — see cove_profile.py) that a cache wrapper can just recompute
    it on every call, hit or miss, instead of serializing it too."""

    wing_shape: cq.Shape
    cs_shape: cq.Shape
    stations: list
    stations_nose: list
    hinge_dir: np.ndarray
    oml_volume_mm3: float
    timings_s: dict = field(default_factory=dict)


def _vec(a: np.ndarray) -> cq.Vector:
    return cq.Vector(float(a[0]), float(a[1]), float(a[2]))


def hinge_frame(config: Config):
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


def _station_point(p0: np.ndarray, h: np.ndarray, s: float) -> np.ndarray:
    """Point on the hinge axis at arc-length s from p0."""
    return p0 + h * s


def _close_polygon(forward_arc: np.ndarray) -> np.ndarray:
    """Close an open forward-arc polyline (from Pl-side to Pu-side) into a
    simple polygon with a single straight chord back from the last point to
    the first — the chord sits aft of the arc's forward bulge, so the loop
    doesn't self-intersect."""
    return forward_arc  # cq.Wire.makePolygon(..., close=True) adds the chord


def _close_nose_polygon(forward_arc: np.ndarray, a: np.ndarray, aft_reach: float) -> np.ndarray:
    """Close the nose forward-arc, extending aft by `aft_reach` beyond the
    hinge so the resulting region genuinely overlaps aft_box_cs before the
    union (tolerances.NOSE_AFT_OVERLAP_MM) — without this, nose_region and
    aft_box_cs don't touch and .fuse() leaves 2 disjoint bodies."""
    p_l, p_u = forward_arc[0], forward_arc[-1]
    aft_vec = a * aft_reach
    return np.vstack([forward_arc, p_u + aft_vec, p_l + aft_vec])


def build_station_profiles(config: Config, sections: list) -> tuple[list, list, list, list]:
    """Returns (station_feet_cove, station_feet_nose, nose_polygons,
    cove_polygons). station_feet_cove/cove_polygons span the full device span
    [0, axis_len]; station_feet_nose/nose_polygons only cover the gap_mm-inset
    sub-span (spanwise clearance, unchanged from P4-v1) — the nose feet are
    returned (not just consumed locally) so the gate can re-verify the actual
    per-station construction the nose loft used, not just the cove stations.

    Sections analytically via the ruled-loft definition (fast; see
    cove_profile.py module docstring) rather than the real OCC boolean —
    `sections` is the half-span PlacedSection list build_planform_sections
    produced for the OML, required to be the SAME list (mirror:false devices)."""
    te = config.te_surface
    p0, p1, h, a, u, axis_len = hinge_frame(config)
    gap = te.gap_mm

    fracs_full = np.linspace(0.0, 1.0, N_STATIONS)
    s_full = fracs_full * axis_len
    s_inset = gap + fracs_full * (axis_len - 2 * gap)

    feet_full, cove_polys = [], []
    for s in s_full:
        C = _station_point(p0, h, s)
        pts = analytic_section_points(sections, C, h)
        feet = find_station_feet(pts, C, a, u)
        feet_full.append(feet)
        cove_polys.append(_close_polygon(build_cove_arc_points(feet, a, u)))

    aft_reach = gap + tolerances.NOSE_AFT_OVERLAP_MM
    feet_inset, nose_polys = [], []
    for s in s_inset:
        C = _station_point(p0, h, s)
        pts = analytic_section_points(sections, C, h)
        feet = find_station_feet(pts, C, a, u)
        feet_inset.append(feet)
        nose_polys.append(_close_nose_polygon(build_nose_arc_points(feet, a, u), a, aft_reach))

    return feet_full, feet_inset, nose_polys, cove_polys


def _loft_region(polygons: list[np.ndarray]) -> cq.Solid:
    wires = [cq.Wire.makePolygon([cq.Vector(*p) for p in poly], close=True) for poly in polygons]
    return cq.Solid.makeLoft(wires, ruled=True)


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


def _station_data(config: Config) -> dict:
    """The cheap half: hinge frame + per-station feet + loft-input polygons.
    Pure numpy/analytic (see cove_profile.py's ~0.4ms/call benchmark) — no
    OCC boolean — so it's fine to recompute this on every call, cache hit or
    miss, rather than serialize it alongside the expensive shapes below."""
    te = config.te_surface
    if te is None or not te.enabled:
        raise ValueError("config has no enabled te_surface")

    p0, p1, h, a, u, axis_len = hinge_frame(config)
    hinge_mid = (p0 + p1) / 2.0
    gap = te.gap_mm

    # Analytic sectioning needs the same half-span PlacedSection list the OML
    # was lofted from (mirror:false devices, per the existing scoping note).
    sections = build_planform_sections(config, config.airfoils.resample_points)
    feet_full, feet_nose, nose_polys, cove_polys = build_station_profiles(config, sections)
    return dict(
        p0=p0, p1=p1, h=h, a=a, u=u, axis_len=axis_len, hinge_mid=hinge_mid, gap=gap,
        feet_full=feet_full, feet_nose=feet_nose, nose_polys=nose_polys, cove_polys=cove_polys,
    )


def build_te_cut_shapes(config: Config, oml: cq.Solid) -> TeCutRawShapes:
    """The expensive, cacheable half: nose/cove lofts, aft boxes, and the two
    booleans that produce the raw (pre-shard-filter) wing/CS shapes. Timed
    per stage so a slow config is diagnosed by reading timings_s (the gate
    persists it to artifacts/gates/p04_timings.json), never by re-running the
    whole gate under a stopwatch."""
    t_start = time.perf_counter()
    timings: dict = {}

    sd = _station_data(config)
    timings["station_data_s"] = time.perf_counter() - t_start

    t0 = time.perf_counter()
    nose_region = _loft_region(sd["nose_polys"])
    cove_region = _loft_region(sd["cove_polys"])
    timings["loft_regions_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    box_len = 3.0 * max(s.chord_mm for s in config.planform.stations)
    box_h = box_len
    inset_span = sd["axis_len"] - 2 * sd["gap"]
    aft_box_wing = _aft_box(sd["hinge_mid"], sd["a"], sd["u"], box_len, box_h, sd["axis_len"], 0.0)
    aft_box_cs = _aft_box(sd["hinge_mid"], sd["a"], sd["u"], box_len, box_h, inset_span, sd["gap"])
    timings["aft_boxes_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    wing_shape = fuzzy_cut(fuzzy_cut(oml, cove_region), aft_box_wing)
    timings["wing_cut_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    cs_region = nose_region.fuse(aft_box_cs)
    timings["cs_fuse_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    cs_shape = fuzzy_common(oml, cs_region)
    timings["cs_common_s"] = time.perf_counter() - t0

    timings["total_s"] = time.perf_counter() - t_start

    return TeCutRawShapes(
        wing_shape=wing_shape,
        cs_shape=cs_shape,
        stations=sd["feet_full"],
        stations_nose=sd["feet_nose"],
        hinge_dir=sd["h"],
        oml_volume_mm3=oml.Volume(),
        timings_s=timings,
    )


def finish_te_cut(raw: TeCutRawShapes) -> TeCutResult:
    """The cheap half: F3 shard-filter + sort + gap-volume arithmetic. ALWAYS
    run fresh — on a cache hit this is the ONLY thing that runs — so F3 and
    every gate assertion computes its own value from the (possibly
    cache-loaded) shapes every time; nothing here is ever itself cached."""
    wing_solids, wing_shards = filter_shards(raw.wing_shape)
    cs_solids, cs_shards = filter_shards(raw.cs_shape)
    wing_solids.sort(key=lambda s: s.Volume(), reverse=True)
    cs_solids.sort(key=lambda s: s.Volume(), reverse=True)
    wing = wing_solids[0]
    cs = cs_solids[0]

    gap_volume = raw.oml_volume_mm3 - wing.Volume() - cs.Volume()
    return TeCutResult(
        wing=wing,
        control_surface=cs,
        gap_volume_mm3=gap_volume,
        hinge_dir=raw.hinge_dir,
        n_wing_bodies=len(wing_solids),
        n_cs_bodies=len(cs_solids),
        shards=wing_shards + cs_shards,
        stations=raw.stations,
        stations_nose=raw.stations_nose,
    )


def cut_te_surface(config: Config, oml: cq.Solid) -> TeCutResult:
    """Direct, uncached build+finish — for callers that always want a fresh
    result (production/worker pipeline, viewer export script). Gate tests go
    through tests/geometry_cache.py + build_te_cut_shapes/finish_te_cut
    instead, so an unchanged config+code hit skips the expensive half."""
    return finish_te_cut(build_te_cut_shapes(config, oml))
