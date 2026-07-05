#!/usr/bin/env python3
"""R0 probe: cadquery/OCP boundary.

Calls the REAL installed cadquery (which bundles OCP) — no mocking (§0.2).
Prints actual entry points/signatures and runs one trivial op: build a box,
measure its volume, and confirm it round-trips through the OCC validity
checker. Appends findings to docs/r0_findings/p00.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FINDINGS = ROOT / "docs" / "r0_findings" / "p00.md"


def main() -> int:
    lines = ["## probe_ocp.py"]
    try:
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer

        lines.append(f"- cadquery version: `{cq.__version__}`")

        box = cq.Workplane("XY").box(10, 20, 30)
        solid = box.val()
        volume = solid.Volume()
        expected = 10 * 20 * 30
        lines.append(
            f"- `cq.Workplane('XY').box(10, 20, 30).val().Volume()` = {volume} "
            f"(expected {expected}, delta {abs(volume - expected):.6g})"
        )

        analyzer = BRepCheck_Analyzer(solid.wrapped)
        lines.append(
            f"- `BRepCheck_Analyzer(solid.wrapped).IsValid()` = {analyzer.IsValid()}"
        )
        lines.append(
            "- entry point confirmed: `cadquery.Workplane`, `.val().wrapped` "
            "gives the underlying `OCP.TopoDS.TopoDS_Shape` for direct OCP calls."
        )

        assert abs(volume - expected) < 1e-6, "box volume mismatch"
        assert analyzer.IsValid(), "box solid not OCC-valid"

    except Exception as exc:  # noqa: BLE001 - probe must report, not hide, failures
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        _append(lines)
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    sys.exit(main())
