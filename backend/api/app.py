"""FastAPI application — job lifecycle, config/material/airfoil CRUD, artifact serving.

End-points:
- POST   /api/jobs          — create a new geometry build job
- GET    /api/jobs/{id}     — job status / checkpoint
- GET    /api/jobs          — list jobs (paginated)
- DELETE /api/jobs/{id}     — cancel a pending/running job (best-effort)
- POST   /api/configs       — persist a config
- GET    /api/configs       — list configs
- GET    /api/configs/{id}  — get a config
- DELETE /api/configs/{id}  — delete a config
- GET    /api/materials     — CRUD for materials
- GET    /api/airfoils      — CRUD for airfoils
- GET    /api/artifacts/{job_id}/{name} — serve exported STEP/STL/glTF
- WS     /api/ws/jobs/{id}  — WebSocket for real-time progress events

Usage:
    uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.schema.db import SessionLocal, engine
from backend.schema.db_models import (
    AirfoilRow,
    ConfigRow,
    GateResultRow,
    JobRow,
    MaterialRow,
)
from backend.schema.models import Config as WingConfig

logger = logging.getLogger(__name__)

# ── WebSocket session registry ──────────────────────────────────────────────

_ws_clients: dict[uuid.UUID, list[WebSocket]] = {}  # job_id → [ws, ...]


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start background reaper on boot, stop on shutdown."""
    async def _reaper_loop():
        while True:
            try:
                from backend.worker.reaper import reap_orphaned_jobs
                reap_orphaned_jobs()
            except Exception:
                logger.exception("Reaper error")
            await asyncio.sleep(30)

    app.state.reaper_task = asyncio.create_task(_reaper_loop())
    yield
    app.state.reaper_task.cancel()
    try:
        await app.state.reaper_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="WingStructGen", version="0.4.0", lifespan=_lifespan)

# Allow the web UI (port 3000) to call the API (port 8000)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")

# ── Request / response models ───────────────────────────────────────────────


class JobCreateRequest(BaseModel):
    config: WingConfig | None = None
    config_id: uuid.UUID | None = None
    quality: str = "high"  # low | medium | high


class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    checkpoint: dict | None = None
    worker_id: str | None = None
    started_at: str | None = None
    timing: dict | None = None
    artifact_manifest: dict | None = None
    created_at: str

    model_config = {"from_attributes": True}


class ConfigRequest(BaseModel):
    schema_version: str = "0.4"
    data: dict


class ConfigResponse(BaseModel):
    id: uuid.UUID
    schema_version: str
    data: dict
    created_at: str

    model_config = {"from_attributes": True}


class MaterialRequest(BaseModel):
    name: str
    kind: str
    e1_mpa: float | None = None
    e2_mpa: float | None = None
    g12_mpa: float | None = None
    nu12: float | None = None
    density_kg_m3: float | None = None
    ply_thickness_mm: float | None = None
    allowables: dict | None = None
    is_custom: bool = False


class AirfoilRequest(BaseModel):
    name: str
    source: str
    raw_points: dict | None = None
    normalized_points: dict | None = None
    format_detected: str | None = None
    validation_flags: dict | None = None


