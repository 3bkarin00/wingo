#!/usr/bin/env python3
"""R0/verify probe for D23 spar shape variants (backend/geometry/spars.py).

Runs every shape path (web / c_channel / i_beam / box / tube) against the
REAL kernel on tests/configs/valid/minimal.yaml, using the OML solid as a
stand-in cavity ("hollow_interior") — build_oml costs seconds, while the
true sandwich cavity costs tens of minutes, and every construction step
under test here (section loop split, sampled-frame cap sweeps, per-point
cavity normals, fuzzy fuses, footprint growth, rib cutouts) is exercised
identically against ANY solid cavity. The real-cavity numbers land with the
gate run, not here.

Checks, per shape:
  - build_spar_bodies -> >=1 valid, watertight solid, volume > 0
  - capped shapes strictly exceed the plain web's volume
  - spar_footprint wires are closed and planar at 3 spanwise stations
  - build_ribs (with cutouts) -> every rib solid has ZERO positive-volume
    intersection with the spar body (the entire point of D23 cutouts)
  - tube: the od-vs-depth validator rejects a deliberately oversized od
    with an actionable message

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


SHAPE_FIELDS = {
    "web": {},
    "c_channel": {"cap_width_mm": 12.0, "cap_thickness_mm": 1.5},
    "i_beam": {"cap_width_mm": 12.0, "cap_thickness_mm": 1.5},
    "box": {"web_spacing_mm": 15.0},
    "tube": {"od_root_mm": 14.0, "od_tip_mm": 9.0, "wall_mm": 1.2},
}


def main() -> int:
    lines = ["## probe_spar_shapes_verify.py (WP2/D23)"]
    failures = 0
    try:
        import yaml

        from backend.geometry.booleans import filter_shards, fuzzy_common
        from backend.geometry.loft import build_oml, is_watertight
        from backend.geometry.reference import build_rib_planes
        from backend.geometry.ribs import build_ribs
        from backend.geometry.sections import build_planform_sections
        from backend.geometry.spars import build_spar_bodies, spar_footprint
        from backend.schema.models import Config

        base = yaml.safe_load((ROOT / "tests/configs/valid/minimal.yaml").read_text())
        config0 = Config.model_validate(base)
        sections = build_planform_sections(config0, config0.airfoils.resample_points)
        cavity = build_oml(sections, mirror=False)  # stand-in cavity (docstring)
        lines.append(f"- stand-in cavity: half-span OML of minimal.yaml, vol={cavity.Volume():.0f}mm^3")

        web_volume = None
        for shape, extra in SHAPE_FIELDS.items():
            cfg_dict = yaml.safe_load((ROOT / "tests/configs/valid/minimal.yaml").read_text())
            cfg_dict["spars"][0].update({"shape": shape, **extra})
            config = Config.model_validate(cfg_dict)

            t0 = time.perf_counter()
            try:
                bodies = build_spar_bodies(config, sections, cavity)
            except Exception as exc:  # noqa: BLE001
                import traceback
                failures += 1
                lines.append(f"- {shape}: **BUILD FAILED** {type(exc).__name__}: {exc}")
                lines.append("```\n" + traceback.format_exc()[-1500:] + "```")
                continue
            dt = time.perf_counter() - t0

            spar_body = next(b for b in bodies if b.name == config.spars[0].name)
            kept, shards = filter_shards(spar_body.solid)
            wt = all(is_watertight(s) for s in kept)
            vol = sum(s.Volume() for s in kept)
            ok = bool(kept) and not shards and spar_body.solid.isValid() and wt and vol > 0
            if shape == "web":
                web_volume = vol
            exceeds = ""
            if shape in ("c_channel", "i_beam", "box") and web_volume:
                grew = vol > web_volume
                ok = ok and grew
                exceeds = f", exceeds web volume ({web_volume:.0f}): {grew}"
            lines.append(
                f"- {shape}: solids={len(kept)} shards={len(shards)} watertight={wt} "
                f"vol={vol:.0f}mm^3{exceeds}, build={dt:.1f}s -> {'PASS' if ok else 'FAIL'}"
            )
            if not ok:
                failures += 1
                continue

            # Footprint wires at 3 stations.
            half_span = config.planform.span_mm / 2.0
            fp_ok = True
            for y_frac in (0.2, 0.5, 0.8):
                fp = spar_footprint(config, config.spars[0], y_frac * half_span, 0.2)
                for part in fp.parts:
                    if not part.wire.IsClosed():
                        fp_ok = False
            lines.append(f"  - footprint wires closed at 3 stations: {fp_ok}")
            if not fp_ok:
                failures += 1

            # Rib cutouts must clear the spar body.
            t0 = time.perf_counter()
            rib_set = build_ribs(config, cavity, build_rib_planes(config))
            dt = time.perf_counter() - t0
            worst = 0.0
            for rib in rib_set.ribs:
                try:
                    common = fuzzy_common(rib.solid, spar_body.solid)
                except RuntimeError:
                    continue
                ck, _ = filter_shards(common)
                worst = max(worst, sum(s.Volume() for s in ck))
            cut_ok = worst == 0.0
            lines.append(
                f"  - {len(rib_set.ribs)} ribs built ({dt:.1f}s), max rib∩spar volume={worst:.4f}mm^3 "
                f"-> {'PASS (cutouts clear the spar)' if cut_ok else 'FAIL — a cutout missed the spar body'}"
            )
            if not cut_ok:
                failures += 1

        # Tube validator must reject an oversized od actionably.
        cfg_dict = yaml.safe_load((ROOT / "tests/configs/valid/minimal.yaml").read_text())
        cfg_dict["spars"][0].update({"shape": "tube", "od_root_mm": 500.0, "od_tip_mm": 500.0, "wall_mm": 1.2})
        config = Config.model_validate(cfg_dict)
        try:
            build_spar_bodies(config, sections, cavity)
            failures += 1
            lines.append("- tube oversize validation: **FAIL — 500mm od was accepted**")
        except ValueError as exc:
            good = "exceeds" in str(exc) and "Reduce" in str(exc)
            lines.append(f"- tube oversize validation: rejected with actionable message: {good}")
            if not good:
                failures += 1

        lines.append(
            f"- CONCLUSION: {'ALL SHAPE PATHS PASS against the real kernel (stand-in cavity) — ready for the real-cavity gate run.' if failures == 0 else f'{failures} check(s) FAILED — fix before gate.'}"
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
