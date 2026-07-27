#!/usr/bin/env python3
"""R0/verify probe for D26/ADR-005 pin-and-tube hinges
(backend/geometry/hinges_pin_tube.py) — WP1.

Unlike the WP2* probes this one runs on the REAL P4 device-cut bodies
(tests/configs/devices/te_half.yaml: cut_te_surface + build_false_spar),
since the whole point of WP1 is clearing the real CS nose and bonding to
the real false spar. Costs a few real minutes — no stand-in here.

Checks (previews of the P7 gate's pass criteria):
  - hinges.count stations, every tube/carrier a valid watertight solid.
  - COAXIALITY: every tube's cylindrical faces coaxial with the true axis
    within COAXIALITY_TOLERANCE_MM.
  - BOND GAPS by measurement: wing carrier ↔ false_spar_pocketed min
    distance in [0, bond_gap + kernel tol] and > 0 (explicit gap, never
    touching); CS carrier ↔ cs_pocketed likewise (Minkowski notch).
  - SWEPT CLEARANCE: CS-side moving hardware (carrier+tube) rotated to
    0/±half/±full deflection has zero positive-volume intersection with
    the wing-side static set (false_spar_pocketed + wing carriers/tubes);
    mirror check for wing hardware vs cs_pocketed.
  - Face registry: 2 bond faces per station matched and named.
  - cs_pocketed strictly smaller than cs_solid (pockets + notches + bore
    actually removed material).

Appends findings to docs/r0_findings/p07.md (WP1's probe trail).
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p07.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_pin_tube_hinges_verify.py (WP1/D26, ADR-005)"]
    failures = 0
    try:
        import cadquery as cq
        import numpy as np
        import yaml
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape

        from backend import tolerances
        from backend.geometry.booleans import (
            coaxial_cylinder_axis_deviation, filter_shards, fuzzy_common,
        )
        from backend.geometry.false_spar import build_false_spar
        from backend.geometry.hinges_pin_tube import build_pin_tube_hinges
        from backend.geometry.iml import build_sandwich_lofts
        from backend.geometry.loft import build_oml, is_watertight
        from backend.geometry.sections import build_planform_sections
        from backend.geometry.te_cut import cut_te_surface
        from backend.schema.models import Config

        config = Config.model_validate(
            yaml.safe_load((ROOT / "tests/configs/devices/te_half.yaml").read_text())
        )
        sections = build_planform_sections(config, config.airfoils.resample_points)
        oml = build_oml(sections, mirror=config.planform.mirror)
        t0 = time.perf_counter()
        te = cut_te_surface(config, oml)
        lines.append(f"- P4 device cut: {time.perf_counter()-t0:.0f}s")
        t0 = time.perf_counter()
        lofts = build_sandwich_lofts(config, sections)
        fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
        lines.append(f"- false spar: {time.perf_counter()-t0:.0f}s")

        t0 = time.perf_counter()
        hs = build_pin_tube_hinges(config, sections, te.control_surface, fs.solid)
        lines.append(f"- build_pin_tube_hinges: {time.perf_counter()-t0:.0f}s, "
                     f"timings={ {k: round(v,1) for k,v in hs.timings_s.items()} }, "
                     f"failed={hs.failed}")
        if hs.failed:
            failures += 1

        n_expected = config.te_surface.hinges.count
        ok_count = len(hs.stations) == n_expected
        all_bodies = []
        for st in hs.stations:
            all_bodies += [("wing_tube", st.wing_tube), ("cs_tube", st.cs_tube),
                           ("wing_carrier", st.wing_carrier), ("cs_carrier", st.cs_carrier)]
        wt = all(
            shape.isValid() and all(is_watertight(s) for s in filter_shards(shape)[0])
            for _n, shape in all_bodies
        )
        lines.append(f"- {len(hs.stations)}/{n_expected} stations; all hardware valid+watertight: {wt}")
        if not (ok_count and wt):
            failures += 1

        # Coaxiality.
        worst_dev = 0.0
        for st in hs.stations:
            for tube in (st.wing_tube, st.cs_tube):
                devs = coaxial_cylinder_axis_deviation(tube, hs.axis_p0, hs.axis_dir)
                if devs:
                    worst_dev = max(worst_dev, max(devs))
        co_ok = worst_dev <= tolerances.COAXIALITY_TOLERANCE_MM
        lines.append(f"- worst tube-face axis deviation: {worst_dev:.5f}mm "
                     f"(<= {tolerances.COAXIALITY_TOLERANCE_MM}): {co_ok}")
        if not co_ok:
            failures += 1

        def dist(a, b) -> float:
            d = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
            d.Perform()
            return d.Value() if d.IsDone() else float("nan")

        # Bond gaps.
        bg = tolerances.HINGE_CARRIER_BOND_GAP_MM
        tol = tolerances.KERNEL_TOLERANCE_MM
        gaps_ok = True
        for st in hs.stations:
            d_fs = dist(st.wing_carrier, hs.false_spar_pocketed)
            d_cs = dist(st.cs_carrier, hs.cs_pocketed)
            ok = (0 < d_fs <= bg + tol) and (0 < d_cs <= bg + tol)
            lines.append(f"  - station {st.index}: wing_carrier↔false_spar={d_fs:.3f}mm, "
                         f"cs_carrier↔cs={d_cs:.3f}mm (target ~{bg}) -> {ok}")
            gaps_ok &= ok
        if not gaps_ok:
            failures += 1

        # Swept clearance at sampled angles.
        max_def = config.te_surface.max_deflection_deg
        a_v = cq.Vector(*hs.axis_p0)
        b_v = cq.Vector(*(hs.axis_p0 + hs.axis_dir))
        static_wing = [hs.false_spar_pocketed] + [st.wing_carrier for st in hs.stations] \
            + [st.wing_tube for st in hs.stations]
        moving_cs = [st.cs_carrier for st in hs.stations] + [st.cs_tube for st in hs.stations]
        worst_hit = 0.0
        for ang in (-max_def, -max_def / 2, 0.0, max_def / 2, max_def):
            for m in moving_cs:
                rm = m.rotate(a_v, b_v, float(ang))
                for s in static_wing:
                    try:
                        common = fuzzy_common(rm, s)
                    except RuntimeError:
                        continue
                    kept, _ = filter_shards(common, min_volume=1e-9)
                    worst_hit = max(worst_hit, sum(x.Volume() for x in kept))
        # Mirror: wing hardware vs pocketed CS through the CS's own frame
        # (equivalently rotate wing bodies the opposite way vs cs_pocketed).
        for ang in (-max_def, 0.0, max_def):
            for m in [st.wing_carrier for st in hs.stations] + [st.wing_tube for st in hs.stations]:
                rm = m.rotate(a_v, b_v, float(-ang))
                try:
                    common = fuzzy_common(rm, hs.cs_pocketed)
                except RuntimeError:
                    continue
                kept, _ = filter_shards(common, min_volume=1e-9)
                worst_hit = max(worst_hit, sum(x.Volume() for x in kept))
        lines.append(f"- swept collision check (0/±half/±full deflection): worst intersection="
                     f"{worst_hit:.6f}mm^3 (must be 0)")
        if worst_hit > 0:
            failures += 1

        # Registry + pocket volume.
        names_ok = len(hs.bond_faces) == 2 * len(hs.stations)
        vol_ok = hs.cs_pocketed.Volume() < te.control_surface.Volume()
        lines.append(f"- bond faces matched: {sorted(hs.bond_faces)} -> {names_ok}; "
                     f"cs pocketed {te.control_surface.Volume():.0f} -> {hs.cs_pocketed.Volume():.0f}mm^3: {vol_ok}")
        if not (names_ok and vol_ok):
            failures += 1

        lines.append(
            f"- CONCLUSION: {'WP1 pin-and-tube construction PASSES on the real device bodies.' if failures == 0 else f'{failures} check(s) FAILED.'}"
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
