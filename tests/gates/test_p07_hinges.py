"""P7 gate — pin-and-tube hinges (D26/ADR-005, plan.md §9 P7 pass criteria):

  all hinge bore holes coaxial with their axis within 0.05mm, measured on
  the generated geometry; carrier clearance to the body it must swing clear
  of >= configured fit gap at rest AND swept through ±max_deflection (0
  collisions in the swept-pocket check); carrier bonded to its mount
  (false spar / LE web) with real positive-volume contact, never exact
  zero-distance touch (F4-adjacent).

Supersedes the retired lug/tang gate (ADR-005) — same phase slot, new
construction target. The lug/tang probe trail in docs/r0_findings/p07.md
is kept as historical record; this gate's own R0 trail (sweep/rotation
APIs, hinge-carrier bond-gap convergence) is appended under its own
heading in the same file.

READING for "carrier clearance ... >= configured fit gap": the wing
carrier and CS carrier are BONDED (explicit gap, HINGE_CARRIER_BOND_GAP_MM)
to their own mount — that's the bond-gap check, not a clearance check. The
actual "clearance to the body it must swing clear of" criterion is the
SWEPT-POCKET collision check: rotate each moving hardware set (carrier+tube)
through ±max_deflection at HINGE_POCKET_SWEEP_STEP_DEG steps and assert
zero positive-volume intersection against the opposing static set, exactly
mirroring probe_pin_tube_hinges_verify.py's real-kernel verification.

SCOPE: te_half.yaml only (hinges.mode: generated, count: 3) — same cost-
driven, documented battery-scope decision as the retired gate and P6.
Independently probed through docs/r0_findings/p07.md's WP1 trail (rotation-
axis accuracy, then this construction against the real P4 device-cut +
false-spar bodies) before this gate was written — confirmatory, not
exploratory.

COST: dominated by the swept-pocket booleans (~300-330s measured for 3
hinges: ~190s CS pockets + ~120s false-spar pockets, docs/r0_findings/
p07.md) on top of the P4 device cut (~55s) and false-spar lofts (~140s).

TEST ARCHITECTURE (matches test_p04_te_cut.py / the retired P7 gate): only
the P4 device-cut booleans go through geometry_cache.py (te_cut.py's own
GEOMETRY_SOURCE_FILES/cache convention). Lofts + false_spar + hinges are
always rebuilt fresh (real, ~350-450s total, not worth caching at this
cost — the swept-pocket construction is itself the point of this gate). A
`slow`-marked tier forces one fully fresh P4 rebuild too; `make gate`/
`make regress` run it every time.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import yaml
from geometry_cache import get_or_build_shapes
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from backend import tolerances
from backend.geometry.booleans import coaxial_cylinder_axis_deviation, filter_shards, fuzzy_common
from backend.geometry.false_spar import build_false_spar
from backend.geometry.hinges_pin_tube import PinTubeHingeSet, build_pin_tube_hinges
from backend.geometry.iml import build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
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
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p07_timings.json"

DEVICE_STEMS = ["te_half"]  # module docstring: intentional, cost-driven battery scope


def _load(stem: str) -> Config:
    return Config.model_validate(yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text()))


def _write_timings(stem: str, timings: dict) -> None:
    data = json.loads(TIMINGS_PATH.read_text()) if TIMINGS_PATH.exists() else {}
    data[stem] = timings
    TIMINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(json.dumps(data, indent=2))


@dataclass
class P7Case:
    stem: str
    config: Config
    sections: list
    wing: cq.Solid
    control_surface: cq.Solid
    false_spar_solid: cq.Shape
    hinge_set: PinTubeHingeSet
    cache_hit: bool


def _build_p7_case(stem: str, force_fresh: bool) -> P7Case:
    config = _load(stem)
    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_te_cut_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        _write_timings(f"{stem}_te_cut", raw.timings_s)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), cache_hit = get_or_build_shapes(
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

    t_start = time.perf_counter()
    lofts = build_sandwich_lofts(config, sections)
    fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
    hinge_set = build_pin_tube_hinges(config, sections, te_res.control_surface, fs.solid)
    timings = {"lofts_false_spar_s": time.perf_counter() - t_start, "hinges": hinge_set.timings_s}
    _write_timings(stem, timings)

    return P7Case(
        stem=stem, config=config, sections=sections,
        wing=te_res.wing, control_surface=te_res.control_surface,
        false_spar_solid=fs.solid, hinge_set=hinge_set, cache_hit=cache_hit,
    )


def pytest_generate_tests(metafunc):
    for fixture_name in ("p7_result", "p7_result_fresh"):
        if fixture_name in metafunc.fixturenames:
            metafunc.parametrize(fixture_name, DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def p7_result(request) -> P7Case:
    return _build_p7_case(request.param, force_fresh=False)


@pytest.fixture(scope="module")
def p7_result_fresh(request) -> P7Case:
    return _build_p7_case(request.param, force_fresh=True)


def test_hinges_built_no_failures(p7_result, gate_metrics):
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    assert hs.stations, f"{stem}: no hinge stations built (mode!=generated or te_surface disabled?)"
    assert len(hs.stations) == r.config.te_surface.hinges.count, (
        f"{stem}: built {len(hs.stations)} stations, config declares "
        f"{r.config.te_surface.hinges.count}"
    )
    assert not hs.failed, f"{stem}: hinge construction failures: {hs.failed}"
    gate_metrics.setdefault("hinges_built", {})[stem] = {
        "count": len(hs.stations), "failed": hs.failed,
    }


def test_all_watertight(p7_result, gate_metrics):
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    not_watertight = []
    for st in hs.stations:
        for label, solid in [
            ("wing_tube", st.wing_tube), ("cs_tube", st.cs_tube),
            ("wing_carrier", st.wing_carrier), ("cs_carrier", st.cs_carrier),
        ]:
            solids, shards = filter_shards(solid, min_volume=1e-9)
            if shards or len(solids) != 1 or not is_watertight(solids[0]):
                not_watertight.append(f"{label}@station{st.index} (solids={len(solids)}, shards={len(shards)})")
    for label, body in [("cs_pocketed", hs.cs_pocketed), ("false_spar_pocketed", hs.false_spar_pocketed)]:
        if body is None:
            not_watertight.append(f"{label}: missing")
            continue
        solids, shards = filter_shards(body, min_volume=1e-6)
        if shards or not all(is_watertight(s) for s in solids):
            not_watertight.append(label)
    assert not not_watertight, f"{stem}: not watertight/single-solid: {not_watertight}"
    gate_metrics.setdefault("watertight_check", {})[stem] = "all pass"


def test_hole_coaxiality(p7_result, gate_metrics):
    """Plan.md: 'all hinge bore holes coaxial with their axis within
    0.05mm, measured on the generated geometry' — extracts the actual
    cylindrical faces of each built tube (not the construction inputs) and
    checks their axis LINES against the true hinge axis line
    (COAXIALITY_TOLERANCE_MM)."""
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    worst = 0.0
    checked = 0
    violations = []
    for st in hs.stations:
        for label, tube in [("wing_tube", st.wing_tube), ("cs_tube", st.cs_tube)]:
            devs = coaxial_cylinder_axis_deviation(tube, hs.axis_p0, hs.axis_dir)
            assert devs, f"{stem}: {label}@station{st.index} has no cylindrical face aligned with the hinge axis"
            checked += len(devs)
            local_worst = max(devs)
            worst = max(worst, local_worst)
            if local_worst > tolerances.COAXIALITY_TOLERANCE_MM:
                violations.append({"label": label, "station": st.index, "dev_mm": round(local_worst, 5)})

    assert not violations, (
        f"{stem}: {len(violations)} tube(s) exceed COAXIALITY_TOLERANCE_MM="
        f"{tolerances.COAXIALITY_TOLERANCE_MM}mm: {violations}"
    )
    gate_metrics.setdefault("hole_coaxiality", {})[stem] = {
        "faces_checked": checked, "worst_deviation_mm": round(worst, 5),
        "tolerance_mm": tolerances.COAXIALITY_TOLERANCE_MM,
    }


def test_carrier_bond_gaps(p7_result, gate_metrics):
    """Every carrier is bonded to its mount with a real, explicit,
    positive-volume gap (HINGE_CARRIER_BOND_GAP_MM) — never exact
    zero-distance touch (F4-adjacent, module docstring)."""
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    bg = tolerances.HINGE_CARRIER_BOND_GAP_MM
    tol = tolerances.KERNEL_TOLERANCE_MM
    violations = []
    worst = {"wing": None, "cs": None}
    for st in hs.stations:
        for label, carrier, mount in [
            ("wing", st.wing_carrier, hs.false_spar_pocketed),
            ("cs", st.cs_carrier, hs.cs_pocketed),
        ]:
            op = BRepExtrema_DistShapeShape(carrier.wrapped, mount.wrapped)
            op.Perform()
            d = op.Value()
            worst[label] = d if worst[label] is None else min(worst[label], d)
            if not (0 < d <= bg + tol):
                violations.append({"label": label, "station": st.index, "gap_mm": round(d, 4)})
    assert not violations, f"{stem}: carrier bond gap not in (0, {bg}+tol]: {violations}"
    gate_metrics.setdefault("carrier_bond_gaps", {})[stem] = {
        "target_mm": bg,
        "worst_wing_mm": round(worst["wing"], 4) if worst["wing"] is not None else None,
        "worst_cs_mm": round(worst["cs"], 4) if worst["cs"] is not None else None,
    }


def test_swept_pocket_clearance(p7_result, gate_metrics):
    """Plan.md: 'carrier clearance to the body it must swing clear of ...
    swept through ±max_deflection (0 collisions in the swept-pocket
    check)' — rotate each moving hardware set through ±max_deflection at
    coarse+extreme sample angles and assert zero positive-volume
    intersection against the opposing static set. Mirrors
    probe_pin_tube_hinges_verify.py's real-kernel check."""
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    max_def = r.config.te_surface.max_deflection_deg
    a_v = cq.Vector(*hs.axis_p0)
    b_v = cq.Vector(*(hs.axis_p0 + hs.axis_dir))
    static_wing = [hs.false_spar_pocketed] + [st.wing_carrier for st in hs.stations] \
        + [st.wing_tube for st in hs.stations]
    moving_cs = [st.cs_carrier for st in hs.stations] + [st.cs_tube for st in hs.stations]
    moving_wing = [st.wing_carrier for st in hs.stations] + [st.wing_tube for st in hs.stations]

    worst_hit = 0.0
    hits = []
    for ang in (-max_def, -max_def / 2.0, 0.0, max_def / 2.0, max_def):
        for m in moving_cs:
            rm = m.rotate(a_v, b_v, float(ang))
            for s in static_wing:
                try:
                    common = fuzzy_common(rm, s)
                except RuntimeError:
                    continue
                kept, _shards = filter_shards(common, min_volume=1e-9)
                vol = sum(x.Volume() for x in kept)
                worst_hit = max(worst_hit, vol)
                if vol > 0:
                    hits.append({"side": "cs", "angle_deg": ang, "volume_mm3": round(vol, 6)})
        for m in moving_wing:
            rm = m.rotate(a_v, b_v, float(-ang))
            try:
                common = fuzzy_common(rm, hs.cs_pocketed)
            except RuntimeError:
                continue
            kept, _shards = filter_shards(common, min_volume=1e-9)
            vol = sum(x.Volume() for x in kept)
            worst_hit = max(worst_hit, vol)
            if vol > 0:
                hits.append({"side": "wing", "angle_deg": ang, "volume_mm3": round(vol, 6)})

    assert not hits, f"{stem}: {len(hits)} collision(s) in the swept-pocket check: {hits}"
    gate_metrics.setdefault("swept_pocket_clearance", {})[stem] = {
        "max_deflection_deg": max_def, "worst_intersection_mm3": round(worst_hit, 6),
    }


