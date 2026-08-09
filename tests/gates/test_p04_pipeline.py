"""Gate P04 — Fast/slow pipeline.

Tests that build_fast and build_full produce correct results:
1. build_fast: loft only, no watertight/volume, returns solid
2. build_full: loft + watertight + volume, returns solid + metrics
3. build() unified entry point dispatches to correct path
4. BuildResult has correct fields for each path
5. Fast path total_ms < full path total_ms (speedup verified)
6. Both paths produce solids with same face/edge counts
7. Volume deviation within tolerance on full path
"""
from __future__ import annotations

import pytest
import yaml

from backend.schema.models import Config


@pytest.fixture
def small_config():
    with open("benchmarks/small.yaml") as f:
        return Config.model_validate(yaml.safe_load(f))


@pytest.fixture
def medium_config():
    with open("benchmarks/medium.yaml") as f:
        return Config.model_validate(yaml.safe_load(f))


@pytest.fixture
def large_config():
    with open("benchmarks/large.yaml") as f:
        return Config.model_validate(yaml.safe_load(f))


# ── 1. build_fast ──────────────────────────────────────────────────────────


def test_build_fast_returns_solid(small_config):
    """build_fast returns a BuildResult with a solid."""
    from backend.geometry.pipeline import build_fast, BuildResult

    result = build_fast(small_config)
    assert isinstance(result, BuildResult)
    assert result.solid is not None
    assert result.solid.Volume() > 0


def test_build_fast_no_watertight(small_config):
    """build_fast does not perform watertight check (watertight is None)."""
    from backend.geometry.pipeline import build_fast

    result = build_fast(small_config)
    assert result.watertight is None
    assert result.volume is None


def test_build_fast_metrics(small_config):
    """build_fast metrics include loft_ms, total_ms but no topology_check_ms."""
    from backend.geometry.pipeline import build_fast

    result = build_fast(small_config)
    assert "loft_ms" in result.metrics
    assert "total_ms" in result.metrics
    assert "watertight_ms" not in result.metrics
    assert "volume_ms" not in result.metrics


# ── 2. build_full ──────────────────────────────────────────────────────────


def test_build_full_returns_solid_and_metrics(small_config):
    """build_full returns solid, watertight=True, volume, and metrics."""
    from backend.geometry.pipeline import build_full

    result = build_full(small_config)
    assert result.solid is not None
    assert result.watertight is True
    assert result.volume is not None
    assert result.volume > 0


def test_build_full_metrics(small_config):
    """build_full metrics include all pipeline stages."""
    from backend.geometry.pipeline import build_full

    result = build_full(small_config)
    assert "loft_ms" in result.metrics
    assert "watertight_ms" in result.metrics
    assert "volume_ms" in result.metrics
    assert "total_ms" in result.metrics


def test_build_full_volume_deviation(small_config):
    """Full path volume deviation within ±3% of analytic estimate."""
    from backend.geometry.pipeline import build_full

    result = build_full(small_config)
    estimate = result.metrics.get("volume_estimate_mm3")
    if estimate:
        deviation = abs(result.volume - estimate) / estimate * 100
        assert deviation < 3.0


# ── 3. build() unified entry point ─────────────────────────────────────────


def test_build_dispatches_fast(small_config):
    """build(mode='fast') dispatches to build_fast."""
    from backend.geometry.pipeline import build

    result = build(small_config, mode="fast")
    assert result.watertight is None


def test_build_dispatches_full(small_config):
    """build(mode='full') dispatches to build_full."""
    from backend.geometry.pipeline import build

    result = build(small_config, mode="full")
    assert result.watertight is True


def test_build_default_is_full(small_config):
    """build() without mode defaults to 'full'."""
    from backend.geometry.pipeline import build

    result = build(small_config)
    assert result.watertight is True


# ── 4. BuildResult fields ─────────────────────────────────────────────────


def test_build_result_has_required_fields(small_config):
    """BuildResult has all required fields."""
    from backend.geometry.pipeline import build_full, BuildResult

    result = build_full(small_config)
    assert hasattr(result, "solid")
    assert hasattr(result, "watertight")
    assert hasattr(result, "volume")
    assert hasattr(result, "metrics")
    assert hasattr(result, "face_count")
    assert hasattr(result, "edge_count")


def test_build_result_face_count_matches_solid(small_config):
    """BuildResult.face_count matches solid.Faces().Length()."""
    from backend.geometry.pipeline import build_full

    result = build_full(small_config)
    assert result.face_count == len(result.solid.Faces())


def test_build_result_edge_count_matches_solid(small_config):
    """BuildResult.edge_count matches solid.Edges().Length()."""
    from backend.geometry.pipeline import build_full

    result = build_full(small_config)
    assert result.edge_count == len(result.solid.Edges())


# ── 5. Speedup verified ───────────────────────────────────────────────────


def test_fast_path_faster_than_full(small_config):
    """Fast path total_ms < full path total_ms."""
    from backend.geometry.pipeline import build_fast, build_full

    fast = build_fast(small_config)
    full = build_full(small_config)

    assert fast.metrics["total_ms"] < full.metrics["total_ms"]


def test_fast_path_speedup_ratio(small_config):
    """Fast path is at least 1.2x faster than full path."""
    from backend.geometry.pipeline import build_fast, build_full

    fast = build_fast(small_config)
    full = build_full(small_config)

    speedup = full.metrics["total_ms"] / fast.metrics["total_ms"]
    assert speedup >= 1.2


# ── 6. Both paths produce consistent geometry ─────────────────────────────


def test_fast_full_same_face_count(small_config):
    """Fast and full paths produce solids with identical face counts."""
    from backend.geometry.pipeline import build_fast, build_full

    fast = build_fast(small_config)
    full = build_full(small_config)

    assert fast.face_count == full.face_count


def test_fast_full_same_edge_count(small_config):
    """Fast and full paths produce solids with identical edge counts."""
    from backend.geometry.pipeline import build_fast, build_full

    fast = build_fast(small_config)
    full = build_full(small_config)

    assert fast.edge_count == full.edge_count


# ── 7. Volume tolerance ───────────────────────────────────────────────────


def test_volume_within_tolerance(medium_config):
    """Volume within ±3% of analytic estimate on medium config."""
    from backend.geometry.pipeline import build_full

    result = build_full(medium_config)
    estimate = result.metrics.get("volume_estimate_mm3")
    if estimate:
        deviation = abs(result.volume - estimate) / estimate * 100
        assert deviation < 3.0


def test_watertight_on_all_sizes(small_config, medium_config, large_config):
    """All sizes produce watertight solids on full path."""
    from backend.geometry.pipeline import build_full

    for cfg in [small_config, medium_config, large_config]:
        result = build_full(cfg)
        assert result.watertight is True


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    gate_metrics["p04"] = {
        "pipeline_paths": ["fast", "full"],
        "fast_skips": ["watertight_check", "volume_computation"],
        "description": "Fast/slow pipeline — build_fast skips watertight/volume, build_full does both",
    }
