"""P4 gate — plan.md §9 pass criteria + the refined per-station cove/nose
construction (docs/decisions/ADR-002, ADR-003, docs/r0_findings/p04.md):

  exactly 2 watertight bodies; vol(wing)+vol(CS)+vol(gap) = vol(P2) within
  0.5%; shard filter reports 0 bodies below min-volume threshold (F3); cove
  clearance present (no tangent face pairs, F4) — verified as an exact
  radial offset (COVE_CLEARANCE_MM) rather than a coarse cylinder-radius gap.

ADR-003 replaced the two-arc + Hermite-blend nose construction with a SINGLE
arc at R=(Ru+Rl)/2, fed by a hinge axis whose height is now DERIVED (least-
squares fit to the true equidistant-from-skin point at many stations,
backend/geometry/reference.py) rather than a 2-point camber-line mean. Root
cause of the retired construction: the two-arc branch fired on nearly every
station of a twisted config, and its G1-only blend was tangent- but not
curvature-continuous — a real, visible lump, confirmed geometric (not a
rendering artifact) via a tessellation-tolerance rule-out and a discrete
curvature-angle proxy (docs/r0_findings/p04.md).

  - nose_is_single_arc: sealed-region points on the REAL built solid sit at
    ONE constant radius (not a min/max band) — the direct "is this actually
    a circle" check;
  - nose_tangency: the single arc's mean-radius deviation from the true
    per-side radius stays under NOSE_TANGENCY_MAX_DEG at >=20 stations —
    the same metric config-time validation already enforces, re-verified
    here as a gate with its own reporting;
  - axis_equidistant_residual: the derived-axis least-squares fit residual,
    reported (never hidden) with a loose sanity bound;
  - loft_topology_uniform: every station profile has identical point count
    before lofting (also a hard precondition in te_cut.py's _loft_region —
    this re-verifies it at the gate level);
  - nose_surface_smoothness: the DIRECT regression test for the original
    bug — a discrete curvature-angle proxy along the raw nose profile must
    stay smooth (no spike), on both untwisted and twisted-but-valid configs;
  - no_unporting: the nose arc's angular extension still overlaps the true
    tangent point by >= OVERLAP_MARGIN_DEG after rotating +/-max_deflection
    about the real hinge axis;
  - cove_clearance: min radial gap between nose and cove == COVE_CLEARANCE_MM,
    at 0 deg AND at the CS rotated to +max_deflection;
  - no_interbody_tangency: wing ^ CS is empty (no coincident/tangent merge);
  - extreme_twist_config_rejected: te_half_twisted.yaml (deliberately too
    aggressive for a straight hinge axis at its hinge_xc) must be REJECTED
    by config-time validation, not silently built with a degraded shape.

TEST ARCHITECTURE (docs/known_issues.md, changelog.md): geometry for each
device config is built LAZILY (indirect parametrization on `cut_result` — a
`-k te_half` run never touches other configs) and through a disk cache
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
from backend.geometry.cove_profile import (
    build_nose_arc_points,
    mean_radius_tangency_err_deg,
    section_points,
)
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.reference import derive_hinge_axis
from backend.geometry.sections import build_planform_sections
from backend.geometry.te_cut import (
    GEOMETRY_SOURCE_FILES,
    TeCutRawShapes,
    _station_data,
    build_te_cut_shapes,
    finish_te_cut,
    hinge_frame,
)
from backend.schema.errors import ConfigErrorCode, ConfigValidationError
from backend.schema.models import Config

pytestmark = pytest.mark.timeout(tolerances.GEOMETRY_TEST_TIMEOUT_S)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
TIMINGS_PATH = REPO_ROOT / "artifacts" / "gates" / "p04_timings.json"
te_configs = sorted(DEVICE_DIR.glob("te_*.yaml"))

# te_half_twisted.yaml is a DELIBERATE negative case (ADR-003): -8deg tip
# twist at a realistic aft hinge_xc measures ~16.75deg mean-radius tangency
# error even with the derived axis — real geometry, not a bug — so it MUST
# be rejected by config-time validation, not built. Excluded from the
# "successfully builds" fixture battery; exercised only by
# test_extreme_twist_config_rejected below. te_half_twisted_moderate.yaml
# (a real, smaller twist that DOES pass) is the "max-twist" config that
# joins the standard battery.
DEVICE_STEMS = [p.stem for p in te_configs if p.stem != "te_half_twisted"]


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


def _rotate_point_about_hinge(point: np.ndarray, p0: np.ndarray, h: np.ndarray, angle_deg: float) -> np.ndarray:
    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(*p0), gp_Dir(*h)), math.radians(angle_deg))
    v = gp_Pnt(*point).Transformed(trsf)
    return np.array([v.X(), v.Y(), v.Z()])


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
    """The single mean-radius arc (R=(Ru+Rl)/2, ADR-003) must stay within
    NOSE_TANGENCY_MAX_DEG of the true per-side radius at every nose station
    — the same metric config-time validation already enforces (te_cut.py's
    _validate_nose_tangency), re-verified here as an explicit, reported
    gate rather than trusted purely as a side effect of construction not
    raising. Also reports the normal-foot tangent_dev_deg (C->foot vs local
    skin tangent, unrelated to the mean-radius approximation and always
    small — the property that makes the arc tangent to the skin AT the
    exact feet, independent of which radius is used elsewhere along it)."""
    res, stem = cut_result.res, cut_result.stem
    assert len(res.stations_nose) >= 20, f"{stem}: only {len(res.stations_nose)} nose stations (need >= 20)"

    worst_mean_radius_err = max(mean_radius_tangency_err_deg(f) for f in res.stations_nose)
    assert worst_mean_radius_err < tolerances.NOSE_TANGENCY_MAX_DEG, (
        f"{stem}: worst mean-radius tangency error {worst_mean_radius_err:.2f}° "
        f"(limit {tolerances.NOSE_TANGENCY_MAX_DEG}°) — should have been caught by "
        f"config-time validation; this indicates the gate and the validator disagree"
    )
    worst_normal_foot_dev = max(f.tangent_dev_deg for f in res.stations_nose)
    gate_metrics.setdefault("nose_tangency", {})[stem] = {
        "worst_mean_radius_err_deg": round(worst_mean_radius_err, 3),
        "worst_normal_foot_dev_deg": round(worst_normal_foot_dev, 3),
    }


def test_nose_is_single_arc(cut_result, gate_metrics):
    """Sealed-region (nose arc) points on the ACTUAL built CS solid — sampled
    via a real OCC section of res.control_surface, not a re-evaluation of the
    construction formula (which would trivially self-satisfy) — must sit at
    ONE constant radius R from the hinge axis (ADR-003: the two-arc branch
    is deleted, so there is no Ru/Rl band to allow anymore, just a single
    value with facet tolerance).

    A section at station C shows two regions: the nose arc (forward half,
    bulging toward the LE) and the OML's own aft/TE skin + aft box (aft half,
    toward the hinge's +a side) — only the former is "sealed region" and
    axis-centered by construction. They split cleanly on angle: Pu/Pl
    (angle_u/angle_l) sit close to +/-90° (normal feet from a hinge line at
    ~70-75% chord), so the SHORT interval (angle_l, angle_u) through 0 is
    the aft half and everything outside it is the nose.

    The sample window is pulled in by the anti-unporting extension angle
    (+ a 20% buffer) from BOTH true tangent points: the extension zone is
    DELIBERATELY clipped against the real OML boundary wherever the
    constant-R arc would otherwise poke outside it there (verified — a real,
    reproducible ~0.15-0.23mm deviation right at the extension boundary on a
    twisted config, not noise: docs/r0_findings/p04.md) — that's the CS
    staying safely inside the wing's cove pocket, not a defect in the nose
    arc itself, which is what this test actually checks: the TRUE
    tangent-to-tangent sealed region, unaffected by the extension. Tolerance
    is COVE_CLEARANCE_TOL_MM — the project's own "per-station loft
    interpolation" allowance (tolerances.py) — because the nose surface is
    a 48-sided polygon loft, not a true circle."""
    res, stem, config = cut_result.res, cut_result.stem, cut_result.config
    _, _, h, a, u, _ = hinge_frame(config)
    assert len(res.stations_nose) >= 20, f"{stem}: only {len(res.stations_nose)} nose stations (need >= 20)"
    max_defl = config.te_surface.max_deflection_deg
    overlap_margin = config.te_surface.overlap_margin_deg or tolerances.OVERLAP_MARGIN_DEG
    exclude_rad = np.radians(max_defl + overlap_margin) * 1.2

    interior = res.stations_nose[2:-2]
    stride = max(1, len(interior) // 5)  # a handful of stations; each section costs ~5s (real OCC boolean)
    sample = interior[::stride]

    worst_dev = 0.0
    for f in sample:
        pts = section_points(res.control_surface, f.C, h)
        rel = pts - f.C
        theta = np.arctan2(rel @ u, rel @ a)
        nose_mask = (theta <= f.angle_l - exclude_rad) | (theta >= f.angle_u + exclude_rad)
        nose_pts = rel[nose_mask]
        assert nose_pts.shape[0] > 0, f"{stem}: no sealed-region points found at station C={f.C}"

        radius = np.linalg.norm(nose_pts, axis=1)
        dev = np.abs(radius - f.R)
        bad = dev[dev > tolerances.COVE_CLEARANCE_TOL_MM]
        assert bad.size == 0, (
            f"{stem}: {bad.size} sealed-region point(s) at station C={f.C} deviate from the "
            f"single radius R={f.R:.3f}mm by more than {tolerances.COVE_CLEARANCE_TOL_MM}mm "
            f"(worst={dev.max():.3f}mm) — not a constant-curvature single arc"
        )
        worst_dev = max(worst_dev, float(dev.max()))

    gate_metrics.setdefault("nose_is_single_arc", {})[stem] = {
        "stations_checked": len(sample),
        "worst_radius_dev_mm": round(worst_dev, 4),
    }


def test_axis_equidistant_residual(cut_result, gate_metrics):
    """The derived hinge-axis's least-squares fit residual (backend/geometry/
    reference.py: true equidistant height vs the fitted straight line) is
    REPORTED, per ADR-003's own rule ("residuals grow with twist — expected
    and bounded, not hidden"), not silently absorbed. The real safety net is
    NOSE_TANGENCY_MAX_DEG (test_nose_tangency + config-time validation); this
    test's own bound is deliberately loose (10x the max residual measured
    across both passing configs, docs/r0_findings/p04.md) — it exists to
    catch a genuinely broken axis fit (e.g. a future regression in
    derive_hinge_axis itself), not to duplicate the tangency gate."""
    stem, config = cut_result.stem, cut_result.config
    te = config.te_surface
    _, _, residuals_mm = derive_hinge_axis(
        config, te.span_start_frac, te.span_end_frac, te.hinge_xc_start, te.hinge_xc_end,
    )
    worst = float(residuals_mm.max())
    assert worst < 2.0, (  # measured worst across te_half/te_half_twisted_moderate: 0.19mm
        f"{stem}: axis-height least-squares residual {worst:.4f}mm exceeds the 2.0mm sanity "
        f"bound (10x the largest residual measured for a passing config) — likely a broken fit"
    )
    gate_metrics.setdefault("axis_equidistant_residual_mm", {})[stem] = {
        "min": round(float(residuals_mm.min()), 4),
        "max": round(worst, 4),
        "mean": round(float(residuals_mm.mean()), 4),
    }


def test_loft_topology_uniform(cut_result, gate_metrics):
    """Every station profile fed to the nose/cove loft must have identical
    point count (ADR-003 point 5) — re-verified at the gate level; the hard
    precondition lives in te_cut.py's _loft_region itself (aborts the build
    with a clear error), so reaching this assertion at all already implies
    the build succeeded, but this keeps the property explicitly reported
    and tested independent of that internal assertion ever being weakened."""
    stem, config = cut_result.stem, cut_result.config
    sd = _station_data(config)
    nose_counts = {len(p) for p in sd["nose_polys"]}
    cove_counts = {len(p) for p in sd["cove_polys"]}
    assert len(nose_counts) == 1, f"{stem}: non-uniform nose loft topology, point counts={sorted(nose_counts)}"
    assert len(cove_counts) == 1, f"{stem}: non-uniform cove loft topology, point counts={sorted(cove_counts)}"
    gate_metrics.setdefault("loft_topology", {})[stem] = {
        "nose_points_per_station": next(iter(nose_counts)),
        "cove_points_per_station": next(iter(cove_counts)),
    }


def _discrete_curvature_angle_proxy(pts: np.ndarray) -> np.ndarray:
    """Angle (deg) between consecutive segments at each interior point — a
    smooth arc has a small, roughly CONSTANT value; a curvature-discontinuous
    kink (the original bug) shows as a spike relative to its neighbors. See
    docs/r0_findings/p04.md for the diagnosis this was derived from."""
    d1 = pts[1:-1] - pts[:-2]
    d2 = pts[2:] - pts[1:-1]
    d1n = d1 / np.linalg.norm(d1, axis=1, keepdims=True)
    d2n = d2 / np.linalg.norm(d2, axis=1, keepdims=True)
    cos_a = np.clip(np.sum(d1n * d2n, axis=1), -1.0, 1.0)
    return np.degrees(np.arccos(cos_a))


def test_nose_surface_smoothness(cut_result, gate_metrics):
    """DIRECT regression test for the reported bug: a discrete curvature-
    angle proxy along the raw nose profile (construction points, independent
    of loft/tessellation) must stay smooth — no spike relative to the local
    mean. Measured baseline (docs/r0_findings/p04.md) before the fix:
    untwisted std=0.11°, spike ratio 1.1x (clean); the OLD two-arc
    construction on a twisted config: std=1.94°, spike ratio 2.6x (the
    lumpy nose). Bound set at 1.5x spike ratio — comfortably above real
    single-arc noise, comfortably below the old defect's signature."""
    res, stem, config = cut_result.res, cut_result.stem, cut_result.config
    _, _, h, a, u, _ = hinge_frame(config)
    max_defl = config.te_surface.max_deflection_deg
    overlap = config.te_surface.overlap_margin_deg or tolerances.OVERLAP_MARGIN_DEG

    worst_ratio = 0.0
    for f in res.stations_nose[::4]:  # every 4th station is plenty for a smoothness sweep
        pts = build_nose_arc_points(f, a, u, max_defl, overlap)
        kink = _discrete_curvature_angle_proxy(pts)
        ratio = float(kink.max() / max(kink.mean(), 1e-9))
        worst_ratio = max(worst_ratio, ratio)

    assert worst_ratio < 1.5, (
        f"{stem}: worst curvature-angle spike ratio {worst_ratio:.2f}x the local mean "
        f"(limit 1.5x) — nose profile shows a real curvature discontinuity, the signature "
        f"of the original lumpy-nose defect"
    )
    gate_metrics.setdefault("nose_surface_smoothness_spike_ratio", {})[stem] = round(worst_ratio, 3)


