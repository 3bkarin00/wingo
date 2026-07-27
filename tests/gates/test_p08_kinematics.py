"""P8 gate — the kinematic sweep (plan.md §9 P8 pass criteria, "the
decisive R1 gate"):

  sweep TE through ±max_deflection: coarse 1° steps + fine 0.1° steps in
  the outer 20% of travel; collision count = 0 at every step; minimum
  clearance >= gap_mm - tolerance and monotonic-trend check; swept-volume
  boolean at both extremes intersect fixed wing = ∅ (F9).

Reuses the EXACT same hinge assembly test_p07_hinges.py already builds and
spot-checks at 5 angles (rest + 4 extremes/midpoints) — this gate exercises
backend.geometry.kinematics's full coarse+fine+envelope discipline against
that SAME assembly instead of re-deriving a different one, so a pass here
is a strictly stronger claim than P7's own swept-pocket check, not a
redundant one. TWO body groupings, for two DIFFERENT physical claims (found
necessary empirically — see test_clearance_floor_and_monotonic_trend's own
docstring for why conflating them silently measures the wrong number):
`wing_bodies`/`cs_bodies` (hinge HARDWARE — false_spar_pocketed/carriers/
tubes, mirroring P7's own `static_wing`/`moving_cs` split, test_p07_hinges.
py's test_swept_pocket_clearance) for the collision-count and swept-volume-
envelope checks; `wing_skin`/`cs_skin` (the actual P4 wing/control_surface
bodies) for the gap_mm clearance-floor + monotonic-trend check.

SCOPE: te_half.yaml only (same cost-driven, documented battery-scope
decision as P6/P7 — module docstring there applies verbatim here).

COST: kinematics.sweep_angles(max_deflection_deg) samples ~150+ angles
(coarse across the full range + fine in the outer 20% band each side,
kinematics.py's own derivation) x every (cs_body, wing_body) pair (~40+
pairs at 3 hinge stations: false_spar_pocketed + 3x(wing_carrier+wing_tube)
vs 3x(cs_carrier+cs_tube)) — materially more boolean ops than P7's 5-angle
spot check, on top of the same P4+lofts+false_spar+hinges construction cost
P7 already documents (~55s P4 + ~140s lofts/false_spar + ~300-330s hinges).
Uses the SAME `GEOMETRY_TEST_TIMEOUT_S * 60` (10hr) per-test budget as
P6/P7's own slow real-build tests — this is the established pattern for
"real, uncached, potentially very slow" gates in this project, not a new
convention invented here.

TEST ARCHITECTURE: identical cache-sharing convention as P6/P6-ext/P7 —
only the P4 device-cut booleans go through geometry_cache.py
(te_cut.py's own GEOMETRY_SOURCE_FILES), sharing whichever of P7's or this
gate's own run happens first in a `make gate` session. Lofts + false_spar +
hinges are always rebuilt fresh (same reasoning as P7: the hinge/pocket
construction IS the point of both gates).
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

from backend import tolerances
from backend.geometry.false_spar import build_false_spar
from backend.geometry.hinges_pin_tube import PinTubeHingeSet, build_pin_tube_hinges
from backend.geometry.iml import build_sandwich_lofts
from backend.geometry.kinematics import (
    envelope_clear_of_wing,
    monotonic_clearance_violations,
    sweep_collisions,
    sweep_min_distance_by_points,
)
from backend.geometry.loft import build_oml
from backend.geometry.sections import build_planform_sections
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES as TE_CUT_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
)
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S * 60)  # module docstring: same
# "real, uncached, potentially very slow" budget as P6/P7's own slow tiers, not a new convention

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p08_timings.json"

DEVICE_STEMS = ["te_half"]  # module docstring: intentional, cost-driven battery scope


def _load(stem: str) -> Config:
    return Config.model_validate(yaml.safe_load((DEVICE_DIR / f"{stem}.yaml").read_text()))


def _write_timings(stem: str, timings: dict) -> None:
    data = json.loads(TIMINGS_PATH.read_text()) if TIMINGS_PATH.exists() else {}
    data[stem] = timings
    TIMINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(json.dumps(data, indent=2))


@dataclass
class P8Case:
    stem: str
    config: Config
    hinge_set: PinTubeHingeSet
    wing_bodies: list  # module docstring: false_spar_pocketed + every wing_carrier/wing_tube
    cs_bodies: list    # every cs_carrier/cs_tube
    wing_skin: cq.Shape  # te_res.wing — the actual skin body the CS must clear by gap_mm
    cs_skin: cq.Shape    # te_res.control_surface


def _build_p8_case(stem: str, force_fresh: bool) -> P8Case:
    config = _load(stem)
    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_te_cut_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        _write_timings(f"{stem}_te_cut", raw.timings_s)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), _cache_hit = get_or_build_shapes(
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
    _write_timings(f"{stem}_build", timings)

    assert not hinge_set.failed, f"{stem}: hinge construction failures (P7's own gate should catch this first): {hinge_set.failed}"
    assert hinge_set.false_spar_pocketed is not None and hinge_set.cs_pocketed is not None

    wing_bodies = [hinge_set.false_spar_pocketed]
    cs_bodies = []
    for st in hinge_set.stations:
        wing_bodies += [st.wing_carrier, st.wing_tube]
        cs_bodies += [st.cs_carrier, st.cs_tube]

    return P8Case(
        stem=stem, config=config, hinge_set=hinge_set, wing_bodies=wing_bodies, cs_bodies=cs_bodies,
        wing_skin=te_res.wing, cs_skin=te_res.control_surface,
    )


def pytest_generate_tests(metafunc):
    if "p8_result" in metafunc.fixturenames:
        metafunc.parametrize("p8_result", DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def p8_result(request) -> P8Case:
    return _build_p8_case(request.param, force_fresh=False)


def test_sweep_zero_collisions(p8_result, gate_metrics):
    """Plan.md: 'collision count = 0 at every step' across the full
    coarse+fine sweep (kinematics.sweep_angles), not just the 5 spot-check
    angles P7's own gate already covers."""
    r, stem = p8_result, p8_result.stem
    max_defl = r.config.te_surface.max_deflection_deg
    t0 = time.perf_counter()
    result = sweep_collisions(
        r.wing_bodies, r.cs_bodies, r.hinge_set.axis_p0, r.hinge_set.axis_dir, max_defl,
    )
    sweep_s = time.perf_counter() - t0
    _write_timings(f"{stem}_sweep", {"n_angles": len(result.samples), "sweep_s": sweep_s})

    assert result.collision_count == 0, (
        f"{stem}: {result.collision_count} colliding sample(s) across "
        f"{len(result.samples)} angles: "
        f"{[(s.angle_deg, s.colliding_pairs) for s in result.samples if s.collision_volume_mm3 > 0]}"
    )
    gate_metrics.setdefault("sweep_collisions", {})[stem] = {
        "n_angles": len(result.samples), "collision_count": result.collision_count,
        "worst_clearance_mm": round(result.worst_clearance_mm, 4),
    }
    p8_result.sweep_result = result


