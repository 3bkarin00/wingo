#!/usr/bin/env python3
"""R0 probe: OCP/cadquery LOFT boundary for P2.

Calls the REAL cadquery/OCP loft path (no mocking, §0.2). Determines, on real
airfoil sections built from our own P1 NACA generator:
  1. how to build a CLOSED wire from airfoil points (spline body + a straight
     edge across the blunt TE);
  2. the actual makeLoft signature and return type;
  3. whether wire ORDER/orientation matters (loft with aligned vs rotated
     start points and observe self-intersection / validity);
  4. how to check watertightness (closed shell + BRepCheck validity) and volume.
Writes findings to docs/r0_findings/p02.md — if reality contradicts the plan,
STOP and update that file before implementing (§0.1).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p02.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def _closed_wire(cq, section_pts, z):
    """Build a closed wire at height z from canonical airfoil points using a
    spline for the body and a straight closing edge across the blunt TE."""
    from cadquery import Vector

    verts = [Vector(float(x), float(y), z) for x, y in section_pts]
    spline = cq.Edge.makeSpline(verts)
    closing = cq.Edge.makeLine(verts[-1], verts[0])
    return cq.Wire.assembleEdges([spline, closing])


def main() -> int:
    lines = ["## probe_ocp_loft.py"]
    try:
        import cadquery as cq
        import numpy as np
        from OCP.BRepCheck import BRepCheck_Analyzer

        from backend.airfoils.naca import generate_naca

        base = generate_naca("naca2412", 121).points  # canonical, unit chord

        # Three sections along span (z), tapering chord — a toy half-wing.
        sections = []
        for z, chord in [(0.0, 1.0), (5.0, 0.7), (10.0, 0.4)]:
            pts = base * np.array([chord, chord])
            sections.append(_closed_wire(cq, pts, z))

        lines.append(f"- built {len(sections)} closed section wires "
                     f"(spline body + straight TE-closing edge); "
                     f"wire type = `{type(sections[0]).__name__}`, "
                     f"closed = {sections[0].wrapped.Closed()}")

        # makeLoft — the real signature/return.
        solid = cq.Solid.makeLoft(sections, ruled=False)
        lines.append(f"- `cq.Solid.makeLoft(wires, ruled=False)` -> "
                     f"`{type(solid).__name__}`, volume = {solid.Volume():.5f}")

        analyzer = BRepCheck_Analyzer(solid.wrapped)
        shells = solid.Shells()
        closed = all(s.wrapped.Closed() for s in shells)
        lines.append(f"- validity: BRepCheck IsValid = {analyzer.IsValid()}; "
                     f"shell count = {len(shells)}; all shells Closed = {closed} "
                     f"(watertightness = valid + closed shell)")

        # Wire-ordering sensitivity: roll one section's start point and re-loft.
        rolled = base.copy()
        rolled = np.roll(rolled, len(rolled) // 3, axis=0)
        bad_sections = [
            _closed_wire(cq, base * np.array([1.0, 1.0]), 0.0),
            _closed_wire(cq, rolled * np.array([0.7, 0.7]), 5.0),
            _closed_wire(cq, base * np.array([0.4, 0.4]), 10.0),
        ]
        try:
            bad = cq.Solid.makeLoft(bad_sections, ruled=False)
            bad_valid = BRepCheck_Analyzer(bad.wrapped).IsValid()
            lines.append(f"- WIRE-ORDER TEST: rolling one section's start point "
                         f"gives volume={bad.Volume():.5f}, valid={bad_valid} — "
                         f"vs aligned volume={solid.Volume():.5f}. Misaligned "
                         f"start points {'DISTORT the loft' if abs(bad.Volume()-solid.Volume())>1e-3 else 'are tolerated'} "
                         f"→ sections must share a consistent start vertex + direction.")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"- WIRE-ORDER TEST: rolled-start loft raised "
                         f"{type(exc).__name__} — confirms sections must be "
                         f"consistently ordered before lofting.")

        assert analyzer.IsValid(), "aligned loft not valid"
        assert closed, "aligned loft shell not closed (not watertight)"
        lines.append("- CONCLUSION: build closed wires (spline + TE edge), keep a "
                     "consistent point order/start across sections, loft with "
                     "`cq.Solid.makeLoft(ruled=False)`, verify watertight via "
                     "BRepCheck_Analyzer.IsValid() + Shell.Closed().")
    except Exception as exc:  # noqa: BLE001 — probe must report, not hide
        import traceback
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        lines.append("```\n" + traceback.format_exc() + "```")
        _append(lines)
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
