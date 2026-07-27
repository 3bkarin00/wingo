"""P9 glTF/STL export (plan.md §9 P9, §8 pipeline step 10) — per-body
tessellation via `cq.Assembly`. R0-verified (docs/r0_findings/p09.md):
`cq.Assembly(...).export(path, exportType=...)` (NOT the deprecated
`.save()`, which the installed cadquery already warns will be removed);
glTF node names are the assembly child names given to `.add(...)`, so the
SAME §5 naming-contract string used for STEP doubles as the glTF node
name — one name per body, one source of truth.

STL has no per-body naming concept (a single mesh file per body, plan.md's
"per-body tessellation ... + STL"), so `write_stl` takes one shape and
writes one file per call — callers loop over bodies themselves, naming the
FILE (not an in-mesh attribute) per the same contract string.

Tolerance: TESSELLATION_TOLERANCE_MM (0.05mm) for both formats — the
project's one shared mesh-fidelity tolerance, not a separate "export
tolerance" (see backend/tolerances.py's own derivation comment; distinct
from scripts/export_viewer_data.py's TESSELLATE_TOLERANCE_MM=0.5, which
that script's own docstring already flags as "visual only, not a gate
tolerance" for the throwaway dev viewer, never this module).
"""
from __future__ import annotations

import cadquery as cq

from backend import tolerances


def write_gltf(bodies: list, path: str) -> None:
    """`bodies` = [(contract_name, cq.Shape), ...] (exporters.step_export.
    NamedBody's own (contract_name, shape) pair, or any equivalent list —
    kept as plain tuples here rather than importing NamedBody, since glTF
    export doesn't need sub_faces at all)."""
    assy = cq.Assembly()
    for name, shape in bodies:
        assy.add(cq.Workplane(obj=shape), name=name)
    assy.export(
        path, exportType="GLTF",
        tolerance=tolerances.TESSELLATION_TOLERANCE_MM,
        angularTolerance=tolerances.TESSELLATION_TOLERANCE_MM,
    )


def write_stl(shape: cq.Shape, path: str) -> None:
    cq.exporters.export(
        cq.Workplane(obj=shape), path, exportType="STL",
        tolerance=tolerances.TESSELLATION_TOLERANCE_MM,
        angularTolerance=tolerances.TESSELLATION_TOLERANCE_MM,
    )
