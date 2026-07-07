"""P4 gate — plan.md §9 pass criteria + the refined per-station cove/nose
construction (docs/decisions/ADR-002, docs/r0_findings/p04.md):

  exactly 2 watertight bodies; vol(wing)+vol(CS)+vol(gap) = vol(P2) within
  0.5%; shard filter reports 0 bodies below min-volume threshold (F3); cove
  clearance present (no tangent face pairs, F4) — now verified as an exact
  radial offset (COVE_CLEARANCE_MM) rather than a coarse cylinder-radius gap:
    - nose_tangency: the normal-foot's C->skin vector is ⟂ the skin tangent
      (the mechanism that makes an axis-centered arc tangent to the skin);
    - nose_axis_centered: sealed-region profile points sit at the expected
      per-station radius from the hinge axis;
    - cove_clearance: min radial gap between nose and cove == COVE_CLEARANCE_MM,
      at 0° AND at the CS rotated to +max_deflection (proving the offset is
      invariant under rotation about the axis, not just true at rest);
    - no_interbody_tangency: wing ∩ CS is empty (no coincident/tangent merge).

TEST ARCHITECTURE (docs/known_issues.md, changelog.md): geometry for each
device config is built LAZILY (indirect parametrization on `cut_result` — a
`-k te_half` run never touches te_half_twisted) and through a disk cache
(geometry_cache.py, keyed on config content + geometry-module source) so a
re-run against unchanged config+code loads the expensive boolean output in
milliseconds instead of rebuilding it. The FAST tier below (everything not
marked `slow`) trusts the cache; the SLOW tier forces one real, uncached
rebuild per config to prove the cache still matches reality. Per-stage
construction timings land in artifacts/gates/p04_timings.json on every real
build — read that file (or `--durations=20`, on by default via `make gate`)
to diagnose a slow config; never re-run the whole gate as a stopwatch.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import yaml
from geometry_cache import get_or_build_shapes
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

from backend import tolerances
from backend.geometry.booleans import fuzzy_common, filter_shards
from backend.geometry.cove_profile import StationFeet, build_nose_arc_points, section_points
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
    hinge_frame,
)
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p04_timings.json"
te_configs = sorted(DEVICE_DIR.glob("te_*.yaml"))
DEVICE_STEMS = [p.stem for p in te_configs]


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


def _write_timings(stem: str, timings: dict) -> None:
    data = json.loads(TIMINGS_PATH.read_text()) if TIMINGS_PATH.exists() else {}
    data[stem] = timings
    TIMINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(json.dumps(data, indent=2))


@dataclass
class CutCase:
    stem: str
    config: Config
    oml: cq.Solid
    res: object  # TeCutResult
    cache_hit: bool


def _build_cut_case(stem: str, force_fresh: bool) -> CutCase:
    """Shared by both the `cut_result` (cache-backed, fast) and
    `cut_result_fresh` (force_fresh=True, slow) fixtures below. Only
    wing_shape/cs_shape — the real OCC boolean outputs, pre-shard-filter —
    go through the cache; station feet/hinge_dir are recomputed fresh every
    time (cove_profile.py's analytic sectioning is ~0.4ms/call, not worth
    caching), and finish_te_cut (filter_shards, sort, gap-volume) always
    runs fresh against whatever shapes came back, cache hit or miss."""
    config = _load(DEVICE_DIR / f"{stem}.yaml")
    oml = build_oml(build_planform_sections(config), config.planform.mirror)

    def _build_raw() -> list[cq.Shape]:
        raw = build_te_cut_shapes(config, oml)
        _write_timings(stem, raw.timings_s)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), cache_hit = get_or_build_shapes(
        config, GEOMETRY_SOURCE_FILES, ["wing_shape", "cs_shape"], _build_raw,
        force_fresh=force_fresh,
    )
    sd = _station_data(config)
    raw = TeCutRawShapes(
        wing_shape=wing_shape, cs_shape=cs_shape,
        stations=sd["feet_full"], stations_nose=sd["feet_nose"], hinge_dir=sd["h"],
        oml_volume_mm3=oml.Volume(),
    )
    return CutCase(stem=stem, config=config, oml=oml, res=finish_te_cut(raw), cache_hit=cache_hit)


def pytest_generate_tests(metafunc):
    for fixture_name in ("cut_result", "cut_result_fresh"):
        if fixture_name in metafunc.fixturenames:
            metafunc.parametrize(fixture_name, DEVICE_STEMS, indirect=True, ids=DEVICE_STEMS)


@pytest.fixture(scope="module")
def cut_result(request) -> CutCase:
    return _build_cut_case(request.param, force_fresh=False)


@pytest.fixture(scope="module")
def cut_result_fresh(request) -> CutCase:
    return _build_cut_case(request.param, force_fresh=True)


def _point_to_shell_distance(point: np.ndarray, solid) -> float:
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    dc = BRepExtrema_DistShapeShape(vertex, solid.Shells()[0].wrapped)
    dc.Perform()
    return dc.Value()


def _rotate_about_hinge(solid, p0: np.ndarray, h: np.ndarray, angle_deg: float):
    """Rigid rotation of `solid` about the real hinge line (point p0, dir h)
    by angle_deg. `cq.Solid.moved` needs a cq.Location wrapping the gp_Trsf,
    confirmed against the real API (a raw gp_Trsf is not accepted)."""
    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(*p0), gp_Dir(*h)), math.radians(angle_deg))
    return solid.moved(cq.Location(trsf))


def test_two_arc_nose_branch_no_duplicate_points():
    """Construction-level unit check (pure numpy, no OCC/OCP — cheap, so it
    runs even though no current device config exercises this branch): when
    |Ru-Rl| > NOSE_RADII_MATCH_MM, build_nose_arc_points takes the two-arc +
    Hermite-blend path. The blend's endpoints (tt=0/1) used to coincide
    exactly with the arc segments' own last/first point, producing two
    consecutive duplicate points (zero-length polygon edges) that would only
    surface as a degenerate loft edge the day a real config's camber
    asymmetry crossed the 1.0mm threshold. Assert no such duplicates, the
    true endpoints still land exactly on Pl/Pu, and the point count is
    unchanged (required for cross-station vertex-count consistency when
    lofting stations that may take different branches)."""
    a = np.array([1.0, 0.0, 0.0])
    u = np.array([0.0, 1.0, 0.0])
    feet = StationFeet(
        C=np.zeros(3), Ru=12.0, Rl=8.0,  # |Ru-Rl|=4mm > NOSE_RADII_MATCH_MM=1.0
        angle_u=2.2, angle_l=-2.0, tangent_dev_deg=0.0,
    )
    assert abs(feet.Ru - feet.Rl) > tolerances.NOSE_RADII_MATCH_MM  # confirms the branch taken

    n = 48
    pts = build_nose_arc_points(feet, a, u, n=n)
    assert pts.shape == (n, 3)

    seg_lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    assert seg_lengths.min() > 1e-6, (
        f"duplicate consecutive point(s) found — min segment length {seg_lengths.min():.2e} mm "
        f"at index {seg_lengths.argmin()} (junction blend defect)"
    )

    p_l_expected = feet.Rl * np.array([np.cos(feet.angle_l), np.sin(feet.angle_l), 0.0])
    p_u_expected = feet.Ru * np.array([np.cos(feet.angle_u), np.sin(feet.angle_u), 0.0])
    assert np.linalg.norm(pts[0] - p_l_expected) < 1e-9
    assert np.linalg.norm(pts[-1] - p_u_expected) < 1e-9


def test_exactly_two_watertight_bodies(cut_result, gate_metrics):
    res, stem = cut_result.res, cut_result.stem
    assert res.n_wing_bodies == 1, f"{stem}: expected 1 wing body, got {res.n_wing_bodies}"
    assert res.n_cs_bodies == 1, f"{stem}: expected 1 control-surface body, got {res.n_cs_bodies}"
    assert is_watertight(res.wing), f"{stem}: wing not watertight"
    assert is_watertight(res.control_surface), f"{stem}: control surface not watertight"
    gate_metrics.setdefault("bodies", {})[stem] = {
        "wing_vol_mm3": round(res.wing.Volume(), 1),
        "cs_vol_mm3": round(res.control_surface.Volume(), 1),
        "cache_hit": cut_result.cache_hit,
    }


def test_volume_conservation(cut_result, gate_metrics):
    res, stem, oml = cut_result.res, cut_result.stem, cut_result.oml
    total = res.wing.Volume() + res.control_surface.Volume() + res.gap_volume_mm3
    dev = abs(total - oml.Volume()) / oml.Volume()
    assert dev < tolerances.DEVICE_CUT_VOLUME_CONSERVATION_FRAC, (
        f"{stem}: vol(wing)+vol(CS)+vol(gap) deviates {dev*100:.3f}% from OML "
        f"(limit {tolerances.DEVICE_CUT_VOLUME_CONSERVATION_FRAC*100:.1f}%)"
    )
    gate_metrics.setdefault("conservation_pct", {})[stem] = round(dev * 100, 4)


def test_no_shards(cut_result, gate_metrics):
    res, stem = cut_result.res, cut_result.stem
    assert len(res.shards) == 0, (
        f"{stem}: {len(res.shards)} shard(s) below {tolerances.SHARD_MIN_VOLUME_MM3} mm^3 "
        f"survived (F3): {[round(s.Volume(), 3) for s in res.shards]}"
    )
    gate_metrics.setdefault("shards", {})[stem] = len(res.shards)


def test_nose_tangency(cut_result, gate_metrics):
    """The normal-foot's (C->skin) vector must be ⟂ the local skin tangent —
    the mathematical property that makes an axis-centered arc through the
    foot tangent to the skin (no solved/iterated tangency)."""
    res, stem = cut_result.res, cut_result.stem
    assert len(res.stations) >= 20, f"{stem}: only {len(res.stations)} stations (need >= 20)"
    worst = max(f.tangent_dev_deg for f in res.stations)
    assert worst < tolerances.NOSE_TANGENCY_ANGLE_TOL_DEG, (
        f"{stem}: worst normal-foot tangency deviation {worst:.2f}° "
        f"(limit {tolerances.NOSE_TANGENCY_ANGLE_TOL_DEG}°)"
    )
    gate_metrics.setdefault("nose_tangency_max_dev_deg", {})[stem] = round(worst, 3)


def test_nose_axis_centered(cut_result, gate_metrics):
    """Sealed-region (nose arc) points on the ACTUAL built CS solid — sampled
    via a real OCC section of res.control_surface, not a re-evaluation of the
    construction formula (which would trivially self-satisfy since it's the
    same arithmetic that built the points) — must sit at the per-station
    constructed radius from the hinge axis.

    A section at station C shows two regions: the nose arc (forward half,
    bulging toward the LE) and the OML's own aft/TE skin + aft box (aft half,
    toward the hinge's +a side) — only the former is "sealed region" and
    axis-centered by construction; the latter is ordinary skin at whatever
    radius the airfoil's real trailing-edge geometry has, unrelated to Ru/Rl.
    They split cleanly on angle: Pu/Pl (angle_u/angle_l) sit close to ±90°
    (normal feet from a hinge line at ~70-75% chord), so the SHORT interval
    (angle_l, angle_u) through 0 is the aft half and everything outside it
    is the nose. Tolerance is COVE_CLEARANCE_TOL_MM — the project's own
    "per-station loft interpolation" allowance (tolerances.py) — because the
    nose surface is a 48-sided polygon loft, not a true circle; at n=48 the
    facet sagitta (~0.04mm at these radii) is well inside it but well outside
    raw KERNEL_TOLERANCE_MM, which governs boolean fuzz, not deliberate
    polygon faceting."""
    res, stem, config = cut_result.res, cut_result.stem, cut_result.config
    _, _, h, a, u, _ = hinge_frame(config)
    assert len(res.stations_nose) >= 20, f"{stem}: only {len(res.stations_nose)} nose stations (need >= 20)"

    # Interior stations only: the first/last are fused with aft_box_cs at the
    # CS's flat spanwise end-cap and aren't representative of the steady-state
    # per-station cross-section.
    interior = res.stations_nose[2:-2]
    stride = max(1, len(interior) // 5)  # a handful of stations; each section costs ~5s (real OCC boolean)
    sample = interior[::stride]

    worst_dev = 0.0
    for f in sample:
        pts = section_points(res.control_surface, f.C, h)
        rel = pts - f.C
        theta = np.arctan2(rel @ u, rel @ a)
        nose_mask = (theta <= f.angle_l) | (theta >= f.angle_u)
        nose_pts = rel[nose_mask]
        assert nose_pts.shape[0] > 0, f"{stem}: no sealed-region points found at station C={f.C}"

        radius = np.linalg.norm(nose_pts, axis=1)
        lo = min(f.Ru, f.Rl) - tolerances.COVE_CLEARANCE_TOL_MM
        hi = max(f.Ru, f.Rl) + tolerances.COVE_CLEARANCE_TOL_MM
        bad = radius[(radius < lo) | (radius > hi)]
        assert bad.size == 0, (
            f"{stem}: {bad.size} sealed-region point(s) at station C={f.C} outside expected "
            f"radius band [{lo:.3f},{hi:.3f}] (worst={bad[np.argmax(np.abs(bad - (lo + hi) / 2))]:.3f})"
        )
        worst_dev = max(worst_dev, float(np.max(np.abs(radius - np.clip(radius, lo, hi)))))

    gate_metrics.setdefault("nose_axis_centered", {})[stem] = {
        "stations_checked": len(sample),
        "worst_band_dev_mm": round(worst_dev, 4),
        "Ru_range": [round(min(f.Ru for f in res.stations_nose), 2), round(max(f.Ru for f in res.stations_nose), 2)],
        "Rl_range": [round(min(f.Rl for f in res.stations_nose), 2), round(max(f.Rl for f in res.stations_nose), 2)],
    }


def test_cove_clearance_at_rest_and_deflected(cut_result, gate_metrics):
    """Min radial gap between the CS nose surface and the wing cove surface
    equals COVE_CLEARANCE_MM (construction target), both at rest (0°) and
    with the CS rotated to +max_deflection about the real hinge axis —
    proving the offset is invariant under rotation, not just true at rest.

    Sampling is restricted to vertices axially INTERIOR to the CS's spanwise
    extent [gap, axis_len-gap]. The CS is deliberately inset by gap_mm from
    the wing at each spanwise end (a separate, pre-existing clearance
    mechanism, independent of COVE_CLEARANCE_MM/F4 here) — vertices on or
    near those two flat end-caps sit close to config-specific gap_mm (e.g.
    1.5mm for te_half_twisted), which would corrupt a "==COVE_CLEARANCE_MM"
    check that's only meaningful for the RADIAL nose/cove offset. Excluding
    2*gap from each end clears both end-cap faces with margin."""
    res, stem, config = cut_result.res, cut_result.stem, cut_result.config
    p0, _, h, _, _, axis_len = hinge_frame(config)
    gap = config.te_surface.gap_mm
    s_lo, s_hi = 2 * gap, axis_len - 2 * gap

    def min_clearance(cs_solid) -> float:
        worst = math.inf
        # Subsample for speed; the min over vertices is a safe lower bound
        # proxy since the nose surface is polygon-faceted (flat between them).
        for v in list(cs_solid.Vertices())[::3]:
            p = np.array(v.toTuple())
            s = float(np.dot(p - p0, h))  # axial position is rotation-invariant about h
            if s < s_lo or s > s_hi:
                continue
            d = _point_to_shell_distance(p, res.wing)
            worst = min(worst, d)
        assert worst < math.inf, f"{stem}: no interior vertices sampled in s∈[{s_lo:.1f},{s_hi:.1f}]"
        return worst

    rest_clearance = min_clearance(res.control_surface)

    rotated = _rotate_about_hinge(res.control_surface, p0, h, config.te_surface.max_deflection_deg)
    deflected_clearance = min_clearance(rotated)

    for label, clearance in [("0deg", rest_clearance), ("deflected", deflected_clearance)]:
        assert abs(clearance - tolerances.COVE_CLEARANCE_MM) < tolerances.COVE_CLEARANCE_TOL_MM, (
            f"{stem} [{label}]: min nose-cove clearance {clearance:.3f} mm != "
            f"{tolerances.COVE_CLEARANCE_MM} mm (tol {tolerances.COVE_CLEARANCE_TOL_MM})"
        )

    gate_metrics.setdefault("cove_clearance_mm", {})[stem] = {
        "rest": round(rest_clearance, 3),
        "deflected": round(deflected_clearance, 3),
    }


def test_no_interbody_tangency(cut_result, gate_metrics):
    """F4: wing ∩ CS must be empty — no coincident/tangent face merge."""
    res, stem = cut_result.res, cut_result.stem
    common = fuzzy_common(res.wing, res.control_surface)
    kept, _ = filter_shards(common)
    assert not kept, f"{stem}: wing and CS overlap ({[round(s.Volume(),4) for s in kept]} mm^3) — F4 violation"
    gate_metrics.setdefault("interbody_overlap", {})[stem] = 0


@pytest.mark.slow
def test_fresh_build_matches_gate_criteria(cut_result_fresh, gate_metrics):
    """Slow tier: force one real, uncached rebuild per config (bypassing the
    cache both for reading AND — force_fresh — it still refreshes the cache
    afterward) and re-check the core P4 pass criteria. Proves the fast
    tier's cache genuinely reflects what a real build produces right now,
    not a stale entry from before some local edit that didn't happen to
    touch a hashed source file. Marked `slow` so a developer can run
    `-m "not slow"` for quick iteration; `make gate`/`make regress` run
    everything, including this, every time — nothing here is optional for
    declaring the phase done."""
    res, stem, oml = cut_result_fresh.res, cut_result_fresh.stem, cut_result_fresh.oml
    assert res.n_wing_bodies == 1, f"{stem}: expected 1 wing body, got {res.n_wing_bodies}"
    assert res.n_cs_bodies == 1, f"{stem}: expected 1 control-surface body, got {res.n_cs_bodies}"
    assert is_watertight(res.wing), f"{stem}: wing not watertight (fresh build)"
    assert is_watertight(res.control_surface), f"{stem}: control surface not watertight (fresh build)"
    total = res.wing.Volume() + res.control_surface.Volume() + res.gap_volume_mm3
    dev = abs(total - oml.Volume()) / oml.Volume()
    assert dev < tolerances.DEVICE_CUT_VOLUME_CONSERVATION_FRAC, (
        f"{stem}: fresh-build conservation deviates {dev*100:.3f}%"
    )
    assert len(res.shards) == 0, f"{stem}: fresh build produced {len(res.shards)} shard(s)"
    gate_metrics.setdefault("slow_tier_fresh_build", {})[stem] = {"conservation_pct": round(dev * 100, 4)}
