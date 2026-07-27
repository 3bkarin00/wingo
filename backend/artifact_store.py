"""Shared job-artifact filesystem layout (plan.md §4 "Storage: artifacts on
shared volume keyed by job ID") — one place both the worker (writes files,
backend/worker/runner.py) and the API (serves files, backend/api/routes/
jobs.py) agree on, so the path can never drift between the two sides of the
process-spawn boundary.

ARTIFACT_ROOT from the environment (matches backend/schema/db.py's
DATABASE_URL pattern — never hardcoded, so a real deployment can point this
at the actual shared volume without a code change).
"""
import os
import re
import uuid
from pathlib import Path

ARTIFACT_ROOT = Path(os.environ.get("ARTIFACT_ROOT", "artifacts/jobs"))

MANIFEST_FILENAME = "manifest.json"
GLTF_FILENAME = "model.gltf"
STEP_FILENAME = "model.step"


def job_dir(job_id: uuid.UUID | str) -> Path:
    d = ARTIFACT_ROOT / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_stl_filename(contract_name: str) -> str:
    """contract_name (`SEG-C/BODY-rib_100/ROLE-rib`) contains `/`, unsafe as
    a bare filename — replaced with `_`, losslessly reversible in practice
    since no body/role/segment token in this project ever contains `_` at
    the position a `/` would (naming contract fields are alnum+underscore
    only, checked at the call site, never round-tripped back to a
    contract_name from the filename anyway — the manifest is what maps
    filename -> contract_name)."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", contract_name) + ".stl"
