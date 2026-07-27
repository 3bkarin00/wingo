"""P9 STEP export (plan.md §9 P9, §8 pipeline step 10) — via the OCP XDE
assembly path (plain export drops names, F10). Thin, naming-contract-aware
wrapper around backend.geometry.face_registry's already R0-verified XDE
recipe (docs/r0_findings/p06_ext.md: write.stepcaf.subshapes.name=1 set
AFTER writer init + STEPCAFControl_Writer.Perform).

Whole-BODY names follow docs/conventions.md's naming contract exactly:
`SEG-{C|L|R}/BODY-{name}/ROLE-{skin|rib|spar|...}`. Bond/sub-face names
(when a body carries a face_registry.FaceRegistry match dict — WP1
carriers, WP2b π bonds, WP2c tab/slot bonds) are passed straight through
unchanged, since those already carry their own contract-independent naming
(HINGE<n>_..., RIB<y>_..., SPAR<name>_... — plan.md §8.8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import cadquery as cq

from backend.geometry.face_registry import write_step_with_names

Segment = Literal["C", "L", "R"]


@dataclass
class NamedBody:
    body_name: str
    role: str
    segment: Segment
    shape: cq.Shape
    sub_faces: dict = field(default_factory=dict)  # face_name -> cq.Face (already matched)

    @property
    def contract_name(self) -> str:
        return f"SEG-{self.segment}/BODY-{self.body_name}/ROLE-{self.role}"


def write_assembly_step(bodies: list[NamedBody], path: str) -> None:
    """One multi-body STEP file: every body named per the §5 naming
    contract, every already-matched sub-face named per its own bond-face
    contract (§8.8). Raises if any body's sub_faces dict references a face
    that isn't actually a sub-shape of that body's OWN shape (a caller bug
    — face_registry.match() already guarantees the face came from the
    right shape at match time, so this would mean a body/faces mismatch
    was assembled incorrectly here, not a boolean-ate-it construction bug)."""
    entries = [(b.contract_name, b.shape, b.sub_faces) for b in bodies]
    write_step_with_names(entries, path)
