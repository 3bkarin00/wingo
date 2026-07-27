#!/usr/bin/env python3
"""R0 probe (P6 midsurfaces, plan.md §8.7): verify BRepOffsetAPI_ThruSections
with isSolid=False produces a genuine open SHELL (no end caps) from the same
per-station polygon wires this project already lofts into solids everywhere
else. cadquery's own cq.Solid.makeLoft hardcodes isSolid=True (its own
source comment: "the True flag requests building a solid instead of a
shell") — this is the SAME underlying OCC call, just the other documented
mode, not a new/uncharted API.

Run: .venv/bin/python scripts/r0_probes/probe_ocp_shell_loft.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import cadquery as cq
import yaml
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

from backend.geometry.loft import build_section_wire
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config


def shell_loft(wires: list[cq.Wire], ruled: bool = True) -> cq.Shape:
    builder = BRepOffsetAPI_ThruSections(False, ruled)  # isSolid=False -> shell, no end caps
    for w in wires:
        builder.AddWire(w.wrapped)
    builder.Build()
    return cq.Shape.cast(builder.Shape())


def main() -> int:
    cfg = Config.model_validate(
        yaml.safe_load((ROOT / "tests/configs/devices/te_half.yaml").read_text())
    )
    sections = build_planform_sections(cfg, cfg.airfoils.resample_points)
    wires = [build_section_wire(sec.points) for sec in sections]
    print(f"{len(wires)} station wires")

    shell = shell_loft(wires)
    print(f"shell: valid={shell.isValid()}, type={type(shell).__name__}")
    print(f"  n_faces={len(shell.Faces())}, n_solids={len(shell.Solids())}")

    # A closed loop of station wires (TE->upper->LE->lower->TE) lofted as a
    # shell should have surface area roughly matching the equivalent solid's
    # LATERAL area (no end caps) -- compare against the solid loft's own
    # face count/area as a sanity check, not just isValid().
    solid = cq.Solid.makeLoft(wires, ruled=True)
    print(f"solid (for comparison): valid={solid.isValid()}, n_faces={len(solid.Faces())}, "
          f"vol={solid.Volume():.1f}")
    print(f"shell area={sum(f.Area() for f in shell.Faces()):.1f}, "
          f"solid lateral-face area (excluding 2 end caps)="
          f"{sum(f.Area() for f in solid.Faces()) - sum(sorted((f.Area() for f in solid.Faces()))[-2:]):.1f}")

    return 0 if shell.isValid() and len(shell.Solids()) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
