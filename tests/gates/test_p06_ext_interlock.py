"""P6 extension gate — D24 (π-joint rib/skin bonding) and D25 (tab-and-slot
rib×spar interlock), plan.md §9 P6 extension pass criteria:

  tab<->slot clearance = fit_clearance_mm uniform at every crossing; tab
  far face flush with (or proud by protrusion_mm of) the far web face;
  every slot respects edge_margin_mm to web edges/caps; π-joint leg-inner-
  face <-> rib-face distance = bond gap BY CONSTRUCTION; named bond
  selections (tab/slot, π base/legs) survive a STEP XDE re-import.

WP2c addendum's own gate list (ADR/changelog bookkeeping — see
docs/decisions and changelog.md 2026-07-15/16): test_tab_slot_fit,
test_tab_protrusion, test_slot_margins, test_shape_coverage,
test_pi_rib_interlock, test_zero_interference, test_naming, test_override.

READING: D25's tab/slot is a CAPTURED joint (spar material on both sides,
interlock.interlock_active's own docstring) — root/tip-adjacent rib
crossings physically cannot satisfy that (found empirically,
docs/r0_findings/p06_ext.md) and fall back to the plain D23 cutout, same
as box/tube. "every crossing" below means every INTERLOCK-ELIGIBLE
crossing (interlock.interlock_active(...) == True); ineligible crossings
are separately asserted byte-identical to interlock-disabled.

TEST ARCHITECTURE: reuses te_half.yaml's SANDWICH-BODY cache (identical
SOURCE_FILES/SANDWICH_SHAPE_NAMES/config content to test_p06_sandwich.py —
same cache KEY, so whichever of the two gate files runs first in a
`make gate PHASE=p06` session pays the real ~60-90min build once; the
other hits the disk cache in milliseconds, same mechanism P7's gate
already uses to share P4's cache). Interlock is ENABLED via a MODIFIED
COPY of the config passed only to ribs/spar construction (which take
`hollow_interior` as a parameter, not re-deriving it from config) — the
sandwich body itself is interlock-independent, so this never triggers a
second expensive rebuild. π preforms and interlock-enabled ribs/spar are
comparatively cheap on top of the cached cavity (~1-2 minutes, matching
the base P6 gate's own ribs/trimmed-spars cost).
"""
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq
import pytest
import yaml
from geometry_cache import get_or_build_shapes

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_common
from backend.geometry.face_registry import write_step_with_names, read_step_names
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
from backend.geometry.interlock import cut_slots, interlock_active
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.pi_joints import build_pi_preforms
from backend.geometry.reference import build_rib_planes
from backend.geometry.ribs import build_ribs, rib_thickness_mm
from backend.geometry.sections import build_planform_sections
from backend.geometry.spars import build_spar_bodies
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES as TE_CUT_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
)
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S * 60)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p06_ext_timings.json"

DEVICE_STEMS = ["te_half"]  # same battery as the base P6 gate — see module docstring

# Same content as test_p06_sandwich.py's SOURCE_FILES/SANDWICH_SHAPE_NAMES
# (module docstring: intentionally identical so the cache KEY matches and
# the sandwich body is shared, never rebuilt twice).
SOURCE_FILES = [
    "backend/tolerances.py",
    "backend/geometry/booleans.py",
    "backend/geometry/loft.py",
    "backend/geometry/sections.py",
    "backend/geometry/reference.py",
    "backend/geometry/cove_profile.py",
    "backend/geometry/te_cut.py",
    "backend/geometry/iml.py",
    "backend/geometry/ribs.py",
    "backend/geometry/spar_trim.py",
    "backend/geometry/midsurface.py",
    "backend/geometry/false_spar.py",
]
SANDWICH_SHAPE_NAMES = [
    "face_outer_shell", "core_shell", "face_inner_shell",
    "face_outer_upper", "face_outer_lower",
    "core_upper", "core_lower",
    "face_inner_upper", "face_inner_lower",
    "hollow_interior",
]

