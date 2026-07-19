"""D25 tab-and-slot rib×spar interlock (plan.md §8.7 step 7c — WP2c).

Applies to web-bearing spar shapes ONLY (web / c_channel / i_beam), when
`structure.interlock.enabled` and not overridden off for a given rib via
`ribs.overrides`. Box/tube crossings and disabled crossings are NEVER
touched by this module — ribs.py falls straight through to the plain D23
cutout, so pre-D25 geometry there is byte-identical by construction.

RIB SIDE (`rib_cut_tool`, consumed by ribs.py's cutout step): the crossing's
cutout tool is the web footprint prism MINUS the tab prisms — the rib KEEPS
material at the tabs. Tabs are `tabs_per_crossing` rectangles,
`tab_width_mm` tall, distributed along the usable web height
(spars.SparFootprint.web_z_interval — between cap inner faces for C/I,
nominal cavity extent for plain web) with `edge_margin_mm` at both extremes
and equal gaps between. Each tab spans chordwise from beyond the tool's
near (fore) edge through to the FAR web face + `protrusion_mm` — so the tab
stays connected to the fore rib piece and its far face lands flush with
(protrusion 0) or proud of the far web face.

SPAR SIDE (`cut_slots`): per crossing, each tab's footprint grown by
`fit_clearance_mm` in the two in-web-plane directions (spanwise ±Y about
the rib midplane, heightwise ±Z-canonical about the tab band) is extruded
generously through the web chordwise and fuzzy_cut from the finished spar
body — cutting the REAL (possibly swept/tilted) web gives the true
prismatic intersection, never an assumed axis-aligned rectangle.

VALIDATION (P0-style, actionable): at every interlocked crossing, tabs +
margins must fit the usable web height; violations are collected across
all crossings and raised together.

All tab/slot rectangles are built in the same canonical unit-chord frame
spars.spar_footprint placed the footprint in (SparFootprint.station), so
tab and slot derive from the SAME single source as the plain cutout.
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

import numpy as np

from backend import tolerances
from backend.geometry.booleans import fuzzy_cut
from backend.geometry.face_registry import FaceRegistry
from backend.geometry.sections import place_section
from backend.geometry.spars import (
    SparFootprint,
    _place_rect,
    spar_footprint,
)
from backend.geometry.spar_trim import spar_web_thickness_mm
from backend.schema.models import Config, Spar

WEB_BEARING_SHAPES = ("web", "c_channel", "i_beam")


@dataclass
class TabBand:
    """One tab's z-band (canonical unit-chord units at the crossing station)."""
    z0: float
    z1: float


def interlock_active(
    config: Config, spar: Spar, rib_index: int, y_mm: float, rib_thickness_mm: float,
) -> bool:
    if not config.structure.interlock.enabled:
        return False
    if spar.shape not in WEB_BEARING_SHAPES:
        return False
    for ov in config.ribs.overrides:
        if ov.index == rib_index and not ov.interlock_enabled:
            return False
    # D25 implicitly assumes a CAPTURED tab — spar material on BOTH sides
    # of the slot (module docstring: "matching SLOTS in the spar web").
    # Every spar in this project spans the full root-to-tip Y range
    # (build_spar_bodies loops over all `sections`), so a rib sitting
    # within one slot half-extent of Y=0 or Y=half_span has no spar
    # material past its near end cap — found empirically
    # (probe_interlock_verify.py: the end wall genuinely doesn't exist
    # there, the spar's own solid stops short of it). Falls back to the
    # plain D23 cutout at those crossings, same posture as box/tube spars.
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    y_half = rib_thickness_mm / 2.0 + config.structure.interlock.fit_clearance_mm
    if y_mm - y_half <= 0.0 or y_mm + y_half >= half_span_mm:
        return False
    # D25 also assumes a simple flat rib slab either side of the tab —
    # found empirically (docs/r0_findings/p06_ext.md) that a crossing
    # inside the te_surface device window can instead follow the cove/
    # nose cut's curved boundary there (a spar whose xc sits near
    # hinge_xc, te_half.yaml's rear spar at xc=0.70 vs hinge_xc=0.75, was
    # affected while the same rib's main-spar crossing, farther from the
    # hinge, was not) — the tab's expected flat wall fragments into many
    # small curved facets instead of one clean plane. CONSERVATIVELY
    # excludes every crossing in the window (not just the affected spar),
    # same precedent as test_iml_min_wall_audit's own device-window vertex
    # exclusion. Precisely handling cove-adjacent tab/slot geometry is
    # follow-on work (handoff.md), not a P6 extension blocker.
    te = config.te_surface
    if te is not None and te.enabled:
        window_lo = te.span_start_frac * half_span_mm
        window_hi = te.span_end_frac * half_span_mm
        if window_lo <= y_mm <= window_hi:
            return False
    return True