def test_no_unporting(cut_result, gate_metrics):
    """Anti-unporting angular overlap (ADR-003 addendum A): the nose arc is
    extended beyond the true tangent points Pu/Pl by (max_deflection_deg +
    overlap_margin_deg). Rotating the arc's extended endpoint by
    +/-max_deflection_deg about the REAL hinge axis and re-measuring its
    angle relative to the (unrotated) station frame must show it still lags
    the true tangent angle by >= overlap_margin_deg — i.e. the nose has not
    rotated past the cove lip and "unported" (exposed its edge to the
    airflow) at full deflection."""
    res, stem, config = cut_result.res, cut_result.stem, cut_result.config
    p0, _, h, a, u, _ = hinge_frame(config)
    max_defl = config.te_surface.max_deflection_deg
    overlap_margin = config.te_surface.overlap_margin_deg or tolerances.OVERLAP_MARGIN_DEG
    # A little slack for discretization (n=48 arc points aren't exactly at
    # the true extended angle) — matches FACE_TANGENCY_TOLERANCE_MM's order
    # of magnitude in spirit, expressed here as a small angular slack.
    slack_deg = 0.5

    interior = res.stations_nose[2:-2]
    worst_margin = math.inf
    for f in interior[::4]:
        arc = build_nose_arc_points(f, a, u, max_defl, overlap_margin)
        for sign, extreme_pt, true_angle in [(+1, arc[0], f.angle_l), (-1, arc[-1], f.angle_u)]:
            for defl in (max_defl, -max_defl):
                rotated = _rotate_point_about_hinge(extreme_pt, p0, h, defl)
                rel = rotated - f.C
                theta = float(np.arctan2(np.dot(rel, u), np.dot(rel, a)))
                # Angular distance from the true tangent angle, unwrapped to
                # the shortest signed direction.
                d = (theta - true_angle + np.pi) % (2 * np.pi) - np.pi
                remaining_margin_deg = abs(np.degrees(d))
                worst_margin = min(worst_margin, remaining_margin_deg)

    assert worst_margin >= overlap_margin - slack_deg, (
        f"{stem}: worst remaining angular overlap {worst_margin:.2f}° at full deflection "
        f"(need >= {overlap_margin - slack_deg:.2f}°) — nose may unport at max deflection"
    )
    gate_metrics.setdefault("no_unporting_worst_margin_deg", {})[stem] = round(worst_margin, 3)


