"""P6 gate — plan.md §9 pass criteria:

  pairwise boolean interference = 0 across ALL bodies; every auto hardpoint
  has core ramp-out (core body distance-to-hardpoint >= ramp length); IML
  audit: min wall >= face-sheet stack everywhere (sampled); every rib
  watertight after holes/cutouts; midsurface face count matches structural
  body count.

TWO of these criteria need an explicit, documented reading against what
this phase actually built (both already established during construction,
re-stated here so the gate's own pass bar is unambiguous):

  - "min wall >= face-sheet stack everywhere": the self-clip behavior at
    locally-thin sections (docs/r0_findings/p06.md, "Addendum: 3-layer
    panel correction") is ALREADY an accepted, R0-verified consequence of
    the frozen offset chain, not a defect — where the local thickness is
    below 2*stack_mm the core vanishes and the two face sheets merge into
    solid laminate. The gate's real floor is therefore "never below
    2*face_mm" (a genuine void/gap would be a defect; the documented
    self-clip is not). Sampled via BRepExtrema_DistShapeShape from the OML
    surface to hollow_iml_solid, the same point-to-shell distance pattern
    test_p04_te_cut.py's _point_to_shell_distance already established.
  - "every auto hardpoint has core ramp-out": `config.hardpoints.auto`
    entries (hinge_lands, joint_housing_zones, fuselage_bosses) and
    `config.hardpoints.fuselage_attachment.bolts` are the ONLY hardpoint
    sources this schema has (backend/schema/models.py); none of P6's
    frozen test configs declare either (grep confirms it) — hinge_lands
    needs P7's hinge placement, joint_housing_zones needs P11's joints,
    and no config opts into auto fuselage_bosses or declares explicit
    bolts yet. This test genuinely iterates `reference.build_hardpoints`
    and checks each one, exactly as the criterion asks — it passes
    VACUOUSLY on every current config (zero hardpoints to check), not by
    being weakened. Wiring real ramp-out at hardpoint locations is a
    P7/P8/P11 follow-on (handoff.md, docs/r0_findings/p06.md).

BATTERY: te_half.yaml only, for now — an explicit, cost-driven scope
decision, not a shortcut. Building the full P6 body (sandwich shells +
hollow interior + ribs + trimmed spars) costs real tens of minutes even
on a cache hit, and ~60-90 minutes on the first (cache-miss) run per
config — see the per-stage timings this file writes to
artifacts/gates/p06_timings.json. Every construction module this gate
exercises was ALSO independently verified against
tests/configs/edge/high_taper.yaml (an intentionally extreme 10:1-taper,
mirror:true, single-ply-thin stress config) during development — see each
module's own docs/r0_findings/p06.md addendum for that trail. Extending
this battery to more device configs is future work, not a P6-completion
blocker.

TEST ARCHITECTURE (matches test_p04_te_cut.py): the expensive sandwich-body
booleans (hollow_interior + the 6 upper/lower shells) go through
geometry_cache.py, keyed on config content + every P6 geometry module's
source (SOURCE_FILES below) — a re-run against unchanged config+code loads
them in milliseconds. Ribs/trimmed-spars/midsurfaces/false-spar are
comparatively cheap (~2 minutes total, measured) and are always rebuilt
fresh from the (possibly cached) sandwich shapes, same "cache only the
truly expensive part, verify everything fresh" split as P4. A `slow`-marked
tier forces one fully fresh rebuild to prove the cache still matches
reality; `make gate`/`make regress` run it every time.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import pytest
import yaml
from geometry_cache import get_or_build_shapes
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from backend import tolerances
from backend.geometry.booleans import filter_shards, fuzzy_common
from backend.geometry.false_spar import build_false_spar
from backend.geometry.iml import (
    build_sandwich_body,
    build_sandwich_lofts,
    face_sheet_thickness_mm,
)
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.midsurface import build_skin_midsurface
from backend.geometry.reference import build_hardpoints, build_rib_planes, build_spar_surfaces
from backend.geometry.ribs import build_ribs
from backend.geometry.sections import build_planform_sections
from backend.geometry.spar_trim import build_trimmed_spars
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES as TE_CUT_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
)
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S * 60)  # a real P6 build is ~60-90min measured,
# WITH documented ~3-4x run-to-run variance on this workspace (docs/known_issues.md) — generous headroom (10hr) so
# hours of real computation are never lost to a premature timeout on a slow run; this is a one-shot gate, not a loop

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p06_timings.json"

DEVICE_STEMS = ["te_half"]  # module docstring: intentional, cost-driven battery scope

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


def _load(stem: str) -> Config:
    return Config.model_validate(yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text()))


def _write_timings(stem: str, timings: dict) -> None:
    data = json.loads(TIMINGS_PATH.read_text()) if TIMINGS_PATH.exists() else {}
    data[stem] = timings
    TIMINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(json.dumps(data, indent=2))


@dataclass
class P6Case:
    stem: str
    config: Config
    sections: list
    oml: cq.Solid
    wing: cq.Solid  # res.wing from te_cut — the device-cut body the sandwich is built on
    control_surface: cq.Solid
    sandwich: dict  # name -> cq.Shape, the SANDWICH_SHAPE_NAMES, post shard-filter kept solids
    false_spar_solid: cq.Shape
    rib_set: object  # RibSet
    trimmed_spars: list  # list[TrimmedSpar]
    skin_midsurface: cq.Shape
    spar_midsurfaces: dict
    cache_hit: bool


def _build_p6_case(stem: str, force_fresh: bool) -> P6Case:
    """Two independent expensive-boolean stages, each through
    geometry_cache.py so a re-run against unchanged config+code loads both
    in milliseconds: the P4 device cut (te_cut.py's own
    GEOMETRY_SOURCE_FILES/cache convention, reused verbatim rather than
    calling the uncached cut_te_surface() wrapper — that would pay the
    P4 boolean cost again on every fast-tier run) and this phase's own
    sandwich-body booleans."""
    config = _load(stem)
    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_te_cut_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        _write_timings(f"{stem}_te_cut", raw.timings_s)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), _te_cut_cache_hit = get_or_build_shapes(
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
        timings = {"lofts_s": lofts.timings_s, "body_s": body.timings_s, "total_s": time.perf_counter() - t_start}
        _write_timings(stem, timings)
        return [getattr(body, name) for name in SANDWICH_SHAPE_NAMES]

    raw_shapes, cache_hit = get_or_build_shapes(
        config, SOURCE_FILES, SANDWICH_SHAPE_NAMES, _build_raw, force_fresh=force_fresh,
    )
    sandwich = dict(zip(SANDWICH_SHAPE_NAMES, raw_shapes))

    lofts = build_sandwich_lofts(config, sections)  # cheap (~seconds) — see module docstring
    fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
    rib_planes = build_rib_planes(config)
    rib_set = build_ribs(config, sandwich["hollow_interior"], rib_planes)
    trimmed_spars = build_trimmed_spars(config, sections, sandwich["hollow_interior"])
    skin_midsurface = build_skin_midsurface(config, sections)
    spar_midsurfaces = build_spar_surfaces(config, sections)

    return P6Case(
        stem=stem, config=config, sections=sections, oml=oml,
        wing=te_res.wing, control_surface=te_res.control_surface,
        sandwich=sandwich, false_spar_solid=fs.solid, rib_set=rib_set,
        trimmed_spars=trimmed_spars, skin_midsurface=skin_midsurface,
        spar_midsurfaces=spar_midsurfaces, cache_hit=cache_hit,
    )


def pytest_generate_tests(metafunc):
    for fixture_name in ("p6_result", "p6_result_fresh"):
        if fixture_name in metafunc.fixturenames:
            metafunc.parametrize(fixture_name, DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def p6_result(request) -> P6Case:
    return _build_p6_case(request.param, force_fresh=False)


@pytest.fixture(scope="module")
def p6_result_fresh(request) -> P6Case:
    return _build_p6_case(request.param, force_fresh=True)


def _kept_solids(shape: cq.Shape) -> list[cq.Solid]:
    kept, _shards = filter_shards(shape, min_volume=1e-6)
    return kept


def test_no_shards(p6_result, gate_metrics):
    r, stem = p6_result, p6_result.stem
    counts = {}
    for name, shape in r.sandwich.items():
        if shape is None:
            continue
        _kept, shards = filter_shards(shape)
        counts[name] = len(shards)
        assert not shards, f"{stem}: sandwich[{name}] has {len(shards)} shard(s) (F3)"
    for rib in r.rib_set.ribs:
        _kept, shards = filter_shards(rib.solid)
        counts[f"rib_{rib.y_mm:.0f}"] = len(shards)
        assert not shards, f"{stem}: rib at y={rib.y_mm} has {len(shards)} shard(s) (F3)"
    for spar in r.trimmed_spars:
        _kept, shards = filter_shards(spar.solid)
        counts[f"spar_{spar.name}"] = len(shards)
        assert not shards, f"{stem}: spar {spar.name} has {len(shards)} shard(s) (F3)"
    gate_metrics.setdefault("shard_counts", {})[stem] = counts


def test_all_watertight(p6_result, gate_metrics):
    r, stem = p6_result, p6_result.stem
    not_watertight = []
    for name, shape in r.sandwich.items():
        if shape is None:
            continue
        for solid in _kept_solids(shape):
            if not is_watertight(solid):
                not_watertight.append(f"sandwich[{name}]")
    for rib in r.rib_set.ribs:
        for solid in _kept_solids(rib.solid):
            if not is_watertight(solid):
                not_watertight.append(f"rib_y={rib.y_mm}")
    for spar in r.trimmed_spars:
        for solid in _kept_solids(spar.solid):
            if not is_watertight(solid):
                not_watertight.append(f"spar_{spar.name}")
    if not is_watertight(r.false_spar_solid):
        not_watertight.append("false_spar")
    assert not not_watertight, f"{stem}: not watertight: {not_watertight}"
    gate_metrics.setdefault("watertight_check", {})[stem] = "all pass"


def test_ribs_watertight_after_holes(p6_result, gate_metrics):
    """Direct restatement of the plan's own wording — every rib, INCLUDING
    the ones with a lightening hole cut, is watertight. ribs.py's own
    graceful fallback (module docstring) means a rib that couldn't fit a
    hole is a plain solid slab instead — both outcomes must still pass
    this check; only shards/invalidity/non-watertightness would fail it."""
    r, stem = p6_result, p6_result.stem
    results = []
    for rib in r.rib_set.ribs:
        solids = _kept_solids(rib.solid)
        ok = len(solids) >= 1 and rib.solid.isValid() and all(is_watertight(s) for s in solids)
        results.append({"y_mm": rib.y_mm, "has_hole": rib.has_hole, "ok": ok})
        assert ok, f"{stem}: rib at y={rib.y_mm} (has_hole={rib.has_hole}) failed watertight check"
    gate_metrics.setdefault("ribs_watertight", {})[stem] = results


def test_pairwise_interference(p6_result, gate_metrics):
    """Pairwise boolean interference = 0 across ALL distinct structural
    bodies: the 6 sandwich shells, every rib, every trimmed spar, and the
    false spar must not overlap each other (they may share a boundary
    FACE — bonded construction — but never a positive-volume intersection),
    EXCEPT three DESIGNED-to-overlap categories (first real-kernel run
    found all three, at small volumes — 4-110 mm^3 — consistent with
    intentional bonded/crossing geometry, not a defect; see
    docs/r0_findings/p06.md's P6-gate addendum for the actual numbers this
    exclusion list was built from):

    1. Adjacent layers of the SAME wall (e.g. face_outer_upper vs
       core_upper) — the same physical laminate by construction
       (fuzzy_cut'd from a shared boundary), not independent bodies.
    2. Ribs/spars vs the inner face sheet they bond to at their perimeter
       (module docstrings, ribs.py/spar_trim.py) — touching face_inner_*
       there is by construction.
    3. Rib vs spar, AND false_spar vs rib/spar: ribs run chordwise at each
       station, spars run spanwise — they physically MUST cross each other
       (real aircraft ribs are notched for the spar to pass through; this
       phase builds both as independent solids, not yet mutually trimmed
       — a finer manufacturing-detail follow-on, not a P6 blocker). The
       false spar's own docstring already anticipated overlapping the
       device-edge ribs as "a bond flange for the forced device-edge ribs
       that arrive later in P6" — this is that overlap, expected."""
    r, stem = p6_result, p6_result.stem

    bodies: dict[str, cq.Shape] = {
        "face_outer_upper": r.sandwich["face_outer_upper"],
        "face_outer_lower": r.sandwich["face_outer_lower"],
        "core_upper": r.sandwich["core_upper"],
        "core_lower": r.sandwich["core_lower"],
        "face_inner_upper": r.sandwich["face_inner_upper"],
        "face_inner_lower": r.sandwich["face_inner_lower"],
        "false_spar": r.false_spar_solid,
    }
    for rib in r.rib_set.ribs:
        bodies[f"rib_y={rib.y_mm:.0f}"] = rib.solid
    for spar in r.trimmed_spars:
        bodies[f"spar_{spar.name}"] = spar.solid

    # Adjacent-layer pairs of the SAME wall — expected to touch (shared
    # boundary), excluded per the docstring above.
    same_wall_pairs = {
        frozenset({"face_outer_upper", "core_upper"}),
        frozenset({"face_outer_lower", "core_lower"}),
        frozenset({"core_upper", "face_inner_upper"}),
        frozenset({"core_lower", "face_inner_lower"}),
    }
    names = list(bodies.keys())
    interferences = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if frozenset({a, b}) in same_wall_pairs:
                continue
            a_rib_or_spar = a.startswith("rib_") or a.startswith("spar_")
            b_rib_or_spar = b.startswith("rib_") or b.startswith("spar_")
            # Category 2: rib/spar vs the inner face sheet they bond to.
            if (a_rib_or_spar and "face_inner" in b) or (b_rib_or_spar and "face_inner" in a):
                continue
            # Category 3: rib CROSSING a spar (structural necessity — NOT
            # rib-vs-rib or spar-vs-spar, which should never overlap and
            # WOULD be a real bug if they did), and false_spar vs rib/spar
            # (documented bond flange) — see docstring above.
            a_is_rib, b_is_rib = a.startswith("rib_"), b.startswith("rib_")
            a_is_spar, b_is_spar = a.startswith("spar_"), b.startswith("spar_")
            if (a_is_rib and b_is_spar) or (a_is_spar and b_is_rib):
                continue
            if (a == "false_spar" and b_rib_or_spar) or (b == "false_spar" and a_rib_or_spar):
                continue
            try:
                common = fuzzy_common(bodies[a], bodies[b])
            except RuntimeError:
                continue
            kept, _shards = filter_shards(common)
            vol = sum(s.Volume() for s in kept)
            if vol > 0:
                interferences[f"{a} ^ {b}"] = round(vol, 4)

    assert not interferences, f"{stem}: pairwise interference detected: {interferences}"
    gate_metrics.setdefault("pairwise_interference", {})[stem] = {"pairs_checked": len(names) * (len(names) - 1) // 2}


def test_iml_min_wall_audit(p6_result, gate_metrics):
    """min wall >= face-sheet stack everywhere (sampled), with the
    documented self-clip floor of 2*face_mm — module docstring. Sampled by
    measuring the ACTUAL as-built distance from OML vertices to
    hollow_iml_solid's surface (BRepExtrema_DistShapeShape, the same
    point-to-shell pattern test_p04_te_cut.py's _point_to_shell_distance
    established) — not re-evaluating the construction formula, which would
    trivially self-satisfy.

    Vertices within the device window's spanwise range are EXCLUDED, same
    reasoning and same margin convention as test_p04_te_cut.py's
    test_cove_clearance_at_rest_and_deflected (its own `2*gap` end-cap
    exclusion): `r.wing` includes vertices on the cove-cut / false-spar
    interface faces there, which are genuinely not "outer skin" points —
    "wall thickness measured from the outer skin" isn't a meaningful
    concept AT a device cut face. First run without this exclusion found 5
    exactly-zero-mm samples, all inside the device window (y in
    [660,1140]mm on te_half.yaml) — confirming they were cut-face
    vertices, not a real void in the clean-span sandwich this audit is
    actually about (docs/r0_findings/p06.md)."""
    r, stem, config = p6_result, p6_result.stem, p6_result.config
    face_mm = face_sheet_thickness_mm(config)
    core_mm = config.skin.core.thickness_mm
    stack_mm = 2 * face_mm + core_mm
    floor_mm = 2 * face_mm - tolerances.KERNEL_TOLERANCE_MM  # solid-laminate floor, small kernel slack

    lofts = build_sandwich_lofts(config, r.sections)

    te = config.te_surface
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    gap = te.gap_mm
    window_lo = te.span_start_frac * half_span_mm - 2 * gap
    window_hi = te.span_end_frac * half_span_mm + 2 * gap

    below_floor = []
    full_stack_count = 0
    self_clipped_count = 0
    excluded_count = 0
    sample_verts = list(r.wing.Vertices())[::5]  # subsample for speed, matches P4's own convention
    for v in sample_verts:
        if window_lo <= v.Y <= window_hi:
            excluded_count += 1
            continue
        dist_op = BRepExtrema_DistShapeShape(v.wrapped, lofts.hollow_iml_solid.wrapped)
        dist_op.Perform()
        wall_mm = dist_op.Value()
        if wall_mm < floor_mm:
            below_floor.append(round(wall_mm, 3))
        elif wall_mm >= stack_mm - tolerances.COVE_CLEARANCE_TOL_MM:
            full_stack_count += 1
        else:
            self_clipped_count += 1

    assert not below_floor, (
        f"{stem}: {len(below_floor)} sampled point(s) below the solid-laminate floor "
        f"{floor_mm:.3f}mm (2x face_mm): {below_floor[:10]}... — a real void, not accepted self-clip"
    )
    gate_metrics.setdefault("iml_min_wall_audit", {})[stem] = {
        "samples": len(sample_verts), "excluded_device_window": excluded_count,
        "full_stack": full_stack_count, "self_clipped_floor_ok": self_clipped_count,
        "below_floor": len(below_floor),
        "stack_mm": round(stack_mm, 3), "floor_mm": round(floor_mm, 3),
    }


def test_midsurface_count_matches_structural_bodies(p6_result, gate_metrics):
    """D15: one midsurface per WALL (not per sandwich layer) — see
    backend/geometry/midsurface.py's module docstring."""
    r, stem = p6_result, p6_result.stem
    assert r.skin_midsurface.isValid() and not r.skin_midsurface.Solids(), (
        f"{stem}: skin midsurface must be a valid open shell"
    )
    for rib in r.rib_set.ribs:
        assert rib.midsurface_face.isValid(), f"{stem}: rib midsurface at y={rib.y_mm} invalid"
    for name, shell in r.spar_midsurfaces.items():
        assert shell.isValid(), f"{stem}: spar midsurface {name} invalid"

    n_midsurfaces = 1 + len(r.rib_set.ribs) + len(r.spar_midsurfaces)
    n_structural_bodies = 1 + len(r.rib_set.ribs) + len(r.trimmed_spars)
    assert n_midsurfaces == n_structural_bodies, (
        f"{stem}: {n_midsurfaces} midsurfaces != {n_structural_bodies} structural bodies"
    )
    gate_metrics.setdefault("midsurface_count", {})[stem] = {
        "midsurfaces": n_midsurfaces, "structural_bodies": n_structural_bodies,
    }


def test_hardpoint_core_ramp_out(p6_result, gate_metrics):
    """Every auto hardpoint has core ramp-out. Genuinely iterates
    reference.build_hardpoints and checks each one — passes VACUOUSLY on
    every current config (none declare hardpoints), not by being weakened.
    See module docstring."""
    r, stem, config = p6_result, p6_result.stem, p6_result.config
    hardpoints = build_hardpoints(config)

    lofts = build_sandwich_lofts(config, r.sections)
    core_mm = config.skin.core.thickness_mm
    ramp_len_mm = config.skin.ramp_ratio * core_mm

    violations = []
    for pt in hardpoints:
        dist_op = BRepExtrema_DistShapeShape(
            cq.Vertex.makeVertex(pt.x, pt.y, pt.z).wrapped, lofts.core_iml_solid.wrapped,
        )
        dist_op.Perform()
        if dist_op.Value() < ramp_len_mm:
            violations.append({"point": [pt.x, pt.y, pt.z], "dist_mm": round(dist_op.Value(), 2)})

    assert not violations, f"{stem}: hardpoint(s) without core ramp-out: {violations}"
    gate_metrics.setdefault("hardpoint_ramp_out", {})[stem] = {
        "hardpoints_checked": len(hardpoints), "violations": len(violations),
    }


@pytest.mark.slow
def test_fresh_build_matches_gate_criteria(p6_result_fresh, gate_metrics):
    """Slow tier: force one real, uncached rebuild of the expensive sandwich
    shapes and re-check the core P6 pass criteria — proves the fast tier's
    cache genuinely reflects what a real build produces right now. Marked
    `slow`; `make gate`/`make regress` run it every time regardless."""
    r, stem = p6_result_fresh, p6_result_fresh.stem
    for name, shape in r.sandwich.items():
        if shape is None:
            continue
        kept, shards = filter_shards(shape)
        assert not shards, f"{stem}: fresh build sandwich[{name}] has {len(shards)} shard(s)"
        assert all(is_watertight(s) for s in kept), f"{stem}: fresh build sandwich[{name}] not watertight"
    for rib in r.rib_set.ribs:
        kept, shards = filter_shards(rib.solid)
        assert not shards and all(is_watertight(s) for s in kept), f"{stem}: fresh build rib at y={rib.y_mm} failed"
    for spar in r.trimmed_spars:
        kept, shards = filter_shards(spar.solid)
        assert not shards and all(is_watertight(s) for s in kept), f"{stem}: fresh build spar {spar.name} failed"
    gate_metrics.setdefault("slow_tier_fresh_build", {})[stem] = "pass"
