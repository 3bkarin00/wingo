"""Resolve a station's airfoil NAME to canonical unit-chord points, reusing
the P1 subsystem. NACA codes are generated; `uiuc:<name>` is ingested from the
vendored snapshot; `db:<name>` is looked up from the uploaded-airfoils DB.
All results share the same odd resample count so sections can be blended and
lofted with aligned point correspondence (r0_findings/p02.md).

Caching: the `resolve_airfoil` function is decorated with the geometry cache
so that repeated lookups (same name + resolution) return cached ndarray objects
without re-parsing or re-generating.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.airfoils.naca import generate_naca
from backend.airfoils.uiuc_ingest import ingest_dat_file
from backend.airfoils.types import Airfoil
from backend.geometry.cache import cache
from backend.schema.db_models import AirfoilRow

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SNAPSHOT = _REPO_ROOT / "data" / "uiuc_snapshot"


def _resolve_from_db(name: str, resample_points: int, te_thickness_frac: float) -> np.ndarray:
    """Look up an uploaded airfoil from the DB and resample it."""
    from backend.airfoils.resample import cosine_resample, close_blunt_te
    from backend.schema.db import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(AirfoilRow).filter(AirfoilRow.name == name).first()
        if row is None or row.normalized_points is None:
            return None
        pts = np.array(row.normalized_points["points"])
        if len(pts) < 3:
            return None
        pts = cosine_resample(pts, resample_points)
        return close_blunt_te(pts, te_thickness_frac)
    finally:
        db.close()


@cache.memoize(category="airfoil", maxsize=128)
def resolve_airfoil(
    name: str,
    resample_points: int,
    te_thickness_frac: float,
) -> np.ndarray:
    """Return canonical (N, 2) unit-chord points for `name`.

    Resolution order:
    1. `db:<name>` → look up uploaded airfoil from DB
    2. `uiuc:<file>` → ingest data/uiuc_snapshot/<file>.dat
    3. NACA 4/5-digit code → generated analytically

    Raises ValueError if the airfoil can't be resolved.

    Cached by (name, resample_points, te_thickness_frac).
    """
    key = name.strip().lower()

    # 1. DB (uploaded airfoils)
    if key.startswith("db:"):
        stem = key.split(":", 1)[1]
        pts = _resolve_from_db(stem, resample_points, te_thickness_frac)
        if pts is None:
            raise ValueError(f"Uploaded airfoil '{stem}' not found in DB")
        return pts

    # 2. UIUC snapshot
    if key.startswith("uiuc:"):
        stem = key.split(":", 1)[1]
        result = ingest_dat_file(_SNAPSHOT / f"{stem}.dat", resample_points, te_thickness_frac)
        if not isinstance(result, Airfoil):
            raise ValueError(f"UIUC airfoil '{stem}' quarantined: {result.reason}")
        return result.points

    # 3. NACA generator
    from backend.airfoils.resample import close_blunt_te

    pts = generate_naca(key, resample_points).points
    return close_blunt_te(pts, te_thickness_frac)