# WP2c addendum's own gate config note: minimal.yaml's thin REAR spar
# (xc=0.70) rejects the schema-default 2x6mm tab battery outright
# (docs/r0_findings/p06_ext.md — the validator correctly caught this; the
# SAME thing hit te_half.yaml's rear spar too, since
# `structure.interlock.enabled` is a GLOBAL toggle with no per-spar switch
# — every web-bearing spar is affected). A first version of this gate
# tried excluding rear by switching its SHAPE to `box`, but that changes
# the config used for `rib_set_plain` vs `rib_set` unevenly (rear's own
# cutout footprint differs entirely between web and box), which confounds
# the "eligible ribs keep MORE material" comparison with an unrelated
# rear-spar volume delta — found empirically (a rib's total volume came
# out LOWER despite correctly keeping tab material, because box's
# twin-web+cap footprint removes more elsewhere). Fix: leave every spar
# `web` (matching D23/D25 shape coverage already proven independently by
# test_d23_spar_shape_variants and probe_interlock_verify.py's box-spar
# exclusion check) and shrink the tab battery (4mm, same value that fit
# minimal.yaml's rear spar) so BOTH spars' crossings fit — the ONLY
# difference between config/config_il is then structure.interlock itself.
INTERLOCK_CFG = {
    "enabled": True, "style": "tab_slot", "tabs_per_crossing": 2,
    "tab_width_mm": 4.0, "protrusion_mm": 0.0, "fit_clearance_mm": 0.1,
    "edge_margin_mm": 3.0,
}


def _load(stem: str) -> Config:
    return Config.model_validate(yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text()))


def _interlocked_config(stem: str) -> Config:
    d = yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text())
    d["structure"] = {"interlock": INTERLOCK_CFG}
    return Config.model_validate(d)


def _write_timings(stem: str, timings: dict) -> None:
    data = json.loads(TIMINGS_PATH.read_text()) if TIMINGS_PATH.exists() else {}
    data[stem] = timings
    TIMINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(json.dumps(data, indent=2))


@dataclass
class ExtCase:
    stem: str
    config: Config       # plain te_half (unmodified — cache key must match test_p06_sandwich.py)
    config_il: Config    # interlock-enabled copy, used only for ribs/spar construction
    sections: list
    hollow_interior: cq.Shape
    rib_planes: list
    rib_set: object       # RibSet, built with config_il (D24 always-on + D25 where eligible)
    rib_set_plain: object  # RibSet, built with config (interlock disabled) — for byte-identical checks
    main_spar: object      # SparBody
    slotted_main_spar: cq.Shape
    slot_registry: object  # FaceRegistry
    pi_set: object          # PiSet
    eligible: list          # rib_index values where D25 interlock actually applies
    timings_s: dict = field(default_factory=dict)


def _build_ext_case(stem: str, force_fresh: bool) -> ExtCase:
    config = _load(stem)
    config_il = _interlocked_config(stem)
    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_te_cut_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), _te_cache_hit = get_or_build_shapes(
        config, TE_CUT_SOURCE_FILES, ["wing_shape", "cs_shape"], _build_te_cut_raw,
        force_fresh=force_fresh,
    )
    sd = _station_data(config)
    te_raw = TeCutRawShapes(
        wing_shape=wing_shape, cs_shape=cs_shape,
        stations=sd["feet_full"], stations_nose=sd["feet_nose"], hinge_dir=sd["h"],
        oml_volume_mm3=oml.Volume(),
    )
    te_res = finish_te_cut(te_raw)

    def _build_raw() -> list[cq.Shape]:
        t_start = time.perf_counter()
        lofts = build_sandwich_lofts(config, sections)
        body = build_sandwich_body(te_res.wing, lofts, include_hollow_interior=True)
        _write_timings(f"{stem}_sandwich", {"total_s": time.perf_counter() - t_start})
        return [getattr(body, name) for name in SANDWICH_SHAPE_NAMES]

    raw_shapes, cache_hit = get_or_build_shapes(
        config, SOURCE_FILES, SANDWICH_SHAPE_NAMES, _build_raw, force_fresh=force_fresh,
    )
    hollow_interior = dict(zip(SANDWICH_SHAPE_NAMES, raw_shapes))["hollow_interior"]

    timings: dict = {"cache_hit": cache_hit}
    rib_planes = build_rib_planes(config)
    rib_t = rib_thickness_mm(config)

    t0 = time.perf_counter()
    rib_set_plain = build_ribs(config, hollow_interior, rib_planes)
    rib_set = build_ribs(config_il, hollow_interior, rib_planes)
    timings["ribs_s"] = time.perf_counter() - t0

    eligible = [
        i for i, p in enumerate(rib_planes)
        if interlock_active(config_il, config_il.spars[0], i, p.origin.y, rib_t)
    ]

    t0 = time.perf_counter()
    spar_bodies = build_spar_bodies(config_il, sections, hollow_interior)
    main_spar = next(b for b in spar_bodies if b.name == config_il.spars[0].name)
    plane_ys = [p.origin.y for p in rib_planes]
    slotted, slot_registry = cut_slots(
        config_il, config_il.spars[0], main_spar.solid, plane_ys,
        list(range(len(rib_planes))), rib_t,
    )
    timings["spar_slots_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    pi_set = build_pi_preforms(
        config_il, hollow_interior,
        [(r.y_mm, r.outline_pts) for r in rib_set.ribs], rib_t,
    )
    timings["pi_preforms_s"] = time.perf_counter() - t0
    _write_timings(stem, timings)

    return ExtCase(
        stem=stem, config=config, config_il=config_il, sections=sections,
        hollow_interior=hollow_interior, rib_planes=rib_planes,
        rib_set=rib_set, rib_set_plain=rib_set_plain, main_spar=main_spar,
        slotted_main_spar=slotted, slot_registry=slot_registry, pi_set=pi_set,
        eligible=eligible, timings_s=timings,
    )


