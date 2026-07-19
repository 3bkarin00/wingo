"""D23 spar shape variants (plan.md §8.7 step 7a — WP2).

Shape-configurable spar bodies behind `spars[].shape`:

- `web`        — the original plain thickened-surface behavior, delegated
                 UNCHANGED to spar_trim.py (same blank, same trim boolean;
                 pre-D23 configs stay byte-identical).
- `c_channel`  — web + caps on ONE (aft) side, swept along the true
                 cap-path curves (P3 ruled spar surface ∩ cavity boundary).
- `i_beam`     — web + symmetric caps along the same cap paths.
- `box`        — twin webs offset ±web_spacing/2 chordwise + full-width
                 caps spanning both.
- `tube`       — lofted circular section along the straight root→tip spar
                 path at mid-depth, od validated against local internal
                 cavity depth at TUBE_DEPTH_VALIDATION_STATIONS stations.

CAP CONSTRUCTION (R0-verified technique, docs/r0_findings/p06_ext.md):
sampled frames + ruled loft, NOT a single OCC pipe sweep — place the cap
profile rectangle at SPAR_CAP_SWEEP_FRAMES frames along the cap-path curve
(tangent = curve tangent, normal = local cavity-boundary/IML surface normal
via GeomAPI_ProjectPointOnSurf + GeomLProp_SLProps per frame — the exact
per-point technique probe_offset_curve_surface.py validated) and loft
ruled=True. The cap-path curves themselves come from ONE
BRepAlgoAPI_Section(spar shell, hollow_interior) — the section loop is
split into upper/lower chains by comparing each sampled point's Z against
the spar's placed mid-height at that Y, after trimming
CAP_PATH_END_TRIM_FRAC off each spanwise end to discard the loop's
near-vertical root/tip closure segments.

Caps deliberately OVERLAP the web chordwise across its full thickness so
every fuzzy_fuse sees a genuine positive-volume intersection, never an
exact shared boundary (F4). Shard filter after every boolean (F3).

FOOTPRINT (single source for rib cutouts here and D25's interlock slots):
`spar_footprint(config, spar, y_mm, clearance_mm)` returns the spar's local
2D cross-section in the rib plane at y_mm as closed wires — web rect /
web+cap rects / twin webs+caps / circle. Clearance is applied by growing
the shapes in CANONICAL 2D space before placement (not wire.offset2D on
the placed wire, whose sign depends on wire orientation) so the growth
direction is correct by construction. Cap rects are oversized vertically
past the OML (same "generously oversized cutting tool" convention as
spar_trim.py's blank): where the core locally ramps out the true cap sits
CLOSER to the OML than the nominal stack predicts, and the oversize keeps
the cutout a superset of the real cap section there.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.BRep import BRep_Tool

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_common, fuzzy_cut, fuzzy_fuse
from backend.geometry.iml import face_sheet_thickness_mm
from backend.geometry.loft import build_section_wire
from backend.geometry.reference import build_spar_surfaces, get_canonical_points_at_xc
from backend.geometry.sections import PlacedSection, interp_station, le_and_z_offset, place_section
from backend.geometry.spar_trim import (
    SPAR_HEIGHT_OVERSIZE_CHORD_FRAC,
    _spar_blank,
    spar_web_thickness_mm,
)
from backend.schema.models import Config, Spar


@dataclass
class SparBody:
    name: str
    shape: str
    solid: cq.Shape
    web_thickness_mm: float
    timings_s: dict = field(default_factory=dict)


@dataclass
class FootprintPart:
    kind: str  # "web" | "cap" | "tube"
    wire: cq.Wire  # closed wire in the rib plane (global coords), clearance already applied


@dataclass
class SparFootprint:
    spar_name: str
    shape: str
    parts: list[FootprintPart]
    # WP2c consumers (interlock.py): the web region's chordwise center and
    # the Z interval available between cap inner faces, both in CANONICAL
    # unit-chord units at this station, plus the station's placement data —
    # enough to reconstruct tab rectangles in the same frame this module
    # placed the footprint in.
    web_xc_center: float | None = None
    web_z_interval: tuple[float, float] | None = None
    station: dict | None = None  # chord/twist/le_x/z_base/y_mm used for placement


def _station_at(config: Config, spar: Spar, y_mm: float) -> dict:
    """Interpolated station data at the rib plane's y (rib planes are all on
    the +y half span, reference.build_rib_planes)."""
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    y_frac = min(max(abs(y_mm) / half_span_mm, 0.0), 1.0)
    chord, twist, pts = interp_station(
        config, y_frac, config.airfoils.resample_points, config.airfoils.te_min_thickness_mm
    )
    xc = spar.xc_root + y_frac * (spar.xc_tip - spar.xc_root)
    zu, zl, zmid = get_canonical_points_at_xc(pts, xc)
    le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
    return {
        "y_mm": y_mm, "y_frac": y_frac, "chord": chord, "twist": twist,
        "xc": xc, "zu": zu, "zl": zl, "zmid": zmid, "le_x": le_x, "z_base": z_base,
    }


def _place_rect(config: Config, st: dict, x0: float, x1: float, z0: float, z1: float) -> cq.Wire:
    """Canonical (unit-chord) rectangle -> placed closed wire in the Y=y_mm
    plane, same placement math as every other per-station body."""
    corners = np.array([[x0, z0], [x1, z0], [x1, z1], [x0, z1]])
    placed = place_section(
        corners, st["chord"], st["twist"], config.planform.twist_axis_xc,
        y_mm=st["y_mm"], le_x_mm=st["le_x"], z_base_mm=st["z_base"],
    )
    return build_section_wire(placed)


def _stack_frac(config: Config, chord: float) -> float:
    """Nominal OML->cavity wall (face + core + face) as a chord fraction."""
    wall_mm = 2.0 * face_sheet_thickness_mm(config) + config.skin.core.thickness_mm
    return wall_mm / chord


def spar_footprint(
    config: Config, spar: Spar, y_mm: float, clearance_mm: float
) -> SparFootprint:
    """The spar's local cross-section footprint in the rib plane at y_mm,
    grown by clearance_mm on every side (module docstring). Single source
    for rib cutouts (D23) and interlock slots (D25)."""
    st = _station_at(config, spar, y_mm)
    chord = st["chord"]
    t = spar_web_thickness_mm(config, spar.name)
    c = clearance_mm / chord  # canonical clearance
    ht = (t / 2.0) / chord
    ov = SPAR_HEIGHT_OVERSIZE_CHORD_FRAC
    xc, zu, zl = st["xc"], st["zu"], st["zl"]
    stack = _stack_frac(config, chord)
    gap = (tolerances.PI_BOND_GAP_MM / chord) if spar.inside_iml else 0.0

    parts: list[FootprintPart] = []
    web_z_interval: tuple[float, float] | None = None

    def rect(kind: str, x0: float, x1: float, z0: float, z1: float) -> None:
        parts.append(FootprintPart(
            kind=kind, wire=_place_rect(config, st, x0 - c, x1 + c, z0 - c, z1 + c),
        ))

    if spar.shape == "web":
        rect("web", xc - ht, xc + ht, zl - ov, zu + ov)
        # The CUTOUT rect above is deliberately oversized past the cavity;
        # the METADATA interval below is the usable web height (nominal
        # cavity extent) — what D25 tab placement may actually occupy.
        web_z_interval = (zl + stack, zu - stack)

    elif spar.shape in ("c_channel", "i_beam"):
        cap_w = spar.cap_width_mm / chord
        cap_t = spar.cap_thickness_mm / chord
        cap_bot_u = zu - stack - gap - cap_t  # upper cap's inner (cavity-side) face, nominal
        cap_top_l = zl + stack + gap + cap_t
        rect("web", xc - ht, xc + ht, zl - ov, zu + ov)
        if spar.shape == "c_channel":
            x0, x1 = xc - ht, xc - ht + cap_w  # caps extend AFT (+x) from the web's fore face
        else:
            x0, x1 = xc - cap_w / 2.0, xc + cap_w / 2.0
        rect("cap", x0, x1, cap_bot_u, zu + ov)
        rect("cap", x0, x1, zl - ov, cap_top_l)
        web_z_interval = (cap_top_l, cap_bot_u)

    elif spar.shape == "box":
        s = spar.web_spacing_mm / chord
        cap_t = t / chord  # box caps reuse the web laminate thickness (schema adds no cap dims, D23)
        rect("web", xc - s / 2 - ht, xc - s / 2 + ht, zl - ov, zu + ov)
        rect("web", xc + s / 2 - ht, xc + s / 2 + ht, zl - ov, zu + ov)
        rect("cap", xc - s / 2 - ht, xc + s / 2 + ht, zu - stack - cap_t, zu + ov)
        rect("cap", xc - s / 2 - ht, xc + s / 2 + ht, zl - ov, zl + stack + cap_t)
        web_z_interval = (zl + stack + cap_t, zu - stack - cap_t)

    elif spar.shape == "tube":
        od = spar.od_root_mm + st["y_frac"] * (spar.od_tip_mm - spar.od_root_mm)
        center_canonical = np.array([[xc, st["zmid"]]])
        placed = place_section(
            center_canonical, chord, st["twist"], config.planform.twist_axis_xc,
            y_mm=st["y_mm"], le_x_mm=st["le_x"], z_base_mm=st["z_base"],
        )
        # Twist is a rotation about the spanwise axis, so a circle in the rib
        # plane stays a circle — radius in real mm, not chord-scaled.
        circle = cq.Wire.makeCircle(
            od / 2.0 + clearance_mm, cq.Vector(*placed[0]), cq.Vector(0, 1, 0)
        )
        parts.append(FootprintPart(kind="tube", wire=circle))

    else:  # pragma: no cover — schema Literal already forbids this
        raise ValueError(f"unknown spar shape {spar.shape!r}")

    return SparFootprint(
        spar_name=spar.name, shape=spar.shape, parts=parts,
        web_xc_center=None if spar.shape == "tube" else xc,
        web_z_interval=web_z_interval, station=st,
    )


def footprints_at(config: Config, y_mm: float, clearance_mm: float) -> list[SparFootprint]:
    return [spar_footprint(config, spar, y_mm, clearance_mm) for spar in config.spars]


# --------------------------------------------------------------------------
# Cap paths: spar ruled surface ∩ cavity boundary, split upper/lower
# --------------------------------------------------------------------------

def _cap_path_points(
    config: Config, spar: Spar, spar_shell: cq.Shell, hollow_interior: cq.Shape,
) -> tuple[np.ndarray, np.ndarray]:
    """(upper_pts, lower_pts) — each (N,3), sorted by Y — sampled from the
    intersection of the spar's ruled surface with the cavity boundary
    (module docstring)."""
    op = BRepAlgoAPI_Section(spar_shell.wrapped, hollow_interior.wrapped)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"spar {spar.name}: surface ∩ cavity section failed")
    edges = cq.Shape.cast(op.Shape()).Edges()
    if not edges:
        raise RuntimeError(f"spar {spar.name}: surface ∩ cavity produced no edges")

    pts = []
    per_edge = 12  # dense enough that resampling below is smooth; loop has O(sections) edges
    for e in edges:
        for i in range(per_edge + 1):
            pts.append(np.array(e.positionAt(i / per_edge).toTuple()))
    pts = np.array(pts)

    # Trim the loop's root/tip closure segments (near-constant-Y verticals).
    y_min, y_max = pts[:, 1].min(), pts[:, 1].max()
    trim = tolerances.CAP_PATH_END_TRIM_FRAC * (y_max - y_min)
    keep = (pts[:, 1] > y_min + trim) & (pts[:, 1] < y_max - trim)
    pts = pts[keep]

    # Split upper/lower against the spar's placed mid-height at each point's Y.
    upper, lower = [], []
    for p in pts:
        st = _station_at(config, spar, float(p[1]))
        mid = place_section(
            np.array([[st["xc"], st["zmid"]]]), st["chord"], st["twist"],
            config.planform.twist_axis_xc, y_mm=float(p[1]), le_x_mm=st["le_x"],
            z_base_mm=st["z_base"],
        )[0]
        (upper if p[2] >= mid[2] else lower).append(p)

    def _sorted_resampled(chain: list[np.ndarray]) -> np.ndarray:
        arr = np.array(sorted(chain, key=lambda q: q[1]))
        if len(arr) < 2:
            raise RuntimeError(f"spar {spar.name}: cap-path chain degenerate ({len(arr)} pts)")
        n = tolerances.SPAR_CAP_SWEEP_FRAMES
        ys = np.linspace(arr[0, 1], arr[-1, 1], n)
        out = np.column_stack([np.interp(ys, arr[:, 1], arr[:, k]) for k in range(3)])
        return out

    return _sorted_resampled(upper), _sorted_resampled(lower)


def _local_cavity_normal(
    cavity_faces: list[cq.Face], p: np.ndarray, toward: np.ndarray
) -> np.ndarray:
    """Unit normal of the cavity boundary at (the projection of) p, oriented
    to point from p toward the cavity interior (`toward`) — the per-point
    projection+normal technique probe_offset_curve_surface.py verified."""
    best = None
    pnt = cq.Vector(*p).toPnt()
    for face in cavity_faces:
        surf = BRep_Tool.Surface_s(face.wrapped)
        proj = GeomAPI_ProjectPointOnSurf(pnt, surf)
        if proj.NbPoints() == 0:
            continue
        d = proj.LowerDistance()
        if best is None or d < best[0]:
            u, v = proj.LowerDistanceParameters()
            props = GeomLProp_SLProps(surf, u, v, 1, 1e-6)
            if not props.IsNormalDefined():
                continue
            n = props.Normal()
            best = (d, np.array([n.X(), n.Y(), n.Z()]))
    if best is None:
        raise RuntimeError("no cavity face yielded a defined normal at cap-path point")
    nv = best[1]
    if np.dot(nv, toward - p) < 0:
        nv = -nv
    return nv / np.linalg.norm(nv)


def _swept_cap(
    config: Config, spar: Spar, path_pts: np.ndarray, cavity_faces: list[cq.Face],
    width_offsets: tuple[float, float], thickness_mm: float, standoff_mm: float,
) -> cq.Solid:
    """Loft the cap profile rectangle over sampled frames along path_pts.
    width_offsets are the profile's two chordwise extents (mm) along the
    frame binormal (oriented aft, +X-ish) relative to the path point;
    the profile spans depth [standoff, standoff+thickness] along the inward
    cavity normal."""
    n = len(path_pts)
    wires = []
    for i in range(n):
        p = path_pts[i]
        if i == 0:
            tang = path_pts[1] - path_pts[0]
        elif i == n - 1:
            tang = path_pts[-1] - path_pts[-2]
        else:
            tang = path_pts[i + 1] - path_pts[i - 1]
        tang = tang / np.linalg.norm(tang)

        st = _station_at(config, spar, float(p[1]))
        mid = place_section(
            np.array([[st["xc"], st["zmid"]]]), st["chord"], st["twist"],
            config.planform.twist_axis_xc, y_mm=float(p[1]), le_x_mm=st["le_x"],
            z_base_mm=st["z_base"],
        )[0]
        nrm = _local_cavity_normal(cavity_faces, p, mid)
        binorm = np.cross(tang, nrm)
        binorm = binorm / np.linalg.norm(binorm)
        if binorm[0] < 0:  # orient aft (+X) so one-sided (c_channel) caps pick a consistent side
            binorm = -binorm
        # Re-orthogonalize the normal so the profile plane is exact.
        nrm = np.cross(binorm, tang)
        nrm = nrm / np.linalg.norm(nrm)
        if np.dot(nrm, mid - p) < 0:
            nrm = -nrm

        c0, c1 = width_offsets
        d0, d1 = standoff_mm, standoff_mm + thickness_mm
        corners = [
            p + binorm * c0 + nrm * d0,
            p + binorm * c1 + nrm * d0,
            p + binorm * c1 + nrm * d1,
            p + binorm * c0 + nrm * d1,
        ]
        wires.append(cq.Wire.makePolygon([cq.Vector(*q) for q in corners], close=True))
    return cq.Solid.makeLoft(wires, ruled=True)


# --------------------------------------------------------------------------
# Per-shape body builders
# --------------------------------------------------------------------------

def _build_web_body(
    config: Config, spar: Spar, sections: list[PlacedSection], hollow_interior: cq.Shape,
    timings: dict,
) -> cq.Shape:
    t0 = time.perf_counter()
    thickness_mm = spar_web_thickness_mm(config, spar.name)
    blank = _spar_blank(config, sections, spar.xc_root, spar.xc_tip, thickness_mm)
    timings["blank_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    trimmed = fuzzy_common(blank, hollow_interior)
    timings["trim_s"] = time.perf_counter() - t0
    return trimmed


def _build_capped_body(
    config: Config, spar: Spar, sections: list[PlacedSection], hollow_interior: cq.Shape,
    timings: dict,
) -> cq.Shape:
    """c_channel / i_beam: web (unchanged construction) + swept caps."""
    web = _build_web_body(config, spar, sections, hollow_interior, timings)
    t = spar_web_thickness_mm(config, spar.name)

    t0 = time.perf_counter()
    shell = build_spar_surfaces(config, sections)[spar.name]
    upper_pts, lower_pts = _cap_path_points(config, spar, shell, hollow_interior)
    timings["cap_paths_s"] = time.perf_counter() - t0

    if spar.shape == "c_channel":
        offsets = (-t / 2.0, -t / 2.0 + spar.cap_width_mm)  # from web fore face, extending aft
    else:
        offsets = (-spar.cap_width_mm / 2.0, spar.cap_width_mm / 2.0)
    standoff = tolerances.PI_BOND_GAP_MM if spar.inside_iml else 0.0

    t0 = time.perf_counter()
    body = web
    for pts in (upper_pts, lower_pts):
        cap = _swept_cap(config, spar, pts, hollow_interior.Faces(), offsets,
                         spar.cap_thickness_mm, standoff)
        body = fuzzy_fuse(body, cap)
    timings["caps_s"] = time.perf_counter() - t0
    return body


def _build_box_body(
    config: Config, spar: Spar, sections: list[PlacedSection], hollow_interior: cq.Shape,
    timings: dict,
) -> cq.Shape:
    t = spar_web_thickness_mm(config, spar.name)
    s = spar.web_spacing_mm

    t0 = time.perf_counter()
    web_fore = fuzzy_common(
        _spar_blank(config, sections, spar.xc_root, spar.xc_tip, t, xc_offset_mm=-s / 2.0),
        hollow_interior,
    )
    web_aft = fuzzy_common(
        _spar_blank(config, sections, spar.xc_root, spar.xc_tip, t, xc_offset_mm=+s / 2.0),
        hollow_interior,
    )
    timings["webs_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    shell = build_spar_surfaces(config, sections)[spar.name]  # centerline surface
    upper_pts, lower_pts = _cap_path_points(config, spar, shell, hollow_interior)
    timings["cap_paths_s"] = time.perf_counter() - t0

    offsets = (-(s / 2.0 + t / 2.0), s / 2.0 + t / 2.0)  # span the full width across both webs
    t0 = time.perf_counter()
    body: cq.Shape = web_fore
    for pts in (upper_pts, lower_pts):
        # Box caps reuse the web laminate thickness (D23 schema adds no
        # separate cap dims for box).
        cap = _swept_cap(config, spar, pts, hollow_interior.Faces(), offsets, t, 0.0)
        body = fuzzy_fuse(body, cap)
    body = fuzzy_fuse(body, web_aft)
    timings["caps_s"] = time.perf_counter() - t0
    return body


def _validate_tube(config: Config, spar: Spar) -> None:
    """D23: od <= TUBE_OD_DEPTH_FRAC_MAX × local internal cavity depth,
    checked at TUBE_DEPTH_VALIDATION_STATIONS stations (analytic nominal
    stack — where the core ramps out the cavity only gets DEEPER, so the
    nominal check is the conservative one)."""
    worst = None
    for y_frac in np.linspace(0.0, 1.0, tolerances.TUBE_DEPTH_VALIDATION_STATIONS):
        chord, _twist, pts = interp_station(
            config, float(y_frac), config.airfoils.resample_points,
            config.airfoils.te_min_thickness_mm,
        )
        xc = spar.xc_root + y_frac * (spar.xc_tip - spar.xc_root)
        zu, zl, _ = get_canonical_points_at_xc(pts, xc)
        wall_mm = 2.0 * face_sheet_thickness_mm(config) + config.skin.core.thickness_mm
        depth_mm = (zu - zl) * chord - 2.0 * wall_mm
        od = spar.od_root_mm + y_frac * (spar.od_tip_mm - spar.od_root_mm)
        limit = tolerances.TUBE_OD_DEPTH_FRAC_MAX * depth_mm
        if od > limit and (worst is None or od - limit > worst[0]):
            worst = (od - limit, y_frac, od, depth_mm)
    if worst is not None:
        _over, y_frac, od, depth_mm = worst
        raise ValueError(
            f"spar '{spar.name}': tube od={od:.2f}mm at y_frac={y_frac:.2f} exceeds "
            f"{tolerances.TUBE_OD_DEPTH_FRAC_MAX:.0%} of the local internal depth "
            f"({depth_mm:.2f}mm -> max od {tolerances.TUBE_OD_DEPTH_FRAC_MAX * depth_mm:.2f}mm). "
            f"Reduce od_root_mm/od_tip_mm, move the spar to a thicker chordwise station, "
            f"or thicken the section."
        )


def _build_tube_body(
    config: Config, spar: Spar, sections: list[PlacedSection], hollow_interior: cq.Shape,
    timings: dict,
) -> cq.Shape:
    t0 = time.perf_counter()
    _validate_tube(config, spar)
    timings["validate_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    ends = []
    for sec, od in (
        (sections[0], spar.od_root_mm),
        (sections[-1], spar.od_tip_mm),
    ):
        st = _station_at(config, spar, sec.y_mm)
        placed = place_section(
            np.array([[st["xc"], st["zmid"]]]), st["chord"], st["twist"],
            config.planform.twist_axis_xc, y_mm=sec.y_mm, le_x_mm=st["le_x"],
            z_base_mm=st["z_base"],
        )
        ends.append((np.array(placed[0]), od))
    (p_root, od_root), (p_tip, od_tip) = ends
    axis = p_tip - p_root
    axis_dir = cq.Vector(*(axis / np.linalg.norm(axis)))

    def _loft(r_root: float, r_tip: float) -> cq.Solid:
        w0 = cq.Wire.makeCircle(r_root, cq.Vector(*p_root), axis_dir)
        w1 = cq.Wire.makeCircle(r_tip, cq.Vector(*p_tip), axis_dir)
        return cq.Solid.makeLoft([w0, w1], ruled=True)

    outer = _loft(od_root / 2.0, od_tip / 2.0)
    inner = _loft(od_root / 2.0 - spar.wall_mm, od_tip / 2.0 - spar.wall_mm)
    tube = fuzzy_cut(outer, inner)
    timings["loft_s"] = time.perf_counter() - t0
    # No IML trim: _validate_tube guarantees the tube sits fully inside the
    # cavity depth-wise (>= 40% headroom split above+below at mid-depth) and
    # the loft already ends at the root/tip section planes.
    return tube


_BUILDERS = {
    "web": _build_web_body,
    "c_channel": _build_capped_body,
    "i_beam": _build_capped_body,
    "box": _build_box_body,
    "tube": _build_tube_body,
}


def build_spar_bodies(
    config: Config, sections: list[PlacedSection], hollow_interior: cq.Shape
) -> list[SparBody]:
    """One shape-dispatched spar body per config.spars entry (D23). The
    `web` path is spar_trim's construction verbatim; all other shapes add
    to it or replace it per the module docstring."""
    result = []
    for spar in config.spars:
        timings: dict = {}
        t0 = time.perf_counter()
        body = _BUILDERS[spar.shape](config, spar, sections, hollow_interior, timings)
        kept, shards = filter_shards(body)
        if shards:
            raise RuntimeError(
                f"spar '{spar.name}' ({spar.shape}): {len(shards)} shard(s) after "
                f"construction booleans (F3)"
            )
        timings["total_s"] = time.perf_counter() - t0
        result.append(SparBody(
            name=spar.name, shape=spar.shape, solid=body,
            web_thickness_mm=spar_web_thickness_mm(config, spar.name),
            timings_s=timings,
        ))
    return result
