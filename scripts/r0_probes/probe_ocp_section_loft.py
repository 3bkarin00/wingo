#!/usr/bin/env python3
"""R0 probe: section + normal-foot + arc/spline + loft for the refined P4 cut.

The refined TE construction (per-station 2D profiles in planes PERPENDICULAR
to the hinge axis, arcs centered on the axis, lofted spanwise) needs several
OCP operations verified on the REAL kernel before coding (§0.2):
  1. section a solid with an arbitrary plane -> cross-section edges;
  2. sample those edges into ordered 3D points;
  3. normal foot: nearest point on the (upper/lower) skin to the axis point C,
     and the skin tangent there (the C->foot direction must be ⟂ tangent — the
     tangency mechanism);
  4. arc centered at C in the station plane (cq.Edge.makeCircle with dir = axis);
  5. G1 blend spline (cq.Edge.makeSpline with tangents);
  6. loft station profile wires (cq.Solid.makeLoft).
Writes findings to docs/r0_findings/p04.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p04.md"


def _append(lines):
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_ocp_section_loft.py (refined per-station construction)"]
    try:
        import numpy as np
        import yaml
        import cadquery as cq
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.gp import gp_Pln, gp_Pnt, gp_Dir

        from backend.schema.models import Config
        from backend.geometry.sections import build_planform_sections
        from backend.geometry.loft import build_oml
        from backend.geometry.reference import build_hinge_axes

        config = Config.model_validate(
            yaml.safe_load((ROOT / "tests/configs/devices/te_half.yaml").read_text())
        )
        oml = build_oml(build_planform_sections(config), config.planform.mirror)
        axis = build_hinge_axes(config)["te"]
        p0 = np.array([axis.startPoint().x, axis.startPoint().y, axis.startPoint().z])
        p1 = np.array([axis.endPoint().x, axis.endPoint().y, axis.endPoint().z])
        h = (p1 - p0) / np.linalg.norm(p1 - p0)
        a = np.array([1.0, 0, 0]) - np.dot([1.0, 0, 0], h) * h
        a /= np.linalg.norm(a)
        u = np.cross(h, a); u /= np.linalg.norm(u)
        C = p0 + 0.5 * (p1 - p0)  # mid-span station point on the axis

        # 1) section the OML with the plane ⟂ h through C.
        pln = gp_Pln(gp_Pnt(*C), gp_Dir(*h))
        sec = BRepAlgoAPI_Section(oml.wrapped, pln)
        sec.Build()
        sec_shape = cq.Shape.cast(sec.Shape())
        edges = sec_shape.Edges()
        lines.append(f"- `BRepAlgoAPI_Section(oml, plane⟂hinge)` -> {len(edges)} edges "
                     f"(the airfoil cross-section at the tilted station)")

        # 2) sample edges into 3D points.
        pts = []
        for e in edges:
            ad = BRepAdaptor_Curve(e.wrapped)
            t0, t1 = ad.FirstParameter(), ad.LastParameter()
            for i in range(25):
                t = t0 + (t1 - t0) * i / 24.0
                v = ad.Value(t)
                pts.append([v.X(), v.Y(), v.Z()])
        pts = np.array(pts)
        lines.append(f"- sampled section into {len(pts)} points")

        # 3) normal feet: nearest upper/lower skin point to C, + local tangent.
        rel = pts - C
        side = rel @ u
        upper = pts[side > 0]
        lower = pts[side < 0]
        du = np.linalg.norm(upper - C, axis=1)
        dl = np.linalg.norm(lower - C, axis=1)
        Pu, Ru = upper[np.argmin(du)], float(du.min())
        Pl, Rl = lower[np.argmin(dl)], float(dl.min())
        # tangent at Pu via nearest two upper neighbours
        order = np.argsort(np.linalg.norm(upper - Pu, axis=1))
        tan = upper[order[1]] - upper[order[2]]
        tan /= np.linalg.norm(tan)
        radial = (Pu - C) / np.linalg.norm(Pu - C)
        perp_deg = abs(90.0 - np.degrees(np.arccos(abs(np.clip(np.dot(tan, radial), -1, 1)))))
        lines.append(f"- normal feet: Ru={Ru:.3f} (upper), Rl={Rl:.3f} (lower); "
                     f"C→Pu vs skin tangent deviates {perp_deg:.2f}° from perpendicular "
                     f"(≈0 confirms the arc-through-foot is tangent to the skin)")

        # 4) arc centered at C in the station plane.
        arc = cq.Edge.makeCircle(Ru, cq.Vector(*C), cq.Vector(*h), angle1=0, angle2=120)
        lines.append(f"- `cq.Edge.makeCircle(Ru, C, dir=hinge, 0..120°)` -> "
                     f"`{type(arc).__name__}`, length={arc.Length():.2f} "
                     f"(axis-centered arc; radius constant under rotation about the axis)")

        # 5) G1 blend spline through two points with end tangents.
        spline = cq.Edge.makeSpline(
            [cq.Vector(*Pu), cq.Vector(*Pl)],
            tangents=[cq.Vector(*tan), cq.Vector(*tan)],
        )
        lines.append(f"- `cq.Edge.makeSpline([...], tangents=[...])` -> "
                     f"`{type(spline).__name__}`, length={spline.Length():.2f} "
                     f"(G1 blend with prescribed end tangents)")

        # 6) loft three axis-centered arcs at three stations -> a surface.
        arcs = []
        for frac in (0.2, 0.5, 0.8):
            Cn = p0 + frac * (p1 - p0)
            arcs.append(cq.Wire.assembleEdges([
                cq.Edge.makeCircle(Ru, cq.Vector(*Cn), cq.Vector(*h), angle1=-60, angle2=60)
            ]))
        lofted = cq.Solid.makeLoft(arcs, ruled=True)
        lines.append(f"- loft 3 axis-centered arc wires -> `{type(lofted).__name__}` "
                     f"(per-station profiles loft along the span)")

        assert perp_deg < 5.0, f"normal-foot tangency check off: {perp_deg}°"
        lines.append("- CONCLUSION: section⟂hinge → sample → nearest-upper/lower = normal feet "
                     "(C→foot ⟂ skin tangent, so an axis-centered arc through the foot is "
                     "tangent to the skin); build nose as makeCircle arcs (dir=hinge) + "
                     "makeSpline G1 blends; loft the per-station wires. All verified.")
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
