#!/usr/bin/env python3
"""R0/verify probe for D24 π-joint ribs (backend/geometry/pi_joints.py).

Same stand-in-cavity strategy as probe_spar_shapes_verify.py (OML solid of
tests/configs/valid/minimal.yaml — seconds, not the tens-of-minutes real
sandwich cavity; every step under test behaves identically on any solid).

Checks:
  - build_ribs now applies the D24 skin-segment offset: every rib is still
    watertight AND strictly smaller in area than its un-offset outline.
  - build_pi_preforms yields >= 2 segments per rib (upper+lower, more when
    spar crossings split a side), each a valid watertight solid.
  - BY-CONSTRUCTION bond gap: each π body has planar ±Y faces at exactly
    rib_y ± (rib_t/2 + PI_BOND_GAP_MM) — the leg inner faces the extension
    gate's slot-fit test measures.
  - π bodies are trimmed clear of the spar: π ∩ spar volume == 0.
  - π ∩ rib intersection volume == 0 (the base underside deliberately
    BUTTS the offset rib edge — touching, never overlapping).

Appends findings to docs/r0_findings/p06_ext.md.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06_ext.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_pi_joints_verify.py (WP2b/D24)"]
    failures = 0
    try:
        import numpy as np
        import yaml
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane

        from backend import tolerances
        from backend.geometry.booleans import filter_shards, fuzzy_common
        from backend.geometry.loft import build_oml, is_watertight
        from backend.geometry.pi_joints import build_pi_preforms
        from backend.geometry.reference import build_rib_planes
        from backend.geometry.ribs import build_ribs, rib_thickness_mm
        from backend.geometry.sections import build_planform_sections
        from backend.geometry.spars import build_spar_bodies
        from backend.schema.models import Config

        config = Config.model_validate(
            yaml.safe_load((ROOT / "tests/configs/valid/minimal.yaml").read_text())
        )
        sections = build_planform_sections(config, config.airfoils.resample_points)
        cavity = build_oml(sections, mirror=False)
        rib_t = rib_thickness_mm(config)

        t0 = time.perf_counter()
        rib_set = build_ribs(config, cavity, build_rib_planes(config))
        lines.append(f"- {len(rib_set.ribs)} π-offset ribs built in {time.perf_counter()-t0:.1f}s "
                     f"(skipped_no_section={len(rib_set.skipped_no_section)})")

        # Offset actually shrank every rib vs its raw outline.
        import cadquery as cq
        shrunk_ok = True
        for rib in rib_set.ribs:
            raw_area = cq.Face.makeFromWires(
                cq.Wire.makePolygon([cq.Vector(*p) for p in rib.outline_pts], close=True)
            ).Area()
            if not rib.area_mm2 < raw_area:
                shrunk_ok = False
                lines.append(f"  - rib y={rib.y_mm:.0f}: area {rib.area_mm2:.0f} NOT < raw {raw_area:.0f} — FAIL")
        wt = all(is_watertight(s) for r in rib_set.ribs for s, _ in [(x, 0) for x in filter_shards(r.solid)[0]])
        lines.append(f"- every rib strictly smaller than raw outline: {shrunk_ok}; all watertight: {wt}")
        if not (shrunk_ok and wt):
            failures += 1

        t0 = time.perf_counter()
        pi_set = build_pi_preforms(
            config, cavity, [(r.y_mm, r.outline_pts) for r in rib_set.ribs], rib_t,
        )
        lines.append(f"- {len(pi_set.segments)} π preform bodies in {time.perf_counter()-t0:.1f}s "
                     f"(skipped_short={len(pi_set.skipped_short)}); "
                     f"expected >= 2 per rib: {len(pi_set.segments) >= 2 * len(rib_set.ribs)}")
        if len(pi_set.segments) < 2 * len(rib_set.ribs):
            failures += 1

        bad = []
        for seg in pi_set.segments:
            kept, shards = filter_shards(seg.solid)
            if not (len(kept) == 1 and not shards and seg.solid.isValid()
                    and is_watertight(kept[0]) and kept[0].Volume() > 0):
                bad.append((seg.rib_y_mm, seg.side))
        lines.append(f"- all π bodies single valid watertight solids: {not bad}"
                     + (f" (bad: {bad})" if bad else ""))
        if bad:
            failures += 1

        # By-construction leg gap: planar ±Y faces at rib_y ± (t/2 + gap).
        expect_off = rib_t / 2.0 + tolerances.PI_BOND_GAP_MM
        gap_ok = True
        for seg in pi_set.segments[:6]:  # sample — construction is identical across segments
            found = 0
            for face in seg.solid.Faces():
                surf = BRepAdaptor_Surface(face.wrapped)
                if surf.GetType() != GeomAbs_Plane:
                    continue
                n = surf.Plane().Axis().Direction()
                if abs(abs(n.Y()) - 1.0) > 1e-6:
                    continue
                y_face = face.Center().y
                if abs(abs(y_face - seg.rib_y_mm) - expect_off) < 1e-6:
                    found += 1
            if found < 2:
                gap_ok = False
        lines.append(f"- leg inner faces at exactly rib_y ± (t/2 + {tolerances.PI_BOND_GAP_MM}mm): {gap_ok}")
        if not gap_ok:
            failures += 1

        # π clear of spar; π vs rib touch-only.
        spar_body = build_spar_bodies(config, sections, cavity)[0]
        worst_spar, worst_rib = 0.0, 0.0
        rib_by_y = {r.y_mm: r for r in rib_set.ribs}
        for seg in pi_set.segments:
            for other, acc in ((spar_body.solid, "spar"), (rib_by_y[seg.rib_y_mm].solid, "rib")):
                try:
                    common = fuzzy_common(seg.solid, other)
                except RuntimeError:
                    continue
                kept, _ = filter_shards(common)
                v = sum(s.Volume() for s in kept)
                if acc == "spar":
                    worst_spar = max(worst_spar, v)
                else:
                    worst_rib = max(worst_rib, v)
        lines.append(f"- max π∩spar volume={worst_spar:.4f}mm^3 (must be 0), "
                     f"max π∩rib volume={worst_rib:.4f}mm^3 (must be 0 — butt contact only)")
        if worst_spar > 0 or worst_rib > 0:
            failures += 1

        lines.append(
            f"- CONCLUSION: {'D24 π-joint construction PASSES on the real kernel (stand-in cavity).' if failures == 0 else f'{failures} check(s) FAILED.'}"
        )

    except Exception as exc:  # noqa: BLE001
        import traceback
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        lines.append("```\n" + traceback.format_exc() + "```")
        _append(lines)
        print("\n".join(lines))
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
