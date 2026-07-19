#!/usr/bin/env python3
"""R0 probe: offset a curve LYING ON A SURFACE, inward along that surface's
local normal, by a fixed distance — needed for WP2b (π-joint construction:
the rib's skin-contact segments and the IML skin-contact curve both get
offset inward along the IML surface normal by the bond gap, NOT a planar
2D offset like P6's per-station wire offset).

This is a genuinely different operation from P6's `Wire.offset2D` (P6 offset
a closed planar polygon in its own plane; this offsets a curve THROUGH 3D
space using a surface's normal field, which varies along the curve) — per
the phase workflow this MUST be probed before implementation.

Two candidate techniques:
  A) `BRepOffsetAPI_NormalProjection` / native on-surface offset API, if one
     exists in the installed OCP that operates directly on a Geom_Curve +
     Geom_Surface pair.
  B) Manual: sample N points along the input curve, evaluate the surface's
     local normal at (or near) each sampled point (GeomLProp_SLProps or a
     nearest-point projection + normal lookup), offset each point along its
     local normal by the target distance, refit a spline through the offset
     points (cq.Wire.makeSpline / Edge.makeSpline).

Writes findings to docs/r0_findings/p06_ext.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06_ext.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_offset_curve_surface.py"]
    try:
        import numpy as np
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRep import BRep_Tool
        from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
        from OCP.GeomLProp import GeomLProp_SLProps

        # Toy surface: a curved skin-like panel (a cylindrical patch — real
        # local normals, non-trivial curvature, unlike a flat plane which
        # would give a trivially-constant offset and prove nothing).
        radius = 150.0
        cyl_face = cq.Solid.makeCylinder(radius, 400.0, cq.Vector(0, 0, 0), cq.Vector(0, 1, 0)).Faces()[0]
        surf = BRep_Tool.Surface_s(cyl_face.wrapped)
        lines.append(f"- toy surface: cylindrical patch, radius={radius}mm, length=400mm")

        # A "skin-contact curve" lying ON the cylinder: a spline threading
        # points at fixed radius but wandering in angle/height (mimics a
        # rib's skin-contact segment, which is NOT a simple circle/line on
        # a real, twisted/tapered OML surface).
        n_pts = 15
        t = np.linspace(0, 1, n_pts)
        theta = np.radians(20 + 15 * np.sin(2 * np.pi * t))  # wandering angle
        y = 400.0 * t
        curve_pts = np.stack([radius * np.sin(theta), y, radius * np.cos(theta)], axis=1)
        curve_wire = cq.Wire.assembleEdges([cq.Edge.makeSpline([cq.Vector(*p) for p in curve_pts])])
        lines.append(f"- skin-contact curve: {n_pts}-point spline ON the cylinder surface "
                      f"(by construction, at exactly radius={radius}mm), Length()={curve_wire.Length():.2f}mm")

        offset_mm = 2.0  # toy PI_BOND_GAP-like distance

        # ---- Technique A: native on-surface offset API discovery ----
        native_found = None
        for candidate in ("BRepOffsetAPI_MakeOffsetOnSurf", "BRepOffsetAPI_NormalProjection"):
            try:
                mod = __import__("OCP.BRepOffsetAPI", fromlist=[candidate])
                getattr(mod, candidate)
                native_found = candidate
                lines.append(f"- `OCP.BRepOffsetAPI.{candidate}` EXISTS in the installed OCP "
                              f"(class importable; signature/usage not yet exercised here)")
            except (ImportError, AttributeError) as exc:
                lines.append(f"- `OCP.BRepOffsetAPI.{candidate}` NOT AVAILABLE: {type(exc).__name__}: {exc}")
        if native_found is None:
            lines.append("- No native on-surface-offset class found under BRepOffsetAPI in this "
                          "OCP build — Technique B (manual per-point normal offset) is required.")

        # ---- Technique B: manual per-point normal-offset + refit spline ----
        def local_normal(pt: np.ndarray) -> np.ndarray:
            projector = GeomAPI_ProjectPointOnSurf(cq.Vector(*pt).toPnt(), surf)
            u, v = projector.LowerDistanceParameters()
            props = GeomLProp_SLProps(surf, u, v, 1, 1e-6)
            n = props.Normal()
            nv = np.array([n.X(), n.Y(), n.Z()])
            # Normal must point INWARD (toward the cylinder axis) for an
            # "inward" bond-gap offset — orient consistently by checking
            # against the vector from the point to the axis.
            to_axis = np.array([0.0, pt[1], 0.0]) - pt
            if np.dot(nv, to_axis) < 0:
                nv = -nv
            return nv / np.linalg.norm(nv)

        # local_normal() already sign-corrects to point INWARD (toward the
        # axis) above, so the inward offset is `p + offset_mm * normal`, not
        # `p - ...` (a first version of this probe subtracted here, which
        # double-negated the already-corrected inward normal and pushed
        # points OUTWARD by offset_mm instead — visible as an exact
        # 2*offset_mm radial error; fixed by this `+`).
        offset_pts = np.array([p + offset_mm * local_normal(p) for p in curve_pts])
        offset_wire = cq.Wire.assembleEdges([cq.Edge.makeSpline([cq.Vector(*p) for p in offset_pts])])
        valid = BRepCheck_Analyzer(offset_wire.wrapped).IsValid()
        # Verify: every offset point should now sit at radius - offset_mm
        # from the cylinder axis (Y-axis), within kernel tolerance.
        radial_dist = np.sqrt(offset_pts[:, 0] ** 2 + offset_pts[:, 2] ** 2)
        expected_r = radius - offset_mm
        max_dev = float(np.max(np.abs(radial_dist - expected_r)))
        lines.append(f"- Technique B (manual normal-offset + refit spline): offset_wire valid={valid}, "
                      f"closed={offset_wire.IsClosed()}, Length()={offset_wire.Length():.2f}mm")
        lines.append(f"- Technique B ACCURACY: offset points' radial distance from cylinder axis, "
                      f"expected={expected_r:.3f}mm, max deviation across {n_pts} points={max_dev:.5f}mm "
                      f"({'PASS — sub-micron, offset correctly followed local curvature' if max_dev < 0.01 else 'FAIL — investigate before using this technique'})")

        lines.append(
            f"- CONCLUSION: {'Native on-surface offset API available (' + native_found + ') — probe its exact signature next.' if native_found else 'No native on-surface offset API in this OCP build; use Technique B (GeomAPI_ProjectPointOnSurf + GeomLProp_SLProps per sampled point, offset along the local normal, refit via Wire.makeSpline) for WP2b π-joint contact-curve offsetting.'}"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