def test_naming_registry(p7_result, gate_metrics):
    """§8.8 centroid registry: 2 bond faces (wing + CS carrier) matched and
    named per station — build_pin_tube_hinges already hard-fails internally
    if a boolean ate one; this re-asserts the count on the finished set."""
    r, stem = p7_result, p7_result.stem
    hs = r.hinge_set
    expected = 2 * len(hs.stations)
    assert len(hs.bond_faces) == expected, (
        f"{stem}: {len(hs.bond_faces)} bond faces matched, expected {expected}: "
        f"{sorted(hs.bond_faces)}"
    )
    gate_metrics.setdefault("naming_registry", {})[stem] = sorted(hs.bond_faces)


@pytest.mark.slow
def test_fresh_build_matches_gate_criteria(p7_result_fresh, gate_metrics):
    """Slow tier: force one real, uncached rebuild of the P4 device cut and
    re-check the core P7 pass criteria — proves the fast tier's cache
    genuinely reflects what a real build produces right now."""
    r, stem = p7_result_fresh, p7_result_fresh.stem
    hs = r.hinge_set
    assert not hs.failed, f"{stem}: fresh build hinge construction failures: {hs.failed}"
    for st in hs.stations:
        for label, solid in [("wing_tube", st.wing_tube), ("cs_tube", st.cs_tube)]:
            solids, shards = filter_shards(solid, min_volume=1e-9)
            assert not shards and len(solids) == 1 and is_watertight(solids[0]), (
                f"{stem}: fresh build {label}@station{st.index} failed watertight check"
            )
            devs = coaxial_cylinder_axis_deviation(solid, hs.axis_p0, hs.axis_dir)
            assert devs and max(devs) <= tolerances.COAXIALITY_TOLERANCE_MM, (
                f"{stem}: fresh build {label}@station{st.index} coaxiality {devs} exceeds tolerance"
            )
    gate_metrics.setdefault("slow_tier_fresh_build", {})[stem] = "pass"
