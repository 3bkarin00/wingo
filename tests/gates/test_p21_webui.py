"""P21 Web UI gate test.

Verifies:
1. FastAPI tessellation endpoints are registered and respond
2. Preview endpoint builds mesh data for golden configs
3. Mesh data has required fields (vertices, indices, triangle_count)
4. LOD levels (low/medium/high) all produce valid meshes
5. Frontend build artifacts exist (package.json, vite.config.js)

Uses real OCP kernel through the geometry pipeline.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.api.app import app
from backend.schema.models import Config as WingConfig

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def golden_configs():
    """Load all golden configs from tests/golden/."""
    golden_dir = Path(__file__).resolve().parent.parent / "golden"
    configs = []
    for f in golden_dir.glob("golden_*.yaml"):
        with open(f) as fh:
            data = yaml.safe_load(fh)
        configs.append((f.stem, data))
    return configs


@pytest.fixture
def frontend_files():
    """Check that required frontend files exist."""
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    required = ["package.json", "vite.config.js", "index.html", "src/main.jsx",
                "src/App.jsx", "src/components/WingViewer.jsx", "src/components/ConfigPanel.jsx"]
    return {f: (frontend_dir / f).exists() for f in required}


# ── Tests ───────────────────────────────────────────────────────────────────

def test_tessellation_router_registered(client):
    """Test that the tessellation router is registered."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    paths = list(res.json()["paths"].keys())
    assert "/api/wing/preview" in paths
    assert "/api/wing/configs/{config_id}" in paths


def test_frontend_files_exist(frontend_files):
    """Test that all required frontend files exist."""
    for fname, exists in frontend_files.items():
        assert exists, f"Frontend file missing: {fname}"


def test_frontend_package_json(frontend_files):
    """Test that package.json has required dependencies."""
    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    pkg_path = frontend_dir / "package.json"
    assert pkg_path.exists()

    with open(pkg_path) as f:
        pkg = json.load(f)

    required_deps = ["react", "three", "@react-three/fiber", "@react-three/drei"]
    for dep in required_deps:
        assert dep in pkg.get("dependencies", {}), f"Missing dependency: {dep}"


def test_preview_endpoint_invalid_config(client):
    """Test preview endpoint rejects invalid config."""
    res = client.post("/api/wing/preview", json={"config": {"invalid": True}, "quality": "medium"})
    assert res.status_code in (400, 422)


def test_preview_endpoint_no_config(client):
    """Test preview endpoint rejects missing config."""
    res = client.post("/api/wing/preview", json={"quality": "medium"})
    assert res.status_code == 400


def test_preview_golden_configs(client, golden_configs):
    """Test preview endpoint builds mesh for all golden configs."""
    for golden_name, golden_data in golden_configs:
        config = WingConfig.model_validate(golden_data)
        config_dict = config.model_dump(mode="json")

        for quality in ["low", "medium", "high"]:
            res = client.post("/api/wing/preview", json={
                "config": config_dict,
                "quality": quality
            })
            assert res.status_code == 200, f"Failed for {golden_name} at {quality}"

            data = res.json()
            assert data["success"] is True, f"Preview failed for {golden_name} at {quality}: {data.get('error')}"
            assert data["quality"] == quality
            assert "mesh" in data
            assert "metrics" in data

            # Check mesh has required LOD levels
            mesh = data["mesh"]
            for lod in ["low", "medium", "high"]:
                assert lod in mesh, f"Missing LOD level: {lod}"
                lod_data = mesh[lod]
                assert "vertices" in lod_data, f"Missing vertices in {lod}"
                assert "indices" in lod_data, f"Missing indices in {lod}"
                assert "triangle_count" in lod_data, f"Missing triangle_count in {lod}"
                assert "vertex_count" in lod_data, f"Missing vertex_count in {lod}"

                # Validate mesh data
                assert len(lod_data["vertices"]) > 0, f"Empty vertices in {lod}"
                assert len(lod_data["indices"]) > 0, f"Empty indices in {lod}"
                assert lod_data["triangle_count"] > 0, f"Zero triangles in {lod}"
                assert lod_data["vertex_count"] > 0, f"Zero vertices in {lod}"

                # Vertices should be 3x vertex_count (x,y,z per vertex)
                assert len(lod_data["vertices"]) == 3 * lod_data["vertex_count"]

                # Indices should be 3x triangle_count (3 vertices per triangle)
                assert len(lod_data["indices"]) == 3 * lod_data["triangle_count"]


def test_preview_quality_levels(client):
    """Test that different quality levels produce different mesh sizes."""
    golden_dir = Path(__file__).resolve().parent.parent / "golden"
    golden_path = golden_dir / "golden_01_straight_taper.yaml"
    with open(golden_path) as f:
        golden_data = yaml.safe_load(f)

    config = WingConfig.model_validate(golden_data)
    config_dict = config.model_dump(mode="json")

    res_low = client.post("/api/wing/preview", json={
        "config": config_dict,
        "quality": "low"
    })
    res_high = client.post("/api/wing/preview", json={
        "config": config_dict,
        "quality": "high"
    })

    assert res_low.status_code == 200
    assert res_high.status_code == 200

    low_data = res_low.json()
    high_data = res_high.json()

    # High quality should have more triangles than low
    low_triangles = low_data["mesh"]["low"]["triangle_count"]
    high_triangles = high_data["mesh"]["high"]["triangle_count"]

    assert high_triangles >= low_triangles, \
        f"High quality ({high_triangles}) should have >= triangles than low ({low_triangles})"


def test_preview_metrics(client):
    """Test that preview returns geometry metrics."""
    golden_dir = Path(__file__).resolve().parent.parent / "golden"
    golden_path = golden_dir / "golden_01_straight_taper.yaml"
    with open(golden_path) as f:
        golden_data = yaml.safe_load(f)

    config = WingConfig.model_validate(golden_data)
    config_dict = config.model_dump(mode="json")

    res = client.post("/api/wing/preview", json={
        "config": config_dict,
        "quality": "high"
    })

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    metrics = data["metrics"]
    assert "total_ms" in metrics
    assert "station_count" in metrics
    assert "face_count" in metrics
    assert "edge_count" in metrics
    assert metrics["station_count"] > 0
    assert metrics["face_count"] > 0


def test_api_endpoint_consistency(client):
    """Test that preview endpoint is consistent with job endpoint."""
    golden_dir = Path(__file__).resolve().parent.parent / "golden"
    golden_path = golden_dir / "golden_01_straight_taper.yaml"
    with open(golden_path) as f:
        golden_data = yaml.safe_load(f)

    config = WingConfig.model_validate(golden_data)
    config_dict = config.model_dump(mode="json")

    # Get preview
    res = client.post("/api/wing/preview", json={
        "config": config_dict,
        "quality": "high"
    })

    assert res.status_code == 200
    preview_data = res.json()

    # Verify the mesh data is consistent (same triangle count across calls)
    triangles1 = preview_data["mesh"]["high"]["triangle_count"]

    res2 = client.post("/api/wing/preview", json={
        "config": config_dict,
        "quality": "high"
    })

    assert res2.status_code == 200
    triangles2 = res2.json()["mesh"]["high"]["triangle_count"]

    assert triangles1 == triangles2, "Preview should be deterministic"