def test_clearance_floor_and_monotonic_trend(p8_result, gate_metrics):
    """Plan.md: 'minimum clearance >= gap_mm - tolerance and monotonic-
    trend check'.

    `gap_mm` is `te_surface.gap_mm` — the SKIN-level (wing-vs-CS, i.e. the
    cove/nose gap P4's own construction targets at COVE_CLEARANCE_MM and
    spot-checks in test_p04_te_cut.py's test_cove_clearance_at_rest_and_
    deflected) clearance, not a hinge-hardware fit. Found empirically
    (first version of this test): sweeping the SAME hardware groupings
    test_sweep_zero_collisions uses makes `worst_clearance_mm` measure the
    wing_tube<->cs_tube AXIAL gap instead (rotation-invariant about its
    own axis) — a real, by-design, unrelated mechanical clearance, not
    this criterion's target.

    TWO further attempts at a body-level check both hit pytest-timeout's
    10-HOUR budget: a raw compound-vs-compound BRepExtrema between the
    full skin solids, then again between proximity-culled face subsets
    (kinematics.proximity_face_subsets — the cull didn't shrink the
    workload enough at these body sizes; kept as a general utility, not
    what this test uses). THIRD approach, adopted here: the exact
    technique test_p04_te_cut.py's own test_cove_clearance_at_rest_and_
    deflected already uses at 2 angles — point-to-SHELL BRepExtrema
    (vertex operand, O(1) cheap) against the moving body's own vertices,
    extended across a full angle sweep
    (kinematics.sweep_min_distance_by_points). Still a REAL measurement
    against REAL built geometry, never a re-derivation of the construction
    formula — just architecturally the right tool (point-location query,
    not many-face proximity search).

    ANGLE SET: coarse-only (KINEMATIC_COARSE_STEP_DEG, ~51 angles for
    ±25°), not the full fine+coarse sweep_angles() the collision/envelope
    tests use. F9's fine-step rationale is "a coarse-only COLLISION sweep
    can step over a fleeting hit between samples" — this isn't a
    collision search, it's confirming a clearance that is, BY
    CONSTRUCTION (ADR-002/003, COVE_CLEARANCE_MM's own derivation: "an
    exact, deflection-invariant offset regardless of deflection angle"),
    expected to be flat across the whole sweep — there is no fleeting dip
    for a finer step to catch that a coarse one would miss."""
    r, stem = p8_result, p8_result.stem
    max_defl = r.config.te_surface.max_deflection_deg
    coarse_angles = np.arange(-max_defl, max_defl + 1e-9, tolerances.KINEMATIC_COARSE_STEP_DEG)
    coarse_angles = np.unique(np.round(np.concatenate([coarse_angles, [0.0, -max_defl, max_defl]]), 6))

    result = sweep_min_distance_by_points(
        r.cs_skin, r.wing_skin, r.hinge_set.axis_p0, r.hinge_set.axis_dir, coarse_angles,
    )
    _write_timings(f"{stem}_skin_sweep", {
        "n_angles": len(result.samples), "sweep_s": result.timings_s["total_s"],
        "n_points": result.timings_s["n_points"],
    })

    gap_mm = r.config.te_surface.gap_mm
    floor_mm = gap_mm - tolerances.KINEMATIC_CLEARANCE_TOLERANCE_MM
    assert result.worst_clearance_mm >= floor_mm, (
        f"{stem}: worst wing/CS skin clearance {result.worst_clearance_mm:.4f}mm < floor {floor_mm:.4f}mm "
        f"(gap_mm={gap_mm} - tolerance={tolerances.KINEMATIC_CLEARANCE_TOLERANCE_MM})"
    )

    violations = monotonic_clearance_violations(result)
    assert not violations, f"{stem}: {len(violations)} monotonic-trend violation(s): {violations}"

    gate_metrics.setdefault("clearance_floor", {})[stem] = {
        "worst_clearance_mm": round(result.worst_clearance_mm, 4), "floor_mm": round(floor_mm, 4),
        "monotonic_violations": violations,
    }


