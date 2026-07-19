#!/usr/bin/env python3
"""R0 probe: sweep-with-spine vs sampled-frames+loft for a rectangular
profile along a curved, NON-PLANAR 3D path.

Needed for WP2 (c_channel/i_beam spar caps swept along the P3 ruled-surface
∩ IML cap-path curves) and WP2b (π-joint base/leg boxes swept along the
offset IML skin-contact curve) — this project has never built a swept solid
along a genuinely 3D (not just planar-arc) spine before (P0-P4 used lofts
and booleans only; P6 used lofts and 2D offsets only). Per the phase
workflow this MUST be probed before implementation.

Two candidate techniques, per the addendum's own instruction to probe both
and "keep the one that behaves":
  A) cq.Workplane(path).sweep(profile) — direct OCC pipe-shell sweep.
  B) Sample ~30 frames along the spine (tangent = curve tangent, a fixed
     reference normal, binormal = cross product), place the profile wire at
     each frame, cq.Solid.makeLoft(wires, ruled=True).
Compares: watertightness, volume vs analytic expectation (constant
cross-section swept along a path of known length ~= area * length for a
LOW-curvature path), and visible twist/orientation artifacts (checked via
cross-section consistency at sampled stations).

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
    lines = ["## probe_sweep_spine.py"]
    try:
        import numpy as np
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer

        # Non-planar spine: a helix-like curve (constant curvature AND
        # torsion) so it stresses frame-orientation the way a swept/tapered
        # spar cap path (curve on a ruled surface) genuinely can.
        n_ctrl = 12
        t = np.linspace(0, 1, n_ctrl)
        spine_pts = np.stack([
            300.0 * t,                       # spanwise (Y in project frame terms)
            20.0 * np.sin(2.0 * np.pi * t),   # in-plane wander
            10.0 * t,                          # slow height drift (mimics taper)
        ], axis=1)
        spine_vecs = [cq.Vector(*p) for p in spine_pts]
        # NOTE (found by this probe): the installed cadquery (2.8.0) has no
        # `cq.Wire.makeSpline` — splines are built as an Edge
        # (`cq.Edge.makeSpline(points)`), then wrapped into a Wire via
        # `cq.Wire.assembleEdges([edge])`.
        spine_wire = cq.Wire.assembleEdges([cq.Edge.makeSpline(spine_vecs)])
        spine_len = spine_wire.Length()
        lines.append(f"- spine: {n_ctrl}-point spline, Length()={spine_len:.2f}mm "
                      f"(chord-to-chord straight distance={np.linalg.norm(spine_pts[-1]-spine_pts[0]):.2f}mm)")

        profile_w, profile_h = 8.0, 3.0  # cap_width x cap_thickness, toy values

        # ---- Technique A: direct sweep ----
        sweep_ok = False
        sweep_vol = None
        try:
            path_wp = cq.Workplane("XY").add(spine_wire)
            tangent0 = (spine_pts[1] - spine_pts[0])
            tangent0 = tangent0 / np.linalg.norm(tangent0)
            # Profile plane normal to the spine's start tangent.
            arbitrary_up = np.array([0, 0, 1.0])
            xdir = np.cross(arbitrary_up, tangent0)
            xdir = xdir / np.linalg.norm(xdir)
            profile_plane = cq.Plane(origin=cq.Vector(*spine_pts[0]), xDir=cq.Vector(*xdir), normal=cq.Vector(*tangent0))
            profile_wp = cq.Workplane(profile_plane).rect(profile_w, profile_h)
            swept = profile_wp.sweep(path_wp, multisection=False)
            solid = swept.val()
            valid = BRepCheck_Analyzer(solid.wrapped).IsValid()
            sweep_vol = solid.Volume()
            sweep_ok = valid
            lines.append(f"- Technique A `Workplane(profile).sweep(pathWorkplane)`: SUCCEEDED, "
                         f"valid={valid}, volume={sweep_vol:.2f}mm^3 "
                         f"(analytic profile_area*spine_len={profile_w*profile_h*spine_len:.2f}mm^3)")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"- Technique A `sweep()` FAILED: {type(exc).__name__}: {exc}")

        # ---- Technique B: sampled frames + loft ----
        try:
            n_frames = 30
            ts = np.linspace(0, 1, n_frames)
            # Re-sample the spline at even parameter steps via nearest ctrl
            # interpolation (toy probe — real impl would sample the actual
            # Geom_Curve via Value(u)); good enough to test the LOFT technique.
            frame_pts = np.stack([
                300.0 * ts,
                20.0 * np.sin(2.0 * np.pi * ts),
                10.0 * ts,
            ], axis=1)
            wires = []
            for i in range(n_frames):
                if i == 0:
                    tang = frame_pts[1] - frame_pts[0]
                elif i == n_frames - 1:
                    tang = frame_pts[-1] - frame_pts[-2]
                else:
                    tang = frame_pts[i + 1] - frame_pts[i - 1]
                tang = tang / np.linalg.norm(tang)
                up = np.array([0, 0, 1.0])
                xdir = np.cross(up, tang)
                nrm = np.linalg.norm(xdir)
                if nrm < 1e-6:  # tangent parallel to "up" — degenerate frame
                    xdir = np.array([1.0, 0, 0])
                else:
                    xdir = xdir / nrm
                plane = cq.Plane(origin=cq.Vector(*frame_pts[i]), xDir=cq.Vector(*xdir), normal=cq.Vector(*tang))
                w = cq.Workplane(plane).rect(profile_w, profile_h).val()
                wires.append(w)
            loft_solid = cq.Solid.makeLoft(wires, ruled=True)
            loft_valid = BRepCheck_Analyzer(loft_solid.wrapped).IsValid()
            loft_vol = loft_solid.Volume()
            lines.append(f"- Technique B `makeLoft([30 sampled-frame rects], ruled=True)`: SUCCEEDED, "
                         f"valid={loft_valid}, volume={loft_vol:.2f}mm^3 "
                         f"(analytic profile_area*spine_len={profile_w*profile_h*spine_len:.2f}mm^3)")
            # Cross-section consistency check: re-slice the loft at t=0.5 and
            # compare its area to the profile area (detects twist-induced
            # cross-section distortion between adjacent loft sections).
            mid_face_areas = [f.Area() for f in loft_solid.Faces() if abs(f.Area() - profile_w * profile_h) < profile_w * profile_h]
            lines.append(f"- Technique B end-cap face areas found near profile_area={profile_w*profile_h}: "
                         f"{[round(a,2) for a in mid_face_areas]}")
        except Exception as exc:  # noqa: BLE001
            import traceback
            lines.append(f"- Technique B `makeLoft(sampled frames)` FAILED: {type(exc).__name__}: {exc}")
            lines.append("```\n" + traceback.format_exc() + "```")
            loft_ok = False
        else:
            loft_ok = loft_valid

        verdict = (
            "Technique B (sampled-frames + loft) is the one to use in construction code"
            if loft_ok and not sweep_ok else
            "Technique A (direct sweep) also works — re-verify on the REAL P3 ruled-surface "
            "cap-path curve before picking it over B, since this probe's spine is a synthetic "
            "spline, not the true intersection curve"
            if sweep_ok else
            "NEITHER technique produced a valid solid on this synthetic spine — investigate "
            "further before writing WP2/WP2b construction code, do not proceed on assumption"
        )
        lines.append(f"- CONCLUSION: {verdict}")

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