class MaterialResponse(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    e1_mpa: float | None = None
    e2_mpa: float | None = None
    g12_mpa: float | None = None
    nu12: float | None = None
    density_kg_m3: float | None = None
    ply_thickness_mm: float | None = None
    allowables: dict | None = None
    is_custom: bool = False

    model_config = {"from_attributes": True}


class AirfoilResponse(BaseModel):
    id: uuid.UUID
    name: str
    source: str
    raw_points: dict | None = None
    normalized_points: dict | None = None
    format_detected: str | None = None
    validation_flags: dict | None = None

    model_config = {"from_attributes": True}

# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_db():
    """Yield a scoped ORM session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "jobs"


def _config_to_dict(cfg: WingConfig) -> dict:
    """Convert Config to a dict safe for JSON/Postgres JSONB.

    Handles tuple fields (e.g. Stock.slab_lwh_mm) by converting to lists.
    """
    d = cfg.model_dump(mode="json")
    # Convert any tuple values to lists for JSON compatibility
    def _convert(obj):
        if isinstance(obj, tuple):
            return list(obj)
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_convert(i) for i in obj]
        return obj
    return _convert(d)


def _broadcast(job_id: uuid.UUID, event: dict) -> None:
    """Push an event to all connected WebSocket clients for a job."""
    dead = []
    for ws in _ws_clients.get(job_id, []):
        try:
            import json as _json
            ws.send_json(_json.dumps(event))
        except Exception:
            dead.append(ws)
    for w in dead:
        if job_id in _ws_clients:
            _ws_clients[job_id].remove(w)


def _run_geometry_job(job_id: uuid.UUID, checkpoint_writer, quality: str) -> None:
    """Target function: runs the geometry pipeline for a job.

    This runs in a child process (sandbox.py) so OCC segfaults don't
    kill the API server.
    """
    from backend.geometry.multires import build_at_quality
    from backend.schema.db import session_scope
    from backend.worker import jobs as job_ops

    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is None or row.config_id is None:
            raise ValueError("Job has no config")
        cfg_row = session.get(ConfigRow, row.config_id)
        if cfg_row is None:
            raise ValueError("Config not found")
        cfg = WingConfig.model_validate(cfg_row.data)

    checkpoint_writer("building")

    # Build geometry at requested quality
    result = build_at_quality(cfg, quality=quality)

    checkpoint_writer("exporting")
    # Write artifact manifest
    manifest = {"quality": result.quality, "metrics": result.metrics}
    with session_scope() as session:
        job_ops.set_checkpoint(session, job_id, manifest)

    _broadcast(job_id, {"type": "complete", "metrics": result.metrics})


# ── Job endpoints ───────────────────────────────────────────────────────────


@router.post("/jobs")
async def create_job(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(_get_db),
) -> JobResponse:
    """Create a new geometry build job."""
    config_id = req.config_id
    if req.config is not None:
        # Persist config inline
        cfg_row = ConfigRow(
            schema_version="0.4",
            data=_config_to_dict(req.config),
        )
        db.add(cfg_row)
        db.flush()
        config_id = cfg_row.id

    job = JobRow(
        config_id=config_id,
        status="pending",
    )
    db.add(job)
    db.flush()

    background_tasks.add_task(
        _submit_job,
        job.id,
        req.quality or "high",
    )

    return JobResponse.model_validate(job)


def _submit_job(job_id: uuid.UUID, quality: str) -> None:
    """Submit a job to the worker pool (background task)."""
    from backend.worker.sandbox import start_job

    try:
        start_job(
            job_id,
            worker_id="api-0",
            target=_run_geometry_job,
            quality=quality,
        )
    except Exception:
        logger.exception("Failed to start job %s", job_id)
        from backend.schema.db import session_scope
        from backend.worker import jobs as job_ops
        with session_scope() as session:
            job_ops.set_failed(session, job_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(_get_db)) -> JobResponse:
    """Get job status and checkpoint."""
    row = db.get(JobRow, job_id)
    if row is None:
        raise HTTPException(404, "Job not found")
    return JobResponse.model_validate(row)


@router.get("/jobs")
def list_jobs(
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    db: Session = Depends(_get_db),
) -> list[JobResponse]:
    """List jobs, optionally filtered by status."""
    from sqlalchemy import desc

    q = db.query(JobRow)
    if status:
        q = q.filter(JobRow.status == status)
    q = q.order_by(desc(JobRow.created_at))
    rows = q.offset(skip).limit(limit).all()
    return [JobResponse.model_validate(r) for r in rows]


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: uuid.UUID,
    db: Session = Depends(_get_db),
) -> dict:
    """Cancel a pending job (best-effort; running jobs can't be forcibly killed yet)."""
    row = db.get(JobRow, job_id)
    if row is None:
        raise HTTPException(404, "Job not found")
    if row.status != "pending":
        raise HTTPException(409, f"Cannot cancel job with status '{row.status}'")
    row.status = "failed"
    row.checkpoint = {"cancelled": True}
    return {"status": "cancelled"}


# ── WebSocket endpoint ──────────────────────────────────────────────────────


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: uuid.UUID) -> None:
    """WebSocket for real-time job progress events."""
    await websocket.accept()
    if job_id not in _ws_clients:
        _ws_clients[job_id] = []
    _ws_clients[job_id].append(websocket)

    try:
        while True:
            # Keep the connection alive; client can send ping messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _ws_clients.get(job_id, []).remove(websocket)


# ── Config endpoints ────────────────────────────────────────────────────────


@router.post("/configs", response_model=ConfigResponse)
def create_config(
    req: ConfigRequest,
    db: Session = Depends(_get_db),
) -> ConfigResponse:
    """Persist a wing config."""
    row = ConfigRow(schema_version=req.schema_version, data=req.data)
    db.add(row)
    db.flush()
    return ConfigResponse.model_validate(row)


@router.get("/configs", response_model=list[ConfigResponse])
def list_configs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(_get_db),
) -> list[ConfigResponse]:
    from sqlalchemy import desc

    rows = (
        db.query(ConfigRow)
        .order_by(desc(ConfigRow.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [ConfigResponse.model_validate(r) for r in rows]


@router.get("/configs/{config_id}", response_model=ConfigResponse)
def get_config(config_id: uuid.UUID, db: Session = Depends(_get_db)) -> ConfigResponse:
    row = db.get(ConfigRow, config_id)
    if row is None:
        raise HTTPException(404, "Config not found")
    return ConfigResponse.model_validate(row)


@router.delete("/configs/{config_id}")
def delete_config(config_id: uuid.UUID, db: Session = Depends(_get_db)) -> dict:
    row = db.get(ConfigRow, config_id)
    if row is None:
        raise HTTPException(404, "Config not found")
    db.delete(row)
    return {"status": "deleted"}


# ── Material endpoints ──────────────────────────────────────────────────────


@router.post("/materials", response_model=MaterialResponse)
def create_material(
    req: MaterialRequest,
    db: Session = Depends(_get_db),
) -> MaterialRow:
    row = MaterialRow(**req.model_dump())
    db.add(row)
    db.flush()
    return row


@router.get("/materials", response_model=list[MaterialResponse])
def list_materials(db: Session = Depends(_get_db)) -> list[MaterialRow]:
    return db.query(MaterialRow).all()


# ── Airfoil endpoints ───────────────────────────────────────────────────────


@router.post("/airfoils", response_model=AirfoilResponse)
def create_airfoil(
    req: AirfoilRequest,
    db: Session = Depends(_get_db),
) -> AirfoilRow:
    row = AirfoilRow(**req.model_dump())
    db.add(row)
    db.flush()
    return row


@router.get("/airfoils", response_model=list[AirfoilResponse])
def list_airfoils(db: Session = Depends(_get_db)) -> list[AirfoilRow]:
    return db.query(AirfoilRow).all()


@router.post("/airfoils/upload", response_model=AirfoilResponse)
async def upload_airfoil(
    file: UploadFile,
    name: str | None = None,
    db: Session = Depends(_get_db),
) -> AirfoilRow:
    """Upload a NACA .dat airfoil file and register it in the DB."""
    if not file.filename or not file.filename.lower().endswith(".dat"):
        raise HTTPException(400, "Only .dat files accepted")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("%")]

    # Parse x,y pairs (skip header lines)
    coords = []
    for line in lines:
        parts = line.replace(",", " ").split()
        if len(parts) >= 2:
            try:
                x, y = float(parts[0]), float(parts[1])
                coords.append([x, y])
            except ValueError:
                continue

    if len(coords) < 5:
        raise HTTPException(400, f"Too few points ({len(coords)}). Need at least 5.")

    # Normalize to unit chord [0,1]
    x_min = min(c[0] for c in coords)
    x_max = max(c[0] for c in coords)
    chord = x_max - x_min if x_max != x_min else 1.0
    normalized = [[(c[0] - x_min) / chord, c[1] / chord] for c in coords]

    # Close the loop if not closed
    if normalized[0] != normalized[-1]:
        normalized.append(normalized[0])

    af_name = (name or file.filename.replace(".dat", "")).lower().replace(" ", "_")

    # Store in DB
    row = AirfoilRow(
        name=af_name,
        source="upload",
        raw_points={"count": len(coords), "format": "xy"},
        normalized_points={"count": len(normalized), "points": normalized[:200]},  # cap for DB
        format_detected="xy",
        validation_flags={"uploaded": True, "points": len(normalized)},
    )
    db.add(row)
    db.flush()
    return row


# ── Artifact serving ────────────────────────────────────────────────────────


@router.get("/artifacts/{job_id}/{name}")
async def serve_artifact(job_id: uuid.UUID, name: str) -> None:
    """Serve an exported artifact (STEP, STL, glTF) for a completed job."""
    job_dir = _ARTIFACT_DIR / str(job_id)
    path = job_dir / name
    if not path.exists():
        raise HTTPException(404, "Artifact not found")

    from fastapi.responses import FileResponse

    ext = path.suffix.lstrip(".")
    if ext == "step":
        media_type = "application/step"
    elif ext == "stl":
        media_type = "application/sla"
    elif ext in ("gltf", "glb"):
        media_type = "model/gltf+json" if ext == "gltf" else "model/gltf-binary"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        str(path),
        media_type=media_type,
        filename=path.name,
    )


# ── Report serving (P19) ──────────────────────────────────────────────────


@router.get("/reports/{job_id}")
async def serve_report(job_id: uuid.UUID) -> None:
    """Generate and serve a bilingual (EN/AR) PDF report for a job.

    Reads gate_results rows from Postgres, compiles via lualatex Docker,
    returns the PDF.
    """
    from fastapi.responses import Response

    try:
        with session_scope() as db_session:
            pdf_bytes = _generate_report(job_id, db_session)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.exception("Report generation failed for job %s", job_id)
        raise HTTPException(500, f"Report generation failed: {exc}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=report-{job_id}.pdf"},
    )


def _generate_report(job_id: uuid.UUID, db_session: Session) -> bytes:
    """Generate PDF report bytes (shared by API and gate tests)."""
    from backend.report.bilingual import generate_report as _gen
    return _gen(job_id, db_session)


# ── P21: Tessellation viewer endpoints ──────────────────────────────────────

from backend.api.tessellation import tess_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app.include_router(tess_router)
app.include_router(router)

# Serve the web UI from the frontend/dist directory
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend web UI."""
    return FileResponse(FRONTEND_DIST / "index.html")

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_static(full_path: str):
    """Serve static assets for the frontend."""
    file_path = FRONTEND_DIST / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    # For SPA routing, return index.html for non-existent files
    return FileResponse(FRONTEND_DIST / "index.html")
