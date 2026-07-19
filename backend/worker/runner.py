"""P10 job entry point — the `target` callable backend/worker/sandbox.py's
`start_job`/`run_job` spawn into a subprocess (F2: OCC failures are often
segfaults, not exceptions, so this always runs inside sandbox.py's
child-process boundary, never called directly by the API).

Signature matches sandbox._child_entry's own call convention exactly:
`target(job_id, checkpoint_writer, *args)` — `checkpoint_writer(stage: str)`
IS `backend.pipeline.build_wing`'s `on_stage` callback (writes
`{"stage": ...}` to the job row + a Redis heartbeat on every call, sandbox.py
module docstring), so the same stage names backend/pipeline.py already emits
("sections", "oml", "device_cut", "sandwich", ...) are what a client polling
GET /jobs/{id} or the WS progress stream sees, with no separate progress
vocabulary invented here.

`config_dict` (plain dict, not a Config) is what crosses the multiprocessing
'spawn' boundary — re-validated with Config.model_validate inside the child,
never pickling a pydantic model across the fork (sandbox.py's own module
docstring: spawn gets a fresh interpreter).
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from backend import artifact_store
from backend.exporters.mesh_export import write_gltf, write_stl
from backend.exporters.step_export import write_assembly_step
from backend.pipeline import build_wing
from backend.schema.db import session_scope
from backend.schema.models import Config
from backend.worker import jobs as job_ops


def run_geometry_job(
    job_id: uuid.UUID, checkpoint_writer: Callable[[str], None], config_dict: dict,
) -> None:
    config = Config.model_validate(config_dict)
    build = build_wing(config, on_stage=checkpoint_writer)

    out_dir = artifact_store.job_dir(job_id)

    checkpoint_writer("export_gltf")
    gltf_path = out_dir / artifact_store.GLTF_FILENAME
    write_gltf([(b.contract_name, b.shape) for b in build.named_bodies], str(gltf_path))

    artifacts: dict = {"gltf": artifact_store.GLTF_FILENAME}

    if "step" in config.output.formats:
        checkpoint_writer("export_step")
        step_path = out_dir / artifact_store.STEP_FILENAME
        write_assembly_step(build.named_bodies, str(step_path))
        artifacts["step"] = artifact_store.STEP_FILENAME

    if "stl" in config.output.formats:
        checkpoint_writer("export_stl")
        stl_dir = out_dir / "stl"
        stl_dir.mkdir(parents=True, exist_ok=True)
        stl_files = {}
        for b in build.named_bodies:
            fname = artifact_store.safe_stl_filename(b.contract_name)
            write_stl(b.shape, str(stl_dir / fname))
            stl_files[b.contract_name] = f"stl/{fname}"
        artifacts["stl"] = stl_files

    manifest = {
        "job_id": str(job_id),
        "bodies": [
            {"contract_name": b.contract_name, "body_name": b.body_name,
             "role": b.role, "segment": b.segment, "has_sub_faces": bool(b.sub_faces)}
            for b in build.named_bodies
        ],
        "kinematics": (
            {
                "axis_p0": build.kinematics.axis_p0,
                "axis_dir": build.kinematics.axis_dir,
                "max_deflection_deg": build.kinematics.max_deflection_deg,
                "wing_body_names": build.kinematics.wing_body_names,
                "cs_body_names": build.kinematics.cs_body_names,
            }
            if build.kinematics is not None else None
        ),
        "warnings": build.warnings,
        "timings_s": build.timings_s,
        "artifacts": artifacts,
    }
    (out_dir / artifact_store.MANIFEST_FILENAME).write_text(json.dumps(manifest, indent=2))

    with session_scope() as session:
        job_ops.set_artifact_manifest(session, job_id, manifest)

    checkpoint_writer("done")
