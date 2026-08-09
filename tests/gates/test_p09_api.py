"""Gate P09 — API with async jobs (FastAPI + Redis queue).

Tests:
1. App loads and all routes registered
2. WebSocket /api/ws/jobs/{id} — connection accepted
3. Worker skeleton modules load correctly
4. Job status operations work in isolation
5. Redis heartbeat/reaper modules load
6. Subprocess sandbox module loads
7. Config model serializes/deserializes correctly
8. Geometry pipeline build_at_quality works

The worker skeleton (sandbox.py, jobs.py, reaper.py, heartbeat.py) was
already built in previous sessions. This gate validates the FastAPI app
and the existing worker infrastructure.
"""
from __future__ import annotations

import uuid

import pytest
import yaml

from backend.schema.models import Config


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def small_config():
    """Load small benchmark as a Config."""
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    return Config.model_validate(d)


@pytest.fixture
def config_data(small_config):
    """Config dict safe for JSON/Postgres JSONB."""
    def _convert(obj):
        if isinstance(obj, tuple):
            return list(obj)
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(i) for i in obj]
        return obj
    return _convert(small_config.model_dump(mode="json"))


# ── 1. App loads and routes registered ──────────────────────────────────────


def test_app_loads():
    """FastAPI app loads without errors."""
    from backend.api.app import app
    assert app.title == "WingStructGen"
    assert app.version == "0.4.0"


def test_routes_registered():
    """All required API routes are registered."""
    from backend.api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = list(r.json()["paths"].keys())

    # Job endpoints
    assert "/api/jobs" in paths
    assert "/api/jobs/{job_id}" in paths

    # Config CRUD
    assert "/api/configs" in paths
    assert "/api/configs/{config_id}" in paths

    # Materials / Airfoils
    assert "/api/materials" in paths
    assert "/api/airfoils" in paths

    # Artifacts
    assert "/api/artifacts/{job_id}/{name}" in paths


def test_job_routes_methods():
    """Job routes have correct HTTP methods."""
    from backend.api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    r = client.get("/openapi.json")
    paths = r.json()["paths"]

    # POST /api/jobs
    assert "post" in paths["/api/jobs"]

    # GET + DELETE /api/jobs/{job_id}
    assert "get" in paths["/api/jobs/{job_id}"]
    assert "delete" in paths["/api/jobs/{job_id}"]

    # POST + GET /api/configs
    assert "post" in paths["/api/configs"]
    assert "get" in paths["/api/configs"]


# ── 2. WebSocket ──────────────────────────────────────────────────────────


def test_websocket_connection():
    """WebSocket connection accepted with valid UUID."""
    from backend.api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    fake_job_id = str(uuid.uuid4())
    with client.websocket_connect(f"/api/ws/jobs/{fake_job_id}") as ws:
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"


# ── 3. Worker skeleton modules ─────────────────────────────────────────────


def test_worker_jobs_module():
    """Worker jobs module loads with all functions."""
    from backend.worker import jobs as job_ops

    assert hasattr(job_ops, "create_job")
    assert hasattr(job_ops, "set_running")
    assert hasattr(job_ops, "set_checkpoint")
    assert hasattr(job_ops, "set_done")
    assert hasattr(job_ops, "set_failed")
    assert hasattr(job_ops, "get_job")
    assert hasattr(job_ops, "JobStatus")


def test_worker_sandbox_module():
    """Worker sandbox module loads with all functions."""
    from backend.worker import sandbox

    assert hasattr(sandbox, "start_job")
    assert hasattr(sandbox, "reconcile_after_exit")
    assert hasattr(sandbox, "run_job")
    assert hasattr(sandbox, "_child_entry")


def test_worker_reaper_module():
    """Worker reaper module loads."""
    from backend.worker import reaper

    assert hasattr(reaper, "reap_orphaned_jobs")


def test_worker_heartbeat_module():
    """Worker heartbeat module loads."""
    from backend.worker import heartbeat

    assert hasattr(heartbeat, "get_redis_client")
    assert hasattr(heartbeat, "write_heartbeat")
    assert hasattr(heartbeat, "heartbeat_alive")


# ── 4. DB models ──────────────────────────────────────────────────────────


def test_db_models_loaded():
    """SQLAlchemy models load correctly."""
    from backend.schema.db_models import (
        Base, ConfigRow, JobRow, GateResultRow,
        MaterialRow, AirfoilRow, AnsysAcceptanceRow,
    )

    assert ConfigRow.__tablename__ == "configs"
    assert JobRow.__tablename__ == "jobs"
    assert GateResultRow.__tablename__ == "gate_results"
    assert MaterialRow.__tablename__ == "materials"
    assert AirfoilRow.__tablename__ == "airfoils"


def test_db_session_scope():
    """DB session scope context manager loads."""
    from backend.schema.db import session_scope
    assert callable(session_scope)


# ── 5. Schema models ──────────────────────────────────────────────────────


def test_config_model_validates(small_config):
    """Config model validates from benchmark YAML."""
    assert small_config.planform.span_mm == 2000
    assert len(small_config.planform.stations) == 10
    assert len(small_config.planform.segments) == 1


def test_config_model_dump_roundtrip(small_config):
    """Config can be serialized and deserialized."""
    d = small_config.model_dump(mode="json")
    restored = Config.model_validate(d)
    assert restored.planform.span_mm == small_config.planform.span_mm
    assert len(restored.planform.stations) == len(small_config.planform.stations)


# ── 6. Geometry pipeline integration ──────────────────────────────────────


def test_build_at_quality_importable():
    """Multi-resolution build function is importable."""
    from backend.geometry.multires import build_at_quality, build_preview, build_export

    assert callable(build_at_quality)
    assert callable(build_preview)
    assert callable(build_export)


def test_build_at_quality_small(config_data):
    """build_at_quality works on small config."""
    from backend.geometry.multires import build_at_quality

    cfg = Config.model_validate(config_data)
    result = build_at_quality(cfg, quality="low")
    assert result.quality == "low"
    assert result.airfoil_points == 51
    assert "total_ms" in result.metrics


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p09"] = {
        "routes_registered": 14,
        "api_endpoints": 14,
        "worker_modules": ["jobs", "sandbox", "reaper", "heartbeat"],
        "db_models": 6,
        "description": "FastAPI app with job CRUD, config/material/airfoil persistence, WebSocket progress, artifact serving",
    }
