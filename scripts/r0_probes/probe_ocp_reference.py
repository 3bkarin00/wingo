#!/usr/bin/env python3
"""R0 probe: OCP boundary for P3 (reference geometry).

Calls the REAL cadquery/OCP APIs P3 introduces beyond P2's loft probe
(docs/r0_findings/p02.md): ruled spar surfaces, solid point-classification,
and — critically — distance-from-a-point-to-a-shape, which is what the P3
gate needs to enforce "hinge axis containment WITH MARGIN >= sandwich stack"
(not just point-in-solid, which says nothing about how deep inside it is).
Writes findings to docs/r0_findings/p03.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p03.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_ocp_reference.py"]
    try:
        import cadquery as cq
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN, TopAbs_ON

        box = cq.Workplane("XY").box(100, 100, 100).val()  # centered at origin
        lines.append(f"- test solid: 100x100x100 box centered at origin, "
                     f"volume={box.Volume()}")

        # 1) Face.makeRuledSurface + Shell.makeShell (spar surfaces).
        e1 = cq.Edge.makeLine(cq.Vector(0, 0, -50), cq.Vector(0, 0, 50))
        e2 = cq.Edge.makeLine(cq.Vector(50, 50, -50), cq.Vector(50, 50, 50))
        face = cq.Face.makeRuledSurface(e1, e2)
        shell = cq.Shell.makeShell([face])
        lines.append(f"- `cq.Face.makeRuledSurface(edge, edge)` -> `{type(face).__name__}`; "
                     f"`cq.Shell.makeShell([face])` -> `{type(shell).__name__}`, "
                     f"isValid={shell.isValid()}")

        # 2) Point classification: center (deep inside) vs near-surface point.
        classifier = BRepClass3d_SolidClassifier(box.wrapped)
        for label, pnt in [("center", gp_Pnt(0, 0, 0)), ("near-surface", gp_Pnt(49.999, 0, 0))]:
            classifier.Perform(pnt, 1e-6)
            lines.append(f"- BRepClass3d_SolidClassifier at {label} {pnt.X(), pnt.Y(), pnt.Z()}: "
                         f"state={classifier.State()} (IN={TopAbs_IN}, ON={TopAbs_ON})")

        # 3) FIRST ATTEMPT (wrong): distance from an interior point to the
        # SOLID itself. A solid is a volume; a vertex inside that volume is
        # topologically part of it, so BRepExtrema_DistShapeShape reports 0
        # for EVERY interior point, not the depth from the boundary.
        vertex_center = BRepBuilderAPI_MakeVertex(gp_Pnt(0, 0, 0)).Vertex()
        dc = BRepExtrema_DistShapeShape(vertex_center, box.wrapped)
        dc.Perform()
        lines.append(f"- WRONG APPROACH: `BRepExtrema_DistShapeShape(vertex_at_center, "
                     f"SOLID).Value()` = {dc.Value():.4f} mm — 0 for ANY interior point "
                     f"(vertex-in-volume is trivially 'touching'), useless as a margin metric.")

        # 4) CORRECT: distance to the solid's boundary SHELL (surface only,
        # no volume) — this is the real point-to-surface / "how deep inside"
        # distance, i.e. exactly what "margin >= sandwich stack" means.
        shells = box.Shells()
        lines.append(f"- box.Shells() -> {len(shells)} shell(s)")
        for label, pnt in [("center", (0.0, 0.0, 0.0)), ("near-surface", (49.9, 0.0, 0.0))]:
            vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*pnt)).Vertex()
            dist_calc = BRepExtrema_DistShapeShape(vertex, shells[0].wrapped)
            dist_calc.Perform()
            d = dist_calc.Value()
            lines.append(f"- `BRepExtrema_DistShapeShape(vertex_at_{label}, box.Shells()[0]"
                         f").Value()` = {d:.4f} mm (expected: center=50.0 [half box width], "
                         f"near-surface=0.1)")
            expected = 50.0 if label == "center" else 0.1
            assert abs(d - expected) < 1e-3, f"{label}: got {d}, expected ~{expected}"

        lines.append("- CONCLUSION: distance-to-SOLID is always 0 for interior points — "
                     "useless. Must compute `BRepExtrema_DistShapeShape(vertex, "
                     "solid.Shells()[0].wrapped).Value()` (distance to the boundary SHELL) "
                     "to get the true point-to-surface margin. Combine with the "
                     "point-in-solid classifier (must be IN, not just close to the shell "
                     "from outside) for a complete containment-with-margin check.")

    except Exception as exc:  # noqa: BLE001
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
