"""Tessellation API endpoints for the web viewer (P21).

Provides endpoints to build wing geometry and serve tessellated mesh data
as JSON for the three.js viewer. Supports multiple LOD levels for
interactive performance.

Endpoints:
- POST   /api/wing/preview      — build and return tessellated wing mesh
- GET    /api/wing/configs/{id} — get a persisted config for the viewer
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.schema.db import SessionLocal
from backend.schema.db_models import ConfigRow
from backend.schema.models import Config as WingConfig

logger = logging.getLogger(__name__)

# ── Request / response models ───────────────────────────────────────────────


@dataclass
class TessellationMesh:
    """Tessellated mesh data for the three.js viewer."""
    vertices: list[float] = None
    indices: list[int] = None
    face_count: int = 0
    triangle_count: int = 0

    def __post_init__(self):
        if self.vertices is None:
            self.vertices = []
        if self.indices is None:
            self.indices = []


class PreviewRequest(BaseModel):
    """Request for a wing preview mesh."""
    config: dict[str, Any] | None = None
    quality: str = "medium"  # low | medium | high

    model_config = {"extra": "forbid"}

    @property
    def wing_config(self) -> WingConfig | None:
        """Convert dict to WingConfig if provided."""
        if self.config is None:
            return None
        try:
            return WingConfig.model_validate(self.config)
        except Exception:
            raise ValueError("Invalid config")


class TessellationResponse(BaseModel):
    """Response containing tessellated mesh data."""
    success: bool = True
    quality: str = "medium"
    mesh: dict[str, Any] = None  # {vertices: [...], indices: [...], ...}
    metrics: dict[str, Any] = None
    error: str | None = None

    model_config = {"extra": "forbid"}


# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_db():
    """Yield a scoped ORM session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_preview_mesh(
    config: WingConfig,
    quality: str = "medium",
) -> TessellationResponse:
    """Build tessellated mesh for a wing config.

    Returns mesh data suitable for three.js rendering.
    """
    from backend.geometry.multires import build_at_quality
    from backend.geometry.mesh import build_lod_meshes

    try:
        result = build_at_quality(config, quality=quality)
        solid = result.solid

        # Build LOD meshes for the viewer
        lod_meshes = build_lod_meshes(solid)

        # Convert to JSON-serializable format
        mesh_data = {}
        for level, (verts, tris) in lod_meshes.items():
            verts_flat = [float(v.x) for v in verts] + \
                         [float(v.y) for v in verts] + \
                         [float(v.z) for v in verts]
            mesh_data[level] = {
                "vertices": verts_flat,
                "indices": [i for tri in tris for i in tri],
                "triangle_count": len(tris),
                "vertex_count": len(verts),
            }

        return TessellationResponse(
            success=True,
            quality=quality,
            mesh=mesh_data,
            metrics=result.metrics,
        )
    except Exception as exc:
        logger.exception("Failed to build preview mesh")
        return TessellationResponse(
            success=False,
            quality=quality,
            error=str(exc),
        )


# ── Router ──────────────────────────────────────────────────────────────────

tess_router = APIRouter(prefix="/api/wing", tags=["tessellation"])


@tess_router.post("/preview", response_model=TessellationResponse)
async def preview_wing(req: PreviewRequest) -> TessellationResponse:
    """Build and return a tessellated wing mesh for the viewer.

    Accepts a full wing config or a config_id reference.
    Returns tessellated mesh data at the requested quality level.
    """
    if req.config is None:
        raise HTTPException(400, "Config is required")

    try:
        config = WingConfig.model_validate(req.config)
    except Exception:
        raise HTTPException(422, "Invalid config")

    return _build_preview_mesh(config, req.quality)


@tess_router.get("/configs/{config_id}", response_model=dict)
async def get_config_for_viewer(
    config_id: uuid.UUID,
    db: Session = Depends(_get_db),
) -> dict:
    """Get a persisted config for the viewer."""
    row = db.get(ConfigRow, config_id)
    if row is None:
        raise HTTPException(404, "Config not found")
    return {
        "id": str(row.id),
        "schema_version": row.schema_version,
        "data": row.data,
    }


