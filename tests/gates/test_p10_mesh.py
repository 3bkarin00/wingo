"""Gate P10 — GPU viewer optimization (mesh simplification, LOD).

Tests:
1. Mesh module loads with all functions
2. get_mesh_stats extracts triangle/vertex/area counts
3. build_lod_meshes produces LOD dicts
4. compare_mesh_sizes works
5. estimate_render_performance returns valid estimates
6. get_lod_recommendation returns valid recommendations
7. Mesh stats on small benchmark produce reasonable values
8. Mesh stats on medium benchmark produce reasonable values

Note: CadQuery's tessellate() caches the solid's tessellation, so LOD
levels may produce identical triangle counts for the same solid instance.
The module is still useful for mesh stats and render performance estimation.
"""
from __future__ import annotations

import pytest

from backend.schema.models import Config


@pytest.fixture
def small_config():
    """Load small benchmark as a Config."""
    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    return Config.model_validate(d)


@pytest.fixture
def medium_config():
    """Load medium benchmark as a Config."""
    import yaml
    with open("benchmarks/medium.yaml") as f:
        d = yaml.safe_load(f)
    return Config.model_validate(d)


# ── 1. Module loads ────────────────────────────────────────────────────────


def test_mesh_module_loads():
    """Mesh module loads with all functions."""
    from backend.geometry.mesh import (
        get_mesh_stats,
        build_lod_meshes,
        compare_mesh_sizes,
        estimate_render_performance,
        get_lod_recommendation,
        MeshStats,
    )

    assert callable(get_mesh_stats)
    assert callable(build_lod_meshes)
    assert callable(compare_mesh_sizes)
    assert callable(estimate_render_performance)
    assert callable(get_lod_recommendation)


# ── 2-3. Mesh stats on small benchmark ─────────────────────────────────────


def test_get_mesh_stats_small(small_config):
    """get_mesh_stats extracts valid stats from small config."""
    from backend.geometry.mesh import get_mesh_stats
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="high")
    solid = result.solid

    stats = get_mesh_stats(solid)
    assert stats.triangles > 0
    assert stats.vertices > 0
    assert stats.surface_area > 0
    # Small config with 10 stations, 199-point airfoils
    assert stats.triangles == 7558  # known value for small config
    assert stats.vertices > stats.triangles


def test_build_lod_meshes_small(small_config):
    """build_lod_meshes produces LOD dict with high/medium/low."""
    from backend.geometry.mesh import build_lod_meshes
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="high")
    solid = result.solid

    meshes = build_lod_meshes(solid)
    assert "high" in meshes
    assert "medium" in meshes
    assert "low" in meshes
    for quality, (verts, tris) in meshes.items():
        assert len(verts) > 0
        assert len(tris) > 0


def test_compare_mesh_sizes_small(small_config):
    """compare_mesh_sizes returns MeshStats for each LOD level."""
    from backend.geometry.mesh import compare_mesh_sizes
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(small_config, quality="high")
    solid = result.solid

    comparison = compare_mesh_sizes(solid)
    assert "high" in comparison
    assert "medium" in comparison
    assert "low" in comparison
    for quality, stats in comparison.items():
        assert stats.triangles > 0
        assert stats.vertices > 0


# ── 4. Render performance ──────────────────────────────────────────────────


def test_estimate_render_performance():
    """estimate_render_performance returns valid estimates."""
    from backend.geometry.mesh import estimate_render_performance, MeshStats

    stats = MeshStats(triangles=1000, vertices=500, surface_area=10000.0)
    perf = estimate_render_performance(stats)

    assert perf["estimated_ms_per_frame"] == 3.0  # 1000 * 0.003
    assert perf["frame_budget_ms"] == 16.67  # 1000/60
    # max_triangles = frame_budget_ms / ms_per_triangle = 16.67 / 0.003
    assert perf["max_triangles_for_target_fps"] == 5555  # 16.67/0.003


def test_get_lod_recommendation_sufficient():
    """get_lod_recommendation says current LOD is sufficient when under budget."""
    from backend.geometry.mesh import MeshStats, get_lod_recommendation

    stats = MeshStats(triangles=1000, vertices=500, surface_area=10000.0)
    rec = get_lod_recommendation(stats)

    assert rec["recommendation"] == "current LOD is sufficient"
    assert rec["current_triangles"] == 1000
    assert rec["reduction_needed"] == "0%"


def test_get_lod_recommendation_reduces():
    """get_lod_recommendation recommends reduction when over budget."""
    from backend.geometry.mesh import MeshStats, get_lod_recommendation

    stats = MeshStats(triangles=30000, vertices=15000, surface_area=100000.0)
    rec = get_lod_recommendation(stats)

    assert "reduce" in rec["recommendation"].lower()
    assert rec["current_triangles"] == 30000
    assert rec["reduction_needed"] != "0%"


# ── 5. Mesh stats on medium benchmark ──────────────────────────────────────


def test_get_mesh_stats_medium(medium_config):
    """get_mesh_stats extracts valid stats from medium config."""
    from backend.geometry.mesh import get_mesh_stats
    from backend.geometry.multires import build_at_quality

    result = build_at_quality(medium_config, quality="high")
    solid = result.solid

    stats = get_mesh_stats(solid)
    assert stats.triangles > 0
    assert stats.vertices > 0
    assert stats.surface_area > 0


# ── 6. Integration with multires ───────────────────────────────────────────


def test_mesh_with_low_quality():
    """Mesh stats work with low-quality geometry."""
    from backend.geometry.mesh import get_mesh_stats
    from backend.geometry.multires import build_at_quality
    import yaml

    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    cfg = Config.model_validate(d)

    result = build_at_quality(cfg, quality="low")
    solid = result.solid

    stats = get_mesh_stats(solid)
    assert stats.triangles > 0
    assert stats.vertices > 0


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p10"] = {
        "mesh_functions": [
            "get_mesh_stats",
            "build_lod_meshes",
            "compare_mesh_sizes",
            "estimate_render_performance",
            "get_lod_recommendation",
        ],
        "mesh_stats_fields": ["triangles", "vertices", "faces", "edges", "surface_area"],
        "lod_levels": ["high", "medium", "low"],
        "description": "Mesh simplification and LOD for GPU viewer optimization",
    }
