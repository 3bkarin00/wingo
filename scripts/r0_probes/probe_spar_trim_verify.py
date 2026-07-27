#!/usr/bin/env python3
"""Verification (exercises the real backend/geometry/spar_trim.py module):
build trimmed spar webs on a config, verify each is a single valid
watertight solid with sane volume.

Run: .venv/bin/python scripts/r0_probes/probe_spar_trim_verify.py [config.yaml]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from backend.geometry.booleans import filter_shards
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.geometry.spar_trim import build_trimmed_spars
from backend.schema.models import Config


def main() -> int:
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "tests/configs/edge/high_taper.yaml"
    cfg = Config.model_validate(yaml.safe_load((ROOT / cfg_path).read_text()))
    print(f"config: {cfg_path}")

    sections = build_planform_sections(cfg, cfg.airfoils.resample_points)
    oml = build_oml(sections, mirror=cfg.planform.mirror)
    print(f"OML: valid={oml.isValid()}, watertight={is_watertight(oml)}")

    lofts = build_sandwich_lofts(cfg, sections)
    body = build_sandwich_body(oml, lofts, include_hollow_interior=True)
    solids, shards = filter_shards(body.hollow_interior)
    print(f"hollow_interior: {len(solids)} solid(s), {len(shards)} shard(s)")
    hollow_solid = max(solids, key=lambda s: s.Volume())

    trimmed = build_trimmed_spars(cfg, sections, hollow_solid)
    print(f"\nspars: {len(trimmed)}")

    n_ok = 0
    for spar in trimmed:
        ssolids, sshards = filter_shards(spar.solid, min_volume=1e-6)
        ok = len(ssolids) >= 1 and spar.solid.isValid() and all(is_watertight(s) for s in ssolids)
        n_ok += ok
        vol = sum(s.Volume() for s in ssolids)
        print(f"  {spar.name}: web_mm={spar.web_thickness_mm:.2f}, timings={spar.timings_s}, "
              f"n_solids={len(ssolids)}, shards={len(sshards)}, valid={spar.solid.isValid()}, "
              f"watertight={[is_watertight(s) for s in ssolids]}, vol={vol:.1f}, ok={ok}")

    print(f"\nCONCLUSION: {n_ok}/{len(trimmed)} spars valid+watertight")
    return 0 if n_ok == len(trimmed) else 1


if __name__ == "__main__":
    sys.exit(main())