def tab_bands(config: Config, fp: SparFootprint) -> list[TabBand]:
    """Tab z-bands for one crossing, from the footprint's usable web height.
    Raises ValueError (actionable) if tabs + margins don't fit."""
    il = config.structure.interlock
    chord = fp.station["chord"]
    z_lo, z_hi = fp.web_z_interval
    height_mm = (z_hi - z_lo) * chord
    margin = il.edge_margin_mm
    n = il.tabs_per_crossing
    needed = n * il.tab_width_mm + 2 * margin
    if needed > height_mm:
        raise ValueError(
            f"interlock: crossing rib_y={fp.station['y_mm']:.1f}mm × spar '{fp.spar_name}': "
            f"{n} tab(s) of {il.tab_width_mm}mm + 2×{margin}mm edge margin = {needed:.1f}mm "
            f"exceeds the usable web height {height_mm:.1f}mm. Reduce tabs_per_crossing/"
            f"tab_width_mm/edge_margin_mm, or disable interlock for this rib via ribs.overrides."
        )
    tab_w = il.tab_width_mm / chord
    m = margin / chord
    band_lo, band_hi = z_lo + m, z_hi - m
    if n == 1:
        centers = [(band_lo + band_hi) / 2.0]
    else:
        gap = ((band_hi - band_lo) - n * tab_w) / (n - 1)
        centers = [band_lo + tab_w / 2.0 + i * (tab_w + gap) for i in range(n)]
    return [TabBand(z0=c - tab_w / 2.0, z1=c + tab_w / 2.0) for c in centers]


def _prism(wire: cq.Wire, normal: cq.Vector, half_extent_mm: float) -> cq.Solid:
    shifted = wire.translate(normal.multiply(-half_extent_mm))
    return cq.Solid.extrudeLinear(shifted, [], normal.multiply(2 * half_extent_mm))


def _placed_point(config: Config, st: dict, xc: float, z: float) -> np.ndarray:
    return place_section(
        np.array([[xc, z]]), st["chord"], st["twist"], config.planform.twist_axis_xc,
        y_mm=st["y_mm"], le_x_mm=st["le_x"], z_base_mm=st["z_base"],
    )[0]


def tab_bond_registry(
    config: Config, spar: Spar, fp: SparFootprint, rib_thickness_mm: float,
    clearance_mm: float, registry: FaceRegistry,
) -> None:
    """Record the expected TAB SIDE faces (§8.8 naming:
    RIB<y>_SPAR<name>_TAB<k>_BOND_{LO,HI}) for one interlocked crossing into
    `registry` — called by ribs.py at cut time, matched against the finished
    rib after all cutouts. Each tab side face is the notch wall the cut tool
    leaves behind: it spans chordwise from the cutout tool's fore edge to
    the tab's far end, across the full rib thickness, at the band's z0/z1."""
    il = config.structure.interlock
    st = fp.station
    chord = st["chord"]
    t = spar_web_thickness_mm(config, spar.name)
    ht = (t / 2.0) / chord
    c = clearance_mm / chord
    xc = fp.web_xc_center
    x0 = xc - ht - c                      # cutout tool's fore edge
    x1 = xc + ht + il.protrusion_mm / chord  # tab far end
    for k, band in enumerate(tab_bands(config, fp)):
        for tag, z in (("LO", band.z0), ("HI", band.z1)):
            p_a = _placed_point(config, st, x0, z)
            p_b = _placed_point(config, st, x1, z)
            centroid = (p_a + p_b) / 2.0
            edge = p_b - p_a
            normal = np.cross(edge, np.array([0.0, 1.0, 0.0]))
            area = float(np.linalg.norm(edge)) * rib_thickness_mm
            registry.record(
                f"RIB{st['y_mm']:.0f}_SPAR{spar.name.upper()}_TAB{k}_BOND_{tag}",
                centroid, normal, area,
            )


def crossing_protect_wire(config: Config, spar: Spar, fp: SparFootprint) -> cq.Wire:
    """Placed rectangle covering every tab band's z-range (+ a small pad) at
    this crossing, in the same x0/x1 chordwise span rib_cut_tool's tab
    prisms use. Consumed by ribs.py's lightening-hole cut so it can carve a
    keep-out region around an interlocked crossing BEFORE cutting — found
    necessary empirically (probe_interlock_verify.py): the lightening
    hole's offset boundary can slice right through the gap between two
    adjacent tabs, fragmenting the tab's bond wall (the centroid registry
    correctly hard-failed on this — see docs/r0_findings/p06_ext.md).
    Non-interlocked crossings never call this — zero effect there."""
    il = config.structure.interlock
    st = fp.station
    chord = st["chord"]
    t = spar_web_thickness_mm(config, spar.name)
    ht = (t / 2.0) / chord
    xc = fp.web_xc_center
    x0 = xc - ht - 2.0 * (tolerances.SPAR_RIB_CUTOUT_CLEARANCE_MM / chord)
    x1 = xc + ht + il.protrusion_mm / chord
    bands = tab_bands(config, fp)
    pad = 2.0 / chord  # small real-mm pad, converted canonical — comfortably covers both tab edges
    z0 = min(b.z0 for b in bands) - pad
    z1 = max(b.z1 for b in bands) + pad
    return _place_rect(config, st, x0, x1, z0, z1)