def test_cove_clearance_at_rest_and_deflected(cut_result, gate_metrics):
    """Min radial gap between the CS nose surface and the wing cove surface
    equals COVE_CLEARANCE_MM (construction target), both at rest (0°) and
    with the CS rotated to +max_deflection about the real hinge axis —
    proving the offset is invariant under rotation, not just true at rest.

    Sampling is restricted to vertices axially INTERIOR to the CS's spanwise
    extent [gap, axis_len-gap]. The CS is deliberately inset by gap_mm from
    the wing at each spanwise end (a separate, pre-existing clearance
    mechanism, independent of COVE_CLEARANCE_MM/F4 here) — vertices on or
    near those two flat end-caps sit close to config-specific gap_mm, which
    would corrupt a "==COVE_CLEARANCE_MM" check that's only meaningful for
    the RADIAL nose/cove offset. Excluding 2*gap from each end clears both
    end-cap faces with margin."""
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


def test_extreme_twist_config_rejected(gate_metrics):
    """ADR-003: te_half_twisted.yaml's -8deg tip twist at hinge_xc=0.72 is
    deliberately too aggressive for a straight hinge axis — config-time
    validation MUST reject it with NOSE_TANGENCY_EXCEEDS_MAX rather than
    silently building a degraded shape. Proves the fail-fast mechanism
    actually fires, not just that it exists in source."""
    config = _load(DEVICE_DIR / "te_half_twisted.yaml")
    oml = build_oml(build_planform_sections(config), config.planform.mirror)
    with pytest.raises(ConfigValidationError) as exc_info:
        build_te_cut_shapes(config, oml)
    assert exc_info.value.code == ConfigErrorCode.NOSE_TANGENCY_EXCEEDS_MAX
    gate_metrics["extreme_twist_config_rejected"] = str(exc_info.value)


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
