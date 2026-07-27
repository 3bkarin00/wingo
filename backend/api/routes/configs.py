"""Config CRUD (§7 `configs` table) + a read-only sample-config catalog.

The sample catalog serves tests/golden/*.yaml and tests/configs/devices/
*.yaml over the API — D17's real config library (materials DB-backed,
user-authored configs) hasn't landed, so this is the pragmatic stand-in
that lets the P10 frontend/gate submit a real, already-known-valid config
without inventing a second copy of these fixtures under backend/. Read-
only, repo-relative — never treat this as the production config store
(that's the `configs` table itself, POST /configs).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from backend.api.schemas import SCHEMA_VERSION, ConfigCreateRequest, ConfigResponse, SampleConfigInfo
from backend.schema.db import session_scope
from backend.schema.db_models import ConfigRow
from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIRS = [
    REPO_ROOT / "tests" / "golden",
    REPO_ROOT / "tests" / "configs" / "devices",
]

router = APIRouter(prefix="/configs", tags=["configs"])


def _row_to_response(row: ConfigRow) -> ConfigResponse:
    return ConfigResponse(id=row.id, data=row.data)


@router.post("", response_model=ConfigResponse)
def create_config(req: ConfigCreateRequest) -> ConfigResponse:
    try:
        validated = Config.model_validate(req.data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    with session_scope() as session:
        row = ConfigRow(schema_version=SCHEMA_VERSION, data=validated.model_dump(mode="json"))
        session.add(row)
        session.flush()
        return _row_to_response(row)


@router.get("/samples", response_model=list[SampleConfigInfo])
def list_samples() -> list[SampleConfigInfo]:
    out = []
    for d in SAMPLE_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.yaml")):
            out.append(SampleConfigInfo(name=f.stem, source=str(f.relative_to(REPO_ROOT))))
    return out


@router.get("/samples/{name}")
def get_sample(name: str) -> dict:
    for d in SAMPLE_DIRS:
        f = d / f"{name}.yaml"
        if f.exists():
            return yaml.safe_load(f.read_text())
    raise HTTPException(status_code=404, detail=f"sample config {name!r} not found")


@router.get("/{config_id}", response_model=ConfigResponse)
def get_config(config_id: uuid.UUID) -> ConfigResponse:
    with session_scope() as session:
        row = session.get(ConfigRow, config_id)
        if row is None:
            raise HTTPException(status_code=404, detail="config not found")
        return _row_to_response(row)
