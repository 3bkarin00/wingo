#!/usr/bin/env python3
"""R0 probe (P6 ribs, plan.md §8.7): verify cq.Solid.extrudeLinear on a REAL
per-station rib cross-section — plane ∩ hollow-interior outline, offset
inward for the lightening-hole inner wire (same offset2D route already
probed/used by iml.py/cove_profile.py), thickened symmetrically about the
rib plane. NOT the F1-banned "shell/thicken a curved skin" — this extrudes
a FLAT planar face along its own normal, a categorically different (and
much simpler/more robust) OCC operation; called out explicitly so this
probe isn't mistaken for reopening F1.

Run: .venv/bin/python scripts/r0_probes/probe_ocp_rib_extrude.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import cadquery as cq
import numpy as np
import yaml

from backend.geometry.booleans import filter_shards, fuzzy_common
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts, face_sheet_thickness_mm
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.reference import build_rib_planes
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config


def main() -> int:
    cfg = Config.model_validate(
        yaml.safe_load((ROOT / "tests/configs/edge/high_taper.yaml").read_text())
    )
    print(f"config: high_taper.yaml (no te_surface — clean-span rib test)")

    sections = build_planform_sections(cfg, cfg.airfoils.resample_points)
    oml = build_oml(sections, mirror=cfg.planform.mirror)
    print(f"OML: valid={oml.isValid()}, watertight={is_watertight(oml)}, vol={oml.Volume():.1f}")

    lofts = build_sandwich_lofts(cfg, sections)
    body = build_sandwich_body(oml, lofts, include_hollow_interior=True)
    hollow = body.hollow_interior
    solids, shards = filter_shards(hollow)
    print(f"hollow_interior: {len(solids)} solid(s), {len(shards)} shard(s), vol={sum(s.Volume() for s in solids):.1f}")
    hollow_solid = max(solids, key=lambda s: s.Volume())

    planes = build_rib_planes(cfg)
    print(f"rib planes: {len(planes)}")

    rib_mm = cfg.ribs.construction.plies * 0.2  # provisional stand-in, doesn't need tolerances.py for a throwaway probe
    margin_mm = cfg.ribs.lightening_holes.margin_mm
    print(f"rib_mm={rib_mm}, margin_mm={margin_mm}")

    n_ok, n_fail = 0, 0
    for i, plane in enumerate(planes):
        y = plane.origin.y
        # A big cutting face at this Y station, then ∩ hollow_solid -> the rib outline.
        big = cq.Face.makePlane(length=10000, width=10000, basePnt=plane.origin, dir=plane.zDir)
        cut = fuzzy_common(hollow_solid, big)
        rib_solids, rib_shards = filter_shards(cut, min_volume=1e-6)
        faces = [f for s in rib_solids for f in s.Faces()] if rib_solids else cut.Faces()
        # cut of a solid by an infinite plane face may itself return faces directly
        # depending on OCC's handling - try both raw cut.Faces() too.
        all_faces = list(cut.Faces())
        if not all_faces:
            print(f"  y={y:.1f}: NO FACE from plane-cut (skip — likely outside body span)")
            continue
        outer_face = max(all_faces, key=lambda f: f.Area())
        outer_wire = outer_face.outerWire()

        try:
            inner_wires = []
            if margin_mm > 0:
                offset_result = outer_wire.offset2D(-margin_mm, kind="intersection")
                inner = offset_result[0] if isinstance(offset_result, list) else offset_result
                inner_wires = [inner]
            solid = cq.Solid.extrudeLinear(outer_wire, inner_wires, cq.Vector(0, rib_mm / 2, 0))
            solid2 = cq.Solid.extrudeLinear(outer_wire, inner_wires, cq.Vector(0, -rib_mm / 2, 0))
            rib = solid.fuse(solid2)
            ok = rib.isValid() and is_watertight(rib)
            print(f"  y={y:.1f}: outer_wire edges={len(outer_wire.Edges())}, "
                  f"hole={'yes' if inner_wires else 'no'}, rib valid={rib.isValid()}, "
                  f"watertight={is_watertight(rib)}, vol={rib.Volume():.2f}")
            n_ok += ok
            n_fail += not ok
        except Exception as e:
            print(f"  y={y:.1f}: FAILED — {type(e).__name__}: {e}")
            n_fail += 1

    print(f"\nCONCLUSION: {n_ok} ok, {n_fail} failed out of {len(planes)} rib planes")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