def rib_cut_tool(
    config: Config, spar: Spar, fp: SparFootprint, web_part_wire: cq.Wire,
    normal: cq.Vector, rib_thickness_mm: float, clearance_mm: float,
) -> cq.Shape:
    """The interlocked crossing's rib cutout tool: web footprint prism minus
    the tab prisms (module docstring). `web_part_wire` is the plain D23
    cutout wire (already grown by clearance_mm) — the tool this replaces."""
    il = config.structure.interlock
    st = fp.station
    chord = st["chord"]
    t = spar_web_thickness_mm(config, spar.name)
    ht = (t / 2.0) / chord
    c = clearance_mm / chord
    xc = fp.web_xc_center

    tool = _prism(web_part_wire, normal, 1.5 * rib_thickness_mm)
    for band in tab_bands(config, fp):
        # Keep-region: from beyond the tool's fore edge through the far web
        # face + protrusion (flush at protrusion 0).
        x0 = xc - ht - 2 * c  # strictly fore of the tool's own fore edge
        x1 = xc + ht + il.protrusion_mm / chord
        tab_wire = _place_rect(config, st, x0, x1, band.z0, band.z1)
        tool = fuzzy_cut(tool, _prism(tab_wire, normal, 2.0 * rib_thickness_mm))
    return tool


def cut_slots(
    config: Config, spar: Spar, spar_solid: cq.Shape, rib_planes_y: list[float],
    rib_indices: list[int], rib_thickness_mm: float,
) -> tuple[cq.Shape, FaceRegistry]:
    """Cut every interlocked crossing's slots from the finished spar body.
    `rib_planes_y`/`rib_indices` parallel lists (build order). Validation
    errors from every crossing are collected and raised together. Also
    returns the slot-wall bond registry (§8.8 naming:
    SPAR<name>_RIB<y>_SLOT<k>_BOND_{IN,OUT}board — the slot's ±Y end walls,
    the faces the rib's tab bonds against), recorded at cut time; callers
    match it against the finished slotted body."""
    il = config.structure.interlock
    errors: list[str] = []
    y_normal = cq.Vector(0, 1, 0)
    registry = FaceRegistry()
    for y_mm, idx in zip(rib_planes_y, rib_indices):
        if not interlock_active(config, spar, idx, y_mm, rib_thickness_mm):
            continue
        fp = spar_footprint(config, spar, y_mm, 0.0)
        try:
            bands = tab_bands(config, fp)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        st = fp.station
        chord = st["chord"]
        t = spar_web_thickness_mm(config, spar.name)
        ht = (t / 2.0) / chord
        fc = il.fit_clearance_mm / chord
        xc = fp.web_xc_center
        # Chordwise span: generously through the web both ways (the same
        # oversized-tool convention as every other cut in this project);
        # the cut against the REAL web solid produces the true prismatic
        # intersection.
        x_over = 2.0 * (il.fit_clearance_mm + t) / chord
        y_half = rib_thickness_mm / 2.0 + il.fit_clearance_mm
        for k, band in enumerate(bands):
            slot_wire = _place_rect(
                config, st, xc - ht - x_over, xc + ht + x_over, band.z0 - fc, band.z1 + fc,
            )
            # slot_wire is already placed at y=y_mm (station data), so the
            # symmetric prism about it spans the rib thickness + clearance.
            tool = _prism(slot_wire, y_normal, y_half)
            spar_solid = fuzzy_cut(spar_solid, tool)
            # Expected ±Y end walls: prism end plane ∩ web = rect spanning
            # the web thickness chordwise × the slot's z height.
            p_a = _placed_point(config, st, xc - ht, (band.z0 + band.z1) / 2.0)
            p_b = _placed_point(config, st, xc + ht, (band.z0 + band.z1) / 2.0)
            height_mm = (band.z1 - band.z0 + 2 * fc) * chord
            width_mm = float(np.linalg.norm(p_b - p_a))
            for tag, y_off in (("IN", -y_half), ("OUT", y_half)):
                centroid = (p_a + p_b) / 2.0 + np.array([0.0, y_off, 0.0])
                registry.record(
                    f"SPAR{spar.name.upper()}_RIB{y_mm:.0f}_SLOT{k}_BOND_{tag}",
                    centroid, [0.0, 1.0, 0.0], width_mm * height_mm,
                )
    if errors:
        raise ValueError("interlock validation failed:\n- " + "\n- ".join(errors))
    return spar_solid, registry
