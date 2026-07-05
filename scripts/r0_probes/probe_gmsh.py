#!/usr/bin/env python3
"""R0 probe: Gmsh boundary.

Calls the REAL installed gmsh (§0.2) — imports, prints version, and meshes a
trivial surface (a unit square) to confirm the initialize/model/mesh/finalize
entry points before any geometry-phase code depends on them. Appends
findings to docs/r0_findings/p00.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FINDINGS = ROOT / "docs" / "r0_findings" / "p00.md"


def main() -> int:
    lines = ["## probe_gmsh.py"]
    try:
        import gmsh

        lines.append(f"- gmsh version: `{gmsh.__version__}`")

        gmsh.initialize()
        try:
            gmsh.model.add("r0_probe_square")
            p1 = gmsh.model.geo.addPoint(0, 0, 0, 1.0)
            p2 = gmsh.model.geo.addPoint(1, 0, 0, 1.0)
            p3 = gmsh.model.geo.addPoint(1, 1, 0, 1.0)
            p4 = gmsh.model.geo.addPoint(0, 1, 0, 1.0)
            l1 = gmsh.model.geo.addLine(p1, p2)
            l2 = gmsh.model.geo.addLine(p2, p3)
            l3 = gmsh.model.geo.addLine(p3, p4)
            l4 = gmsh.model.geo.addLine(p4, p1)
            loop = gmsh.model.geo.addCurveLoop([l1, l2, l3, l4])
            surface = gmsh.model.geo.addPlaneSurface([loop])
            gmsh.model.geo.synchronize()
            gmsh.model.mesh.generate(2)

            node_tags, _, _ = gmsh.model.mesh.getNodes()
            elem_types, elem_tags, _ = gmsh.model.mesh.getElements(dim=2)
            n_nodes = len(node_tags)
            n_elems = sum(len(t) for t in elem_tags)

            lines.append(
                f"- unit-square mesh: {n_nodes} nodes, {n_elems} 2D elements "
                f"(surface tag {surface})"
            )
            lines.append(
                "- entry points confirmed: `gmsh.model.geo.add*` for CAD-lite "
                "construction, `gmsh.model.mesh.generate(2)`, "
                "`gmsh.model.mesh.getNodes/getElements` for extraction."
            )
            assert n_nodes > 0, "no nodes produced"
            assert n_elems > 0, "no elements produced"
        finally:
            gmsh.finalize()

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