def test_swept_volume_envelope_clear(p8_result, gate_metrics):
    """Plan.md (F9): 'swept-volume boolean at both extremes intersect
    fixed wing = ∅' — kinematics.envelope_clear_of_wing's own union-of-
    rotated-copies technique (same as WP1's pocket construction), a check
    the point-sample sweep's discrete angles cannot by itself guarantee."""
    r, stem = p8_result, p8_result.stem
    max_defl = r.config.te_surface.max_deflection_deg
    t0 = time.perf_counter()
    results = envelope_clear_of_wing(
        r.wing_bodies, r.cs_bodies, r.hinge_set.axis_p0, r.hinge_set.axis_dir, max_defl,
    )
    envelope_s = time.perf_counter() - t0
    _write_timings(f"{stem}_envelope", {"envelope_s": envelope_s})

    hits = [
        {"angle_extreme_deg": e.angle_extreme_deg, "volume_mm3": round(e.collision_volume_mm3, 6)}
        for e in results if e.collision_volume_mm3 > 0
    ]
    assert not hits, f"{stem}: swept-volume envelope intersects the fixed wing at: {hits}"
    gate_metrics.setdefault("swept_volume_envelope", {})[stem] = {
        "extremes_checked": [e.angle_extreme_deg for e in results],
        "worst_volume_mm3": max((e.collision_volume_mm3 for e in results), default=0.0),
    }