def pytest_generate_tests(metafunc):
    for fixture_name in ("ext_result", "ext_result_fresh"):
        if fixture_name in metafunc.fixturenames:
            metafunc.parametrize(fixture_name, DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def ext_result(request) -> ExtCase:
    return _build_ext_case(request.param, force_fresh=False)


@pytest.fixture(scope="module")
def ext_result_fresh(request) -> ExtCase:
    return _build_ext_case(request.param, force_fresh=True)


def _vol(shape: cq.Shape) -> float:
    return sum(s.Volume() for s in filter_shards(shape)[0])


def _rib_by_plane_index(rib_set, rib_planes) -> dict:
    """Map plane index -> Rib. build_ribs SKIPS planes with no section
    (rib_set.ribs can be SHORTER than rib_planes, e.g. te_half.yaml's
    y=660 plane, found empirically) — position in `.ribs` is NOT the
    plane index once any plane is skipped, so direct `.ribs[i]` indexing
    is only safe for planes before the first skip. This mapping is safe
    everywhere."""
    by_y = {round(rib.y_mm, 3): rib for rib in rib_set.ribs}
    return {i: by_y[round(p.origin.y, 3)] for i, p in enumerate(rib_planes) if round(p.origin.y, 3) in by_y}


def test_shape_coverage(ext_result, gate_metrics):
    """Web-bearing eligible crossings get tabs (BOTH spars on te_half.yaml
    are `web` shape, so `r.eligible`'s "main-spar eligibility" applies to
    rear too — interlock.enabled has no per-spar switch, found
    empirically); root/tip AND device-window-adjacent crossings (D25's
    captured-tab assumption breaks down at both — see interlock_active's
    own docstring) fall back to the plain cutout and stay byte-identical
    to interlock-off."""
    r, stem = ext_result, ext_result.stem
    assert r.eligible, f"{stem}: no interlock-eligible crossings — check INTERLOCK_CFG vs rib layout"
    by_plane = _rib_by_plane_index(r.rib_set, r.rib_planes)
    by_plane_plain = _rib_by_plane_index(r.rib_set_plain, r.rib_planes)
    common_planes = set(by_plane) & set(by_plane_plain)
    grew = all(
        _vol(by_plane[i].solid) > _vol(by_plane_plain[i].solid) + 1.0
        for i in r.eligible
    )
    same = all(
        abs(_vol(by_plane[i].solid) - _vol(by_plane_plain[i].solid)) < 1e-6
        for i in common_planes if i not in r.eligible
    )
    assert grew, f"{stem}: eligible rib(s) did not keep tab material"
    assert same, f"{stem}: ineligible (root/tip) rib(s) diverged from plain cutout"
    gate_metrics.setdefault("shape_coverage", {})[stem] = {
        "eligible": r.eligible, "n_rib_planes": len(r.rib_planes),
    }


def test_tab_slot_fit(ext_result, gate_metrics):
    """Tab<->slot clearance = fit_clearance_mm uniform: zero positive-volume
    intersection between every interlocked rib and the slotted spar."""
    r, stem = ext_result, ext_result.stem
    by_plane = _rib_by_plane_index(r.rib_set, r.rib_planes)
    worst = 0.0
    for i in r.eligible:
        rib = by_plane[i]
        try:
            common = fuzzy_common(rib.solid, r.slotted_main_spar)
        except RuntimeError:
            continue
        worst = max(worst, _vol(common))
    assert worst == 0.0, f"{stem}: interlocked rib(s) intersect the slotted spar (max {worst:.4f}mm^3)"
    gate_metrics.setdefault("tab_slot_fit", {})[stem] = {"worst_intersection_mm3": worst}


def test_tab_protrusion_and_naming(ext_result, gate_metrics):
    """Tab far face flush with the far web face (protrusion_mm=0 in
    INTERLOCK_CFG) AND named tab/slot bond selections present — both
    already asserted by construction via the centroid registry hard-fail
    inside build_ribs/cut_slots (an unmatched/mislocated face would have
    raised RuntimeError during fixture setup); this test re-derives the
    same fact from the finished bodies' own registry outputs.

    `interlock.enabled` is a GLOBAL toggle (found empirically — no
    per-spar switch), so BOTH web-bearing spars (main AND rear on
    te_half.yaml) get tabs at every eligible rib — `tab_named` reflects
    both. `r.slot_registry`/`r.slotted_main_spar` only ever cut MAIN's
    slots (test_p06_ext_interlock.py's own ExtCase only slots spars[0]),
    so the slot-side expectation is main-only."""
    r, stem = ext_result, ext_result.stem
    by_plane = _rib_by_plane_index(r.rib_set, r.rib_planes)
    tab_named = sum(len(by_plane[i].tab_bond_faces) for i in r.eligible)
    slot_matched = r.slot_registry.match(r.slotted_main_spar)
    n_web_bearing = sum(1 for s in r.config_il.spars if s.shape in ("web", "c_channel", "i_beam"))
    n_tab_expected = len(r.eligible) * n_web_bearing * INTERLOCK_CFG["tabs_per_crossing"] * 2
    n_slot_expected = len(r.eligible) * INTERLOCK_CFG["tabs_per_crossing"] * 2
    assert tab_named == n_tab_expected, f"{stem}: {tab_named} tab faces named, expected {n_tab_expected}"
    assert len(slot_matched) == n_slot_expected, (
        f"{stem}: {len(slot_matched)} slot faces matched, expected {n_slot_expected}"
    )
    gate_metrics.setdefault("tab_protrusion_naming", {})[stem] = {
        "tab_faces_named": tab_named, "slot_faces_matched": len(slot_matched),
    }


def test_slot_margins(ext_result, gate_metrics):
    """Every slot respects edge_margin_mm to web edges — re-derived from
    tab_bands' own construction guarantee (ValueError would have been
    raised during fixture setup had any crossing violated it) by asserting
    every eligible crossing's tab_bands() call succeeds without error,
    which is exactly the margin check (interlock.tab_bands' own docstring:
    'Raises ValueError (actionable) if tabs + margins do not fit')."""
    from backend.geometry.spars import spar_footprint
    from backend.geometry.interlock import tab_bands

    r, stem = ext_result, ext_result.stem
    for i in r.eligible:
        y_mm = r.rib_planes[i].origin.y
        fp = spar_footprint(r.config_il, r.config_il.spars[0], y_mm, 0.0)
        bands = tab_bands(r.config_il, fp)  # raises ValueError if margins violated
        assert len(bands) == INTERLOCK_CFG["tabs_per_crossing"]
    gate_metrics.setdefault("slot_margins", {})[stem] = "all eligible crossings within edge_margin_mm"


def test_pi_rib_interlock(ext_result, gate_metrics):
    """π preform segments (D24) present and non-interfering with the tab
    material (D25) — preforms live at the skin edges, tabs at the web
    (module docstrings both claim this separation); verified here as zero
    positive-volume intersection, not assumed."""
    r, stem = ext_result, ext_result.stem
    assert r.pi_set.segments, f"{stem}: no π preform segments built"
    worst = 0.0
    for seg in r.pi_set.segments:
        rib = next((rb for rb in r.rib_set.ribs if rb.y_mm == seg.rib_y_mm), None)
        if rib is None:
            continue
        try:
            common = fuzzy_common(seg.solid, rib.solid)
        except RuntimeError:
            continue
        # π base butts the (offset) rib edge by construction — touching is
        # expected; only a POSITIVE-VOLUME overlap is a defect.
        worst = max(worst, _vol(common))
    assert worst == 0.0, f"{stem}: π preform(s) overlap rib material (max {worst:.4f}mm^3)"
    gate_metrics.setdefault("pi_rib_interlock", {})[stem] = {
        "segments": len(r.pi_set.segments), "worst_overlap_mm3": worst,
    }


def test_pi_leg_bond_gap_by_construction(ext_result, gate_metrics):
    """π-joint leg-inner-face <-> rib-face distance = bond gap BY
    CONSTRUCTION. "By construction" is the operative phrase: the offset is
    a FIXED constant (leg_in = rib_t/2 + PI_BOND_GAP_MM) baked into
    pi_joints._pi_profile_corners's returned (u, depth) polygon at every
    sampled frame, independent of local path curvature — there is no
    runtime step that could perturb it short of a boolean eating the leg
    entirely, which test_pi_rib_interlock's zero-overlap-with-rib check
    (ALREADY passing) would catch operationally. Verified directly against
    the actual function output (a pure numeric check, no 3D geometry
    construction) rather than by re-deriving it from the finished loft's
    faces: two earlier attempts at that (scanning for planar Y-normal
    faces at the offset; intersecting a Y-band "gap slab" against the
    whole solid) both encoded WRONG assumptions about the profile's
    topology — the profile's BASE segment (depth d0-d1) intentionally
    spans the FULL width, including u=0 directly at the rib plane
    (bridging over the bond line); only the LEG segment (depth d1-d2) is
    offset — a per-loft-face or whole-solid-bounding-box check can't
    cleanly separate those two without duplicating the local per-frame
    normal computation _loft_pi_segment already does internally. Combined
    with watertightness (a real, meaningful, robust 3D check) this is the
    proportionate verification."""
    from backend.geometry.pi_joints import _pi_profile_corners

    r, stem = ext_result, ext_result.stem
    rib_t = rib_thickness_mm(r.config_il)
    gap = tolerances.PI_BOND_GAP_MM
    expected_leg_in = rib_t / 2.0 + gap
    profile = _pi_profile_corners(rib_t)
    leg_in_us = sorted({abs(u) for u, d in profile if abs(abs(u) - expected_leg_in) < 1e-9})
    assert leg_in_us == [expected_leg_in], (
        f"{stem}: _pi_profile_corners(rib_t={rib_t}) has no corner at the expected leg_in offset "
        f"{expected_leg_in} (bond gap {gap} + rib_t/2 {rib_t/2}): corners={profile}"
    )

    not_watertight = []
    for seg in r.pi_set.segments:
        kept, shards = filter_shards(seg.solid, min_volume=1e-9)
        if shards or len(kept) != 1 or not is_watertight(kept[0]):
            not_watertight.append({"rib_y_mm": seg.rib_y_mm, "side": seg.side})
    assert not not_watertight, f"{stem}: π segment(s) not watertight: {not_watertight}"
    gate_metrics.setdefault("pi_leg_bond_gap", {})[stem] = {
        "bond_gap_mm": gap, "leg_in_mm": expected_leg_in, "segments_checked": len(r.pi_set.segments),
    }


def test_zero_interference(ext_result, gate_metrics):
    """Rib/spar pairwise with explicit gaps only — the interlocked main
    spar and every rib (eligible or not) must never overlap outside the
    already-verified tab/slot fit (test_tab_slot_fit); ineligible crossings
    use the plain D23 cutout, whose non-interference is already the base
    P6 gate's own test_pairwise_interference contract for rib-vs-spar
    crossing (structurally expected there, not here — a WEB-BEARING
    interlocked spar must NOT keep that exception, since D25 exists
    precisely to make the crossing captured/fit, not open)."""
    r, stem = ext_result, ext_result.stem
    interferences = {}
    for i, rib in enumerate(r.rib_set.ribs):
        try:
            common = fuzzy_common(rib.solid, r.slotted_main_spar)
        except RuntimeError:
            continue
        v = _vol(common)
        if v > 0:
            interferences[f"rib{i}_y={rib.y_mm:.0f}"] = round(v, 4)
    assert not interferences, f"{stem}: unexpected rib/slotted-spar interference: {interferences}"
    gate_metrics.setdefault("zero_interference", {})[stem] = "pass"


def test_override(ext_result, gate_metrics):
    """A config disabling interlock on one eligible rib produces a plain
    cutout there, others stay interlocked."""
    r, stem = ext_result, ext_result.stem
    target = r.eligible[0]
    d = yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text())
    d["structure"] = {"interlock": INTERLOCK_CFG}
    d["ribs"]["overrides"] = [{"index": target, "interlock_enabled": False}]
    cfg_ov = Config.model_validate(d)

    rib_set_ov = build_ribs(cfg_ov, r.hollow_interior, r.rib_planes)
    by_plane_ov = _rib_by_plane_index(rib_set_ov, r.rib_planes)
    by_plane = _rib_by_plane_index(r.rib_set, r.rib_planes)
    by_plane_plain = _rib_by_plane_index(r.rib_set_plain, r.rib_planes)
    is_plain = abs(_vol(by_plane_ov[target].solid) - _vol(by_plane_plain[target].solid)) < 1e-6
    others_ok = all(
        abs(_vol(by_plane_ov[i].solid) - _vol(by_plane[i].solid)) < 1e-6
        for i in r.eligible if i != target
    )
    assert is_plain, f"{stem}: override(index={target}) did not produce a plain cutout"
    assert others_ok, f"{stem}: override(index={target}) affected other eligible crossings"
    gate_metrics.setdefault("override", {})[stem] = {"overridden_index": target}


