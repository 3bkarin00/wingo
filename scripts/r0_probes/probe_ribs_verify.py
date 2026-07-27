#!/usr/bin/env python3
"""Verification (not a throwaway diagnostic — exercises the real
backend/geometry/ribs.py module): build ribs on a config and report the
outcome per plane (clean/fallback/skipped), verifying every rib is a
single valid watertight solid.

Run: .venv/bin/python scripts/r0_probes/probe_ribs_verify.py [config.yaml]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from backend.geometry.booleans import filter_shards
from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.reference import build_rib_planes
from backend.geometry.ribs import build_ribs
from backend.geometry.sections import build_planform_sections
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

    planes = build_rib_planes(cfg)
    rib_set = build_ribs(cfg, hollow_solid, planes)

    print(f"\nribs built: {len(rib_set.ribs)}/{len(planes)}")
    print(f"skipped (no section): {rib_set.skipped_no_section}")
    print(f"fallback to solid (hole didn't fit): {rib_set.fallback_solid}")

    n_valid = 0
    for rib in rib_set.ribs:
        rsolids, rshards = filter_shards(rib.solid, min_volume=1e-6)
        ok = len(rsolids) == 1 and rib.solid.isValid() and all(is_watertight(s) for s in rsolids)
        n_valid += ok
        print(f"  y={rib.y_mm:.1f}: has_hole={rib.has_hole}, area={rib.area_mm2:.1f}mm2, "
              f"n_solids={len(rsolids)}, shards={len(rshards)}, valid_and_watertight={ok}")

    print(f"\nCONCLUSION: {n_valid}/{len(rib_set.ribs)} ribs valid+watertight "
          f"({len(rib_set.skipped_no_section)} skipped, {len(rib_set.fallback_solid)} fell back to solid)")
    return 0 if n_valid == len(rib_set.ribs) else 1


if __name__ == "__main__":
    sys.exit(main())
