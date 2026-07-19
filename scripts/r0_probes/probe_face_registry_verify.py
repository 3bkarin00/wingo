#!/usr/bin/env python3
"""R0/verify probe for the shared centroid registry (backend/geometry/face_registry.py).

Checks against the real kernel:
  - record_face + match on an UNTOUCHED face after an unrelated boolean.
  - match on a face that a boolean merely PIERCED (small hole, <10% area
    loss, centroid ~unchanged) — must still match.
  - HARD FAILURE: a boolean that consumes the recorded face raises
    RuntimeError naming it.
  - write_step_with_names -> read_step_names full round-trip: body AND face
    names recovered (the probed XDE recipe, now productionized).

Appends findings to docs/r0_findings/p06_ext.md.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06_ext.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_face_registry_verify.py (centroid registry, §8.8)"]
    failures = 0
    try:
        import cadquery as cq

        from backend.geometry.booleans import fuzzy_cut
        from backend.geometry.face_registry import (
            FaceRegistry, read_step_names, write_step_with_names,
        )

        box = cq.Solid.makeBox(40, 20, 10)  # x∈[0,40], y∈[0,20], z∈[0,10]
        # Record the +Z top face (centroid (20,10,10)).
        top_face = max(box.Faces(), key=lambda f: f.Center().z)
        reg = FaceRegistry()
        reg.record_face("TEST_BOND_TOP", top_face)
        lines.append(f"- recorded top face: centroid={top_face.Center().toTuple()}, "
                     f"area={top_face.Area():.1f}mm^2")

        # 1. Unrelated boolean (notch on the -X end, nowhere near top's bulk).
        notch = cq.Solid.makeBox(4, 20, 4, cq.Vector(-1, 0, -1))
        cut1 = fuzzy_cut(box, notch)
        m = reg.match(cut1)
        ok1 = "TEST_BOND_TOP" in m
        lines.append(f"- match after unrelated boolean: {ok1}")
        failures += 0 if ok1 else 1

        # 2. Pierced face: Ø4 hole through the top (area loss ~1.6%, centroid ~fixed).
        drill = cq.Solid.makeCylinder(2.0, 30, cq.Vector(20, 10, -5), cq.Vector(0, 0, 1))
        cut2 = fuzzy_cut(box, drill)
        m2 = reg.match(cut2)
        ok2 = "TEST_BOND_TOP" in m2 and abs(m2["TEST_BOND_TOP"].Area() - top_face.Area() + 12.57) < 1.0
        lines.append(f"- match after piercing boolean (area {top_face.Area():.1f} -> "
                     f"{m2['TEST_BOND_TOP'].Area():.1f}): {ok2}")
        failures += 0 if ok2 else 1

        # 3. Face consumed -> hard failure.
        eat = cq.Solid.makeBox(50, 30, 8, cq.Vector(-5, -5, 6))  # removes the whole top region
        cut3 = fuzzy_cut(box, eat)
        try:
            reg.match(cut3)
            lines.append("- consumed face: **FAIL — match did not raise**")
            failures += 1
        except RuntimeError as exc:
            good = "TEST_BOND_TOP" in str(exc) and "boolean ate" in str(exc)
            lines.append(f"- consumed face raises hard failure naming it: {good}")
            failures += 0 if good else 1

        # 4. Full STEP round-trip through the production helpers.
        with tempfile.TemporaryDirectory() as tmp:
            step = str(Path(tmp) / "reg.step")
            write_step_with_names([("TEST_BODY", cut2, m2)], step)
            names = read_step_names(step)
        ok4 = {"TEST_BODY", "TEST_BOND_TOP"} <= names
        lines.append(f"- STEP round-trip names recovered: {sorted(names)} -> {ok4}")
        failures += 0 if ok4 else 1

        lines.append(
            f"- CONCLUSION: {'centroid registry PASSES on the real kernel — WP1/gates can build on it.' if failures == 0 else f'{failures} check(s) FAILED.'}"
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
