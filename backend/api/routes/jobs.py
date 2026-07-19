"""Job lifecycle (§7 `jobs` table) + artifact serving + progress + the P10
kinematics-sample endpoint (plan.md §9 P10: "deflection slider animates
about correct axis (compare a tracked vertex against server-computed
position)").

Job launch: plan.md §4's architecture diagram shows the API talking to a
separate "Geometry worker" over a Redis queue; the code that actually
exists (backend/worker/sandbox.py) is a direct subprocess-spawn sandbox,
not a queue consumer — no queue/consumer loop is invented here to match
the diagram literally. `create_job` calls `sandbox.start_job` in-process,
which spawns the job's own child process and returns immediately
(non-blocking, sandbox.py's own docstring); Redis is still used exactly as
sandbox.py already wired it (heartbeats), just not as a job queue.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from backend import artifact_store
from backend.api.schemas import (
    SCHEMA_VERSION,
    JobCreateRequest,
    JobResponse,
    VertexSampleRequest,
    VertexSampleResponse,
)
from backend.geometry.kinematics import rotate_point
from backend.schema.db import session_scope
from backend.schema.db_models import ConfigRow, JobRow
from backend.schema.models import Config
from backend.worker import jobs as job_ops
from backend.worker import sandbox
from backend.worker.runner import run_geometry_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

_TERMINAL_STATUSES = {job_ops.JobStatus.DONE.value, job_ops.JobStatus.FAILED.value}


def _job_response(row: JobRow) -> JobResponse:
    return JobResponse(
        id=row.id, status=row.status, checkpoint=row.checkpoint,
        artifact_manifest=row.artifact_manifest,
    )


@router.post("", response_model=JobResponse)
def create_job(req: JobCreateRequest) -> JobResponse:
    if req.config is None and req.config_id is None:
        raise HTTPException(status_code=422, detail="either 'config' or 'config_id' is required")

    with session_scope() as session:
        if req.config is not None:
            try:
                validated = Config.model_validate(req.config)
            except Exception as exc:  # noqa: BLE001 — surfaced as a 422, not a 500
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            config_dict = validated.model_dump(mode="json")
            config_row = ConfigRow(schema_version=SCHEMA_VERSION, data=config_dict)
            session.add(config_row)
            session.flush()
            config_id = config_row.id
        else:
            config_row = session.get(ConfigRow, req.config_id)
            if config_row is None:
                raise HTTPException(status_code=404, detail="config not found")
            config_id = config_row.id
            config_dict = config_row.data

        job = job_ops.create_job(session, config_id=config_id)
        job_id = job.id

    worker_id = f"api-{os.getpid()}"
    sandbox.start_job(job_id, worker_id, run_geometry_job, config_dict)

    with session_scope() as session:
        return _job_response(job_ops.get_job(session, job_id))


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID) -> JobResponse:
    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_response(row)


@router.get("/{job_id}/kinematics")
def get_kinematics(job_id: uuid.UUID) -> dict | None:
    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        if row.artifact_manifest is None:
            raise HTTPException(status_code=409, detail="job has no artifacts yet")
        return row.artifact_manifest.get("kinematics")


@router.post("/{job_id}/kinematics/sample", response_model=VertexSampleResponse)
def sample_kinematics(job_id: uuid.UUID, req: VertexSampleRequest) -> VertexSampleResponse:
    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        manifest = row.artifact_manifest

    if manifest is None:
        raise HTTPException(status_code=409, detail="job has no artifacts yet")
    kin = manifest.get("kinematics")
    if kin is None:
        raise HTTPException(status_code=422, detail="this build has no hinge kinematics (no te_surface/hinges)")

    point = np.array(req.point_local, dtype=float)
    if req.body_name in kin["cs_body_names"]:
        p0 = np.array(kin["axis_p0"], dtype=float)
        d = np.array(kin["axis_dir"], dtype=float)
        world = rotate_point(point, p0, d, req.angle_deg)
        moved = True
    elif req.body_name in kin["wing_body_names"]:
        world = point
        moved = False
    else:
        raise HTTPException(status_code=422, detail=f"unknown body_name {req.body_name!r} for this job")

    return VertexSampleResponse(point_world=tuple(float(x) for x in world), moved=moved)


@router.get("/{job_id}/artifacts/{filename:path}")
def get_artifact(job_id: uuid.UUID, filename: str) -> FileResponse:
    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is None or row.artifact_manifest is None:
            raise HTTPException(status_code=404, detail="artifacts not ready")
        manifest = row.artifact_manifest

    allowed = {manifest["artifacts"].get("gltf"), manifest["artifacts"].get("step")}
    allowed |= set((manifest["artifacts"].get("stl") or {}).values())
    allowed.discard(None)
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="artifact not in this job's manifest")

    path = artifact_store.job_dir(job_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing on disk")
    return FileResponse(str(path))


@router.websocket("/{job_id}/ws")
async def job_progress_ws(websocket: WebSocket, job_id: uuid.UUID) -> None:
    """Progress stream (plan.md §9 P10: "progress events received") — polls
    the job row (checkpoint written by backend.pipeline.build_wing's
    on_stage callback via sandbox.py's checkpoint_writer) once a second and
    pushes only on change, until a terminal status closes the stream."""
    await websocket.accept()
    last_payload: dict | None = None
    try:
        while True:
            with session_scope() as session:
                row = job_ops.get_job(session, job_id)
                if row is None:
                    await websocket.send_json({"error": "job not found"})
                    break
                payload = {"status": row.status, "checkpoint": row.checkpoint}
                status = row.status
            if payload != last_payload:
                await websocket.send_json(payload)
                last_payload = payload
            if status in _TERMINAL_STATUSES:
                break
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    await websocket.close()
