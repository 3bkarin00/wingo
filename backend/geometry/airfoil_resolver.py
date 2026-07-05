"""Resolve a station's airfoil NAME to canonical unit-chord points, reusing
the P1 subsystem. NACA codes are generated; `uiuc:<name>` is ingested from the
vendored snapshot. All results share the same odd resample count so sections
can be blended and lofted with aligned point correspondence (r0_findings/p02.md).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.airfoils.naca import generate_naca
from backend.airfoils.uiuc_ingest import ingest_dat_file
from backend.airfoils.types import Airfoil

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SNAPSHOT = _REPO_ROOT / "data" / "uiuc_snapshot"


def resolve_airfoil(
    name: str,
    resample_points: int,
    te_thickness_frac: float,
) -> np.ndarray:
    """Return canonical (N, 2) unit-chord points for `name`.

    `uiuc:<file>` → ingest data/uiuc_snapshot/<file>.dat; otherwise treat as a
    NACA 4/5-digit code. Raises ValueError if the airfoil can't be resolved
    (a quarantined UIUC file is an error here — placement needs real geometry).
    """
    key = name.strip().lower()
    if key.startswith("uiuc:"):
        stem = key.split(":", 1)[1]
        result = ingest_dat_file(_SNAPSHOT / f"{stem}.dat", resample_points, te_thickness_frac)
        if not isinstance(result, Airfoil):
            raise ValueError(f"UIUC airfoil '{stem}' quarantined: {result.reason}")
        return result.points
    # NACA generator produces sharp-ish TE; enforce the same blunt-TE minimum.
    from backend.airfoils.resample import close_blunt_te

    pts = generate_naca(key, resample_points).points
    return close_blunt_te(pts, te_thickness_frac)
