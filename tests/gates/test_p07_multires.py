"""Gate P07 — Multi-resolution geometry (quality levels, preview vs export).

Tests:
1. build_at_quality loads with all quality presets
2. Low quality produces valid geometry (fewer points, faster)
3. High quality produces valid geometry (full resolution)
4. Low quality is faster than high quality (speedup verified)
5. Low and high quality produce solids with same face/edge topology class
6. build_preview returns low quality
7. build_export returns high quality
8. Unknown quality raises ValueError
9. resample_override forces specific point count
10. MultiResResult has correct fields
"""
from __future__ import annotations

import pytest

from backend.schema.models import Config


@pytest.fixture
def small_config():
    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    return Config.model_validate(d)


@pytest.fixture
def medium_config():
    import yaml
    with open("benchmarks/medium.yaml") as f:
        d = yaml.safe_load(f)
    return Config.model_validate(d)


# ── 1. Module loads ────────────────────────────────────────────────────────


def test_multires_module_loads():
    """Multires module loads with all functions and presets."""
    from backend.geometry.multires import (
        build_at_quality,
        build_preview,
        build_export,
        MultiResResult,
        QUALITY_PRESETS,
    )

    assert callable(build_at_quality)
    assert callable(build_preview)
    assert callable(build_export)
    assert "low" in QUALITY_PRESETS
    assert "medium" in QUALITY_PRESETS
    assert "high" in QUALITY_PRESETS


# ── 2. Low quality geometry ────────────────────────────────────────────────


def test_build_at_quality_low_returns_solid(small_config):
    """build_at_quality(quality='low') returns a valid solid."""
    from backend.geometry.multires import build_at_quality, MultiResResult

    result = build_at_quality(small_config, quality="low")
    assert isinstance(result, MultiResResult)
    assert result.solid is not None
    assert result.solid.Volume() > 0
    assert result.quality == "low"
    assert result.airfoil_points == 51  # QUALITY_PRESETS["low"][0]


def test_build_at_quality_low_metrics(small_config):
    """Low quality metrics include sections_ms, loft_ms, total_ms."""
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="low")
    assert "sections_ms" in result.metrics
    assert "loft_ms" in result.metrics
    assert "total_ms" in result.metrics
    assert result.metrics["quality"] == "low"
    assert result.metrics["airfoil_points"] == 51


def test_build_at_quality_low_no_watertight(small_config):
    """Low quality does not compute watertight or volume."""
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="low")
    assert result.watertight is None
    assert result.volume is None


# ── 3. High quality geometry ───────────────────────────────────────────────


def test_build_at_quality_high_returns_solid(small_config):
    """build_at_quality(quality='high') returns a valid solid with watertight."""
    from backend.geometry.multires import build_at_quality, MultiResResult

    result = build_at_quality(small_config, quality="high")
    assert isinstance(result, MultiResResult)
    assert result.solid is not None
    assert result.solid.Volume() > 0
    assert result.quality == "high"
    assert result.airfoil_points == 199  # QUALITY_PRESETS["high"][0]
    assert result.watertight is True
    assert result.volume is not None


def test_build_at_quality_high_metrics(small_config):
    """High quality metrics include all stages including watertight_ms, volume_ms."""
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="high")
    assert "watertight_ms" in result.metrics
    assert "volume_ms" in result.metrics
    assert "volume_mm3" in result.metrics
    assert result.metrics["face_count"] > 0
    assert result.metrics["edge_count"] > 0


# ── 4. Speedup verified ───────────────────────────────────────────────────


def test_low_faster_than_high(small_config):
    """Low quality total_ms < high quality total_ms."""
    from backend.geometry.multires import build_at_quality

    low = build_at_quality(small_config, quality="low")
    high = build_at_quality(small_config, quality="high")

    assert low.metrics["total_ms"] < high.metrics["total_ms"]