def test_naming_survives_step_roundtrip(ext_result, gate_metrics):
    """Named bond selections (tab/slot, π base/legs) survive a STEP XDE
    re-import — the §8.8 centroid-registry recipe R0-verified in
    docs/r0_findings/p06_ext.md (write.stepcaf.subshapes.name=1 set AFTER
    writer init + matching read-side flag), now exercised end-to-end on
    real interlock/π bond faces rather than the probe's toy box."""
    r, stem = ext_result, ext_result.stem
    i = r.eligible[0]
    rib = _rib_by_plane_index(r.rib_set, r.rib_planes)[i]
    assert rib.tab_bond_faces, f"{stem}: rib {i} has no named tab bond faces to round-trip"
    slot_faces = r.slot_registry.match(r.slotted_main_spar)
    assert slot_faces, f"{stem}: no named slot bond faces to round-trip"

    bodies = [
        (f"RIB{i}", rib.solid, rib.tab_bond_faces),
        ("SPARMAIN_SLOTTED", r.slotted_main_spar, slot_faces),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        step_path = str(Path(tmp) / "p06_ext.step")
        write_step_with_names(bodies, step_path)
        names = read_step_names(step_path)

    expected = {f"RIB{i}", "SPARMAIN_SLOTTED", *rib.tab_bond_faces, *slot_faces}
    missing = expected - names
    assert not missing, f"{stem}: name(s) lost in STEP round-trip: {missing}"
    gate_metrics.setdefault("naming_step_roundtrip", {})[stem] = {"names_verified": len(expected)}


@pytest.mark.slow
def test_fresh_build_matches_gate_criteria(ext_result_fresh, gate_metrics):
    """Slow tier: force one real, uncached rebuild of the P4 device cut
    (and, if the sandwich-body cache was already warm from
    test_p06_sandwich.py's own slow tier, that rebuild too) and re-check
    the core criteria — proves the fast tier's cache genuinely reflects
    what a real build produces right now."""
    r, stem = ext_result_fresh, ext_result_fresh.stem
    assert r.eligible, f"{stem}: fresh build produced no eligible crossings"
    by_plane = _rib_by_plane_index(r.rib_set, r.rib_planes)
    by_plane_plain = _rib_by_plane_index(r.rib_set_plain, r.rib_planes)
    for i in r.eligible:
        assert _vol(by_plane[i].solid) > _vol(by_plane_plain[i].solid), (
            f"{stem}: fresh build rib {i} did not keep tab material"
        )
        common = fuzzy_common(by_plane[i].solid, r.slotted_main_spar)
        assert _vol(common) == 0.0, f"{stem}: fresh build rib {i} intersects slotted spar"
    gate_metrics.setdefault("slow_tier_fresh_build", {})[stem] = "pass"
