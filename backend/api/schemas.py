"""P10 API request/response models — thin Pydantic wrappers around the
`configs`/`jobs` tables (§7). Kept separate from backend.schema.models
(the geometry input schema itself, validated identically here via
Config.model_validate before anything is stored) since these describe the
HTTP wire shape, not the CAD config shape.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel

# D17 (materials/config-library versioning) hasn't landed — one fixed
# version string for every config this API stores, same posture as
# backend/tolerances.py's PLY_THICKNESS_MM_PROVISIONAL ("standing in for
# the D17 materials DB until it's seeded").
SCHEMA_VERSION = "0.4"


class ConfigCreateRequest(BaseModel):
    data: dict


class ConfigResponse(BaseModel):
    id: uuid.UUID
    data: dict


class SampleConfigInfo(BaseModel):
    name: str
    source: str  # relative path, for humans debugging which fixture this is


class JobCreateRequest(BaseModel):
    config_id: uuid.UUID | None = None
    config: dict | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    checkpoint: dict | None = None
    artifact_manifest: dict | None = None


class VertexSampleRequest(BaseModel):
    body_name: str  # contract_name (SEG-.../BODY-.../ROLE-...)
    point_local: tuple[float, float, float]
    angle_deg: float


class VertexSampleResponse(BaseModel):
    point_world: tuple[float, float, float]
    moved: bool  # True if body_name is CS-side (rotated about the hinge axis)
