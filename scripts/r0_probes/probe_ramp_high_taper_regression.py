#!/usr/bin/env python3
"""Regression probe (P6 ramped drop-offs, docs/r0_findings/p06.md's
"ramp regression on high_taper.yaml" addendum): replicates
build_sandwich_body's exact boolean chain on high_taper.yaml (10:1 taper,
mirror:true, single-ply thin layers — an explicit self-intersection
stress-test config), with validity/watertight/solid-count checks after
EVERY step. Originally written to pinpoint why
face_inner_upper = fuzzy_cut(face_inner_shell, parting_solid) failed while
every other split succeeded (root cause: parting_solid vs. the other three
lofts had mismatched per-station Y-sampling — fixed in iml.py). Re-run this
after any future change to iml.py's per-station construction to confirm
the whole chain still stays valid on this deliberately extreme config."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import yaml

from backend.geometry.booleans import filter_shards, fuzzy_common, fuzzy_cut
from backend.geometry.iml import build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config


def report(name, shape):
    try:
        solids = shape.Solids()
        print(f"  {name}: valid={shape.isValid()}, n_solids={len(solids)}, "
              f"vols={[round(s.Volume(),4) for s in solids]}, "
              f"watertight_each={[is_watertight(s) for s in solids]}")
    except Exception as e:
        print(f"  {name}: REPORT FAILED — {type(e).__name__}: {e}")


def main() -> int:
    cfg = Config.model_validate(
        yaml.safe_load((ROOT / "tests/configs/edge/high_taper.yaml").read_text())
    )
    sections = build_planform_sections(cfg, cfg.airfoils.resample_points)
    body = build_oml(sections, mirror=cfg.planform.mirror)
    print(f"body(OML): valid={body.isValid()}, watertight={is_watertight(body)}, vol={body.Volume():.1f}")

    lofts = build_sandwich_lofts(cfg, sections)
    report("face_iml_solid", lofts.face_iml_solid)
    report("core_iml_solid", lofts.core_iml_solid)
    report("hollow_iml_solid", lofts.hollow_iml_solid)
    report("parting_solid", lofts.parting_solid)

    face_outer_shell = fuzzy_cut(body, lofts.face_iml_solid)
    report("face_outer_shell", face_outer_shell)

    core_band = fuzzy_cut(lofts.face_iml_solid, lofts.core_iml_solid)
    report("core_band", core_band)
    core_shell = fuzzy_common(core_band, body)
    report("core_shell", core_shell)

    face_inner_band = fuzzy_cut(lofts.core_iml_solid, lofts.hollow_iml_solid)
    report("face_inner_band", face_inner_band)
    face_inner_shell = fuzzy_common(face_inner_band, body)
    report("face_inner_shell", face_inner_shell)

    print("\n--- splits ---")
    fo_lower = fuzzy_common(face_outer_shell, lofts.parting_solid)
    report("face_outer_lower", fo_lower)
    fo_upper = fuzzy_cut(face_outer_shell, lofts.parting_solid)
    report("face_outer_upper", fo_upper)

    c_lower = fuzzy_common(core_shell, lofts.parting_solid)
    report("core_lower", c_lower)
    c_upper = fuzzy_cut(core_shell, lofts.parting_solid)
    report("core_upper", c_upper)

    fi_lower = fuzzy_common(face_inner_shell, lofts.parting_solid)
    report("face_inner_lower", fi_lower)
    try:
        fi_upper = fuzzy_cut(face_inner_shell, lofts.parting_solid)
        report("face_inner_upper", fi_upper)
    except Exception as e:
        print(f"  face_inner_upper: FAILED — {type(e).__name__}: {e}")
        # Try a larger fuzzy value as a targeted experiment.
        for fz in (0.01, 0.05, 0.1, 0.5):
            try:
                fi_upper2 = fuzzy_cut(face_inner_shell, lofts.parting_solid, fuzzy=fz)
                report(f"face_inner_upper (fuzzy={fz})", fi_upper2)
            except Exception as e2:
                print(f"  face_inner_upper (fuzzy={fz}): FAILED — {type(e2).__name__}: {e2}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
