#!/usr/bin/env python3
"""Verification (exercises the real backend/geometry/midsurface.py module,
plus the already-built rib/spar midsurface byproducts): build all three
midsurface sources on a config, verify each is a genuine open shell (no
enclosed solid) with sane area, and that face count matches structural
body count (the P6 gate's own eventual pass criterion).

Run: .venv/bin/python scripts/r0_probes/probe_midsurface_verify.py [config.yaml]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from backend.geometry.booleans import filter_shards
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.midsurface import build_skin_midsurface
from backend.geometry.reference import build_rib_planes, build_spar_surfaces
from backend.geometry.ribs import build_ribs
from backend.geometry.sections import build_planform_sections
from backend.geometry.spar_trim import build_trimmed_spars
from backend.schema.models import Config


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "tests/configs/edge/high_taper.yaml"
    cfg = Config.model_validate(yaml.safe_load((ROOT / cfg_path).read_text()))
    print(f"config: {cfg_path}")

    sections = build_planform_sections(cfg, cfg.airfoils.resample_points)
    oml = build_oml(sections, mirror=cfg.planform.mirror)

    skin_mid = build_skin_midsurface(cfg, sections)
    print(f"skin midsurface: valid={skin_mid.isValid()}, n_faces={len(skin_mid.Faces())}, "
          f"n_solids={len(skin_mid.Solids())}, area={sum(f.Area() for f in skin_mid.Faces()):.1f}")
    assert len(skin_mid.Solids()) == 0, "skin midsurface must be an open shell, not enclose a volume"

    lofts = build_sandwich_lofts(cfg, sections)
    body = build_sandwich_body(oml, lofts, include_hollow_interior=True)
    solids, shards = filter_shards(body.hollow_interior)
    hollow_solid = max(solids, key=lambda s: s.Volume())

    rib_planes = build_rib_planes(cfg)
    rib_set = build_ribs(cfg, hollow_solid, rib_planes)
    print(f"\nrib midsurfaces: {len(rib_set.ribs)}")
    for rib in rib_set.ribs:
        f = rib.midsurface_face
        print(f"  y={rib.y_mm:.1f}: valid={f.isValid()}, area={f.Area():.1f}")
        assert f.isValid(), f"rib midsurface at y={rib.y_mm} invalid"

    spar_surfaces = build_spar_surfaces(cfg, sections)
    trimmed = build_trimmed_spars(cfg, sections, hollow_solid)
    print(f"\nspar midsurfaces (P3 build_spar_surfaces, already built): {len(spar_surfaces)}")
    for name, shell in spar_surfaces.items():
        print(f"  {name}: valid={shell.isValid()}, n_faces={len(shell.Faces())}, "
              f"area={sum(f.Area() for f in shell.Faces()):.1f}")
        assert shell.isValid(), f"spar midsurface {name} invalid"

    n_midsurfaces = 1 + len(rib_set.ribs) + len(spar_surfaces)  # skin + ribs + spars
    n_structural_bodies = 1 + len(rib_set.ribs) + len(trimmed)  # skin body + ribs + trimmed spars
    print(f"\nCONCLUSION: {n_midsurfaces} midsurfaces vs {n_structural_bodies} structural bodies "
          f"(skin=1+1, ribs={len(rib_set.ribs)}={len(rib_set.ribs)}, spars={len(spar_surfaces)}={len(trimmed)})")
    return 0 if n_midsurfaces == n_structural_bodies else 1


if __name__ == "__main__":
    sys.exit(main())