def test_low_speedup_ratio(small_config):
    """Low quality is at least 1.2x faster than high quality."""
    from backend.geometry.multires import build_at_quality

    low = build_at_quality(small_config, quality="low")
    high = build_at_quality(small_config, quality="high")

    speedup = high.metrics["total_ms"] / low.metrics["total_ms"]
    assert speedup >= 1.2


# ── 5. Consistent topology ────────────────────────────────────────────────


def test_low_high_same_face_count(small_config):
    """Low and high quality produce solids with same face/edge topology class."""
    from backend.geometry.multires import build_at_quality

    low = build_at_quality(small_config, quality="low")
    high = build_at_quality(small_config, quality="high")

    # Both should be valid solids with same number of faces/edges
    # (different tessellation doesn't change topology)
    assert low.face_count == high.face_count
    assert low.edge_count == high.edge_count


# ── 6. Convenience functions ───────────────────────────────────────────────


def test_build_preview_returns_low():
    """build_preview() returns a MultiResResult with quality='low'."""
    from backend.geometry.multires import build_preview
    import yaml

    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    cfg = Config.model_validate(d)

    result = build_preview(cfg)
    assert result.quality == "low"
    assert result.airfoil_points == 51
    assert result.solid is not None


def test_build_export_returns_high():
    """build_export() returns a MultiResResult with quality='high'."""
    from backend.geometry.multires import build_export
    import yaml

    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    cfg = Config.model_validate(d)

    result = build_export(cfg)
    assert result.quality == "high"
    assert result.airfoil_points == 199
    assert result.watertight is True


# ── 7. Error handling ─────────────────────────────────────────────────────


def test_unknown_quality_raises():
    """build_at_quality(quality='unknown') raises ValueError."""
    from backend.geometry.multires import build_at_quality
    import yaml

    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    cfg = Config.model_validate(d)

    with pytest.raises(ValueError, match="Unknown quality"):
        build_at_quality(cfg, quality="unknown")


# ── 8. Resample override ──────────────────────────────────────────────────


def test_resample_override_forces_points(small_config):
    """resample_override forces a specific point count regardless of quality."""
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="low", resample_override=99)
    assert result.airfoil_points == 99
    assert result.solid is not None
    assert result.solid.Volume() > 0


# ── 9. Medium quality ─────────────────────────────────────────────────────


def test_medium_quality(small_config):
    """Medium quality produces valid geometry with correct preset values."""
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="medium")
    assert result.quality == "medium"
    assert result.airfoil_points == 127  # QUALITY_PRESETS["medium"][0]
    assert result.solid is not None
    assert result.solid.Volume() > 0


# ── 10. MultiResResult fields ─────────────────────────────────────────────


def test_multires_result_has_required_fields(small_config):
    """MultiResResult has solid, quality, airfoil_points, metrics, watertight, volume."""
    from backend.geometry.multires import build_at_quality, MultiResResult

    result = build_at_quality(small_config, quality="high")
    assert isinstance(result, MultiResResult)
    assert hasattr(result, "solid")
    assert hasattr(result, "quality")
    assert hasattr(result, "airfoil_points")
    assert hasattr(result, "metrics")
    assert hasattr(result, "watertight")
    assert hasattr(result, "volume")


# ── 11. Medium config ─────────────────────────────────────────────────────


def test_medium_config_all_qualities(medium_config):
    """All quality levels produce valid geometry on medium config."""
    from backend.geometry.multires import build_at_quality

    for quality in ["low", "medium", "high"]:
        result = build_at_quality(medium_config, quality=quality)
        assert result.solid is not None
        assert result.solid.Volume() > 0


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p07"] = {
        "quality_presets": {
            "low": {"airfoil_points": 51, "tessellation_tolerance_mm": 0.5},
            "medium": {"airfoil_points": 127, "tessellation_tolerance_mm": 0.1},
            "high": {"airfoil_points": 199, "tessellation_tolerance_mm": 0.05},
        },
        "functions": ["build_at_quality", "build_preview", "build_export"],
        "result_class": "MultiResResult",
        "description": "Multi-resolution geometry — low/medium/high quality levels for preview vs export",
    }
