#!/usr/bin/env python3
"""R0 probe: rotate a solid about an ARBITRARY 3D axis (two points defining
a line, not necessarily a coordinate axis) — needed for WP1's swept-pocket
construction (union of rotated copies of a carrier+tube body through
±(max_deflection + margin) about the true hinge axis, which is a general
3D line derived from geometry, not aligned with X/Y/Z) and reusable for P8
(kinematic sweep gate), which flagged the exact same need in a prior
handoff.md note.

Candidate techniques:
  A) `cq.Shape.rotate(axis_start_point, axis_end_point, angle_deg)` —
     cadquery's own convenience method, if it accepts two arbitrary points.
  B) Raw `OCP.gp.gp_Trsf().SetRotation(gp_Ax1(location, direction), angle)`
     + `BRepBuilderAPI_Transform`.

Verification: rotate a point-like probe solid (small sphere) at a known
offset from an off-axis line by a known angle, and check its new position
against the analytic rotation formula (Rodrigues' rotation formula) —
not just "did it not crash."

Writes findings to docs/r0_findings/p07.md (append — this is WP1's probe
trail, kept separate from the retired lug/tang trail per ADR-005).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p07.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def _rodrigues(point, axis_point, axis_dir_unit, angle_deg):
    import numpy as np
    theta = np.radians(angle_deg)
    v = point - axis_point
    k = axis_dir_unit
    v_rot = (
        v * np.cos(theta)
        + np.cross(k, v) * np.sin(theta)
        + k * np.dot(k, v) * (1 - np.cos(theta))
    )
    return axis_point + v_rot


def main() -> int:
    lines = ["## probe_rotation_axis.py — WP1 probe trail (ADR-005; the pre-pivot lug/tang", "trail above is kept as historical record, not overwritten)"]
    try:
        import numpy as np
        import cadquery as cq

        # Arbitrary, deliberately off-axis, non-unit-length 3D line — mimics
        # a real derived hinge axis (not aligned with any global axis).
        axis_p0 = np.array([50.0, 0.0, 20.0])
        axis_p1 = np.array([50.0 + 100.0, 30.0, 20.0 + 15.0])
        axis_dir = axis_p1 - axis_p0
        axis_dir_unit = axis_dir / np.linalg.norm(axis_dir)
        angle_deg = 25.0
        lines.append(f"- axis: p0={axis_p0.tolist()} p1={axis_p1.tolist()} (deliberately off every "
                      f"global coordinate axis), rotation angle={angle_deg} deg")

        # Probe body: small sphere at a known offset from the axis, centered
        # away from the axis so rotation is unambiguously observable.
        probe_center = np.array([120.0, 10.0, 5.0])
        probe_radius = 3.0
        # NOTE (found by this probe's first run): makeSphere's default
        # angleDegrees1/2 do NOT sweep a full -90..90 latitude range in the
        # installed cadquery version — the 2-arg call produces a HEMISPHERE
        # (centroid 3/8*r above `pnt`), not a full sphere centered at `pnt`.
        # Explicit angles are required for a true full sphere.
        probe_solid = cq.Solid.makeSphere(probe_radius, cq.Vector(*probe_center), cq.Vector(0, 0, 1), -90, 90, 360)
        expected_center_after = _rodrigues(probe_center, axis_p0, axis_dir_unit, angle_deg)
        lines.append(f"- probe body: sphere r={probe_radius}mm at center={probe_center.tolist()}; "
                      f"analytic (Rodrigues) expected center after rotation={np.round(expected_center_after, 4).tolist()}")

        # ---- Technique A: cq.Shape.rotate(axisStartPoint, axisEndPoint, angleDegrees) ----
        a_ok = False
        try:
            rotated_a = probe_solid.rotate(
                cq.Vector(*axis_p0), cq.Vector(*axis_p1), angle_deg
            )
            com_a = np.array(rotated_a.Center().toTuple())
            dev_a = float(np.linalg.norm(com_a - expected_center_after))
            a_ok = dev_a < 1e-3
            lines.append(f"- Technique A `cq.Shape.rotate(p0, p1, angle_deg)`: SUCCEEDED, "
                          f"resulting center of mass={np.round(com_a, 4).tolist()}, "
                          f"deviation from analytic={dev_a:.6f}mm "
                          f"({'PASS' if a_ok else 'FAIL — signature/sign/units may differ from assumption'})")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"- Technique A `cq.Shape.rotate(p0, p1, angle_deg)` FAILED: {type(exc).__name__}: {exc}")

        # ---- Technique B: raw gp_Trsf + gp_Ax1 ----
        b_ok = False
        try:
            from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
            from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

            trsf = gp_Trsf()
            ax1 = gp_Ax1(gp_Pnt(*axis_p0.tolist()), gp_Dir(*axis_dir_unit.tolist()))
            trsf.SetRotation(ax1, np.radians(angle_deg))
            transformer = BRepBuilderAPI_Transform(probe_solid.wrapped, trsf, True)
            rotated_b_shape = transformer.Shape()
            rotated_b = cq.Shape.cast(rotated_b_shape)
            com_b = np.array(rotated_b.Center().toTuple())
            dev_b = float(np.linalg.norm(com_b - expected_center_after))
            b_ok = dev_b < 1e-3
            lines.append(f"- Technique B `gp_Trsf().SetRotation(gp_Ax1(p0, dir), radians)` + "
                          f"`BRepBuilderAPI_Transform`: SUCCEEDED, resulting center of mass="
                          f"{np.round(com_b, 4).tolist()}, deviation from analytic={dev_b:.6f}mm "
                          f"({'PASS' if b_ok else 'FAIL'})")
        except Exception as exc:  # noqa: BLE001
            import traceback
            lines.append(f"- Technique B `gp_Trsf`/`BRepBuilderAPI_Transform` FAILED: {type(exc).__name__}: {exc}")
            lines.append("```\n" + traceback.format_exc() + "```")

        # ---- Union-of-rotated-copies smoke test (the actual WP1 technique) ----
        if a_ok or b_ok:
            rotate_fn = (
                (lambda s, ang: s.rotate(cq.Vector(*axis_p0), cq.Vector(*axis_p1), ang))
                if a_ok else
                (lambda s, ang: cq.Shape.cast(
                    BRepBuilderAPI_Transform(
                        s.wrapped,
                        gp_Trsf().SetRotation(gp_Ax1(gp_Pnt(*axis_p0.tolist()), gp_Dir(*axis_dir_unit.tolist())), np.radians(ang)) or gp_Trsf(),
                        True,
                    ).Shape()
                ))
            )
            try:
                step_deg = 2.0
                steps = np.arange(-angle_deg, angle_deg + 1e-6, step_deg)
                union_body = None
                t0 = __import__("time").perf_counter()
                for ang in steps:
                    copy = rotate_fn(probe_solid, float(ang))
                    union_body = copy if union_body is None else union_body.fuse(copy)
                t1 = __import__("time").perf_counter()
                lines.append(f"- union-of-rotated-copies smoke test: {len(steps)} copies at {step_deg}deg "
                              f"steps through ±{angle_deg}deg, union succeeded, "
                              f"union.Volume()={union_body.Volume():.2f}mm^3 "
                              f"(single sphere volume={probe_solid.Volume():.2f}mm^3 — union should exceed "
                              f"this since copies sweep apart), time={t1-t0:.2f}s for this toy body "
                              f"(WP1's real carrier+tube body will cost proportionally more per fuse — "
                              f"log per-step timing in construction code per the addendum's own instruction)")
            except Exception as exc:  # noqa: BLE001
                import traceback
                lines.append(f"- union-of-rotated-copies smoke test FAILED: {type(exc).__name__}: {exc}")
                lines.append("```\n" + traceback.format_exc() + "```")

        lines.append(
            f"- CONCLUSION: {'Technique A (cq.Shape.rotate) is real, accurate to sub-micron, and simplest — use it in WP1/P8 construction code.' if a_ok else ('Technique A failed/unavailable; Technique B (raw gp_Trsf+gp_Ax1+BRepBuilderAPI_Transform) is the fallback — use it instead.' if b_ok else 'NEITHER technique produced an accurate rotation — investigate further before writing WP1 pocket-sweep or P8 kinematic-sweep code, do not proceed on assumption.')}"
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
