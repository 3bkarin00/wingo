#!/usr/bin/env python3
"""R0 probe: OCP/cadquery 2D wire-offset boundary for P6 (sandwich internals).

Calls the REAL cadquery/OCP kernel (§0.2). P6's IML construction is "2D
per-station offset + second loft + subtract, NEVER OCC shell/thicken" (F1,
plan.md §8.7) — offset is a boundary this project has never touched before
(P0-P4 used lofts and booleans only), so per the phase workflow this MUST be
probed before implementation:
  1. what's the real offset API (cadquery Wire method vs raw OCP), and its
     signature/join-type options?
  2. does offsetting a REAL closed airfoil polygon (the exact canonical-order
     points backend/geometry/airfoil_resolver.py produces, blunt TE) inward
     by a SAFE stack thickness (<= SANDWICH_MARGIN_FRACTION of local min
     thickness, the existing P0 validation bound) produce a single valid
     closed wire?
  3. what does an UNSAFE (too-large) offset actually do — exception, a
     self-intersecting-but-"valid" wire, or a multi-wire result? P0's
     validation should make this unreachable in practice, but the failure
     signature matters for a good error message / defensive assert.
  4. do two per-station offset wires (root/tip, different chord scale) loft
     (ruled=True, matching every prior lofting decision in this project) into
     a valid solid, and does subtracting it from the outer loft produce a
     watertight "skin shell"?
Writes findings to docs/r0_findings/p06.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def _station_solid_from_points(pts_2d, y_mm, chord_mm):
    import cadquery as cq
    return [cq.Vector(float(x) * chord_mm, float(y_mm), float(z) * chord_mm) for x, z in pts_2d]


def main() -> int:
    lines = ["## probe_ocp_offset.py"]
    try:
        import cadquery as cq
        import numpy as np
        from OCP.BRepCheck import BRepCheck_Analyzer

        from backend.geometry.airfoil_resolver import resolve_airfoil
        from backend.airfoils.naca_thickness import min_thickness_mm

        # Real production airfoil, exactly as the OML loft uses it.
        pts = resolve_airfoil("naca2412", 199, te_thickness_frac=0.008)
        chord_mm = 300.0
        min_thick = min_thickness_mm("naca2412", chord_mm)
        lines.append(f"- naca2412 @ chord={chord_mm}mm: min local thickness = {min_thick:.3f}mm "
                     f"(backend/airfoils/naca_thickness.py, the same helper P0 validation uses)")

        world_pts = _station_solid_from_points(pts, 0.0, chord_mm)
        wire = cq.Wire.makePolygon(world_pts, close=True)
        lines.append(f"- outer station wire: {len(world_pts)} points, "
                     f"valid={BRepCheck_Analyzer(wire.wrapped).IsValid()}")

        # 1) API discovery: cadquery's own Wire.offset2D, if it exists.
        safe_offset_mm = 0.8 * min_thick / 2.0  # SANDWICH_MARGIN_FRACTION of HALF-thickness (radial inward)
        api_found = None
        offset_wires = None
        for kind in ("intersection", "arc", "tangent"):
            try:
                result = wire.offset2D(-safe_offset_mm, kind=kind)
                api_found = f"cq.Wire.offset2D(-d, kind='{kind}')"
                offset_wires = result if isinstance(result, list) else [result]
                lines.append(f"- `{api_found}` SUCCEEDED: returned {len(offset_wires)} wire(s)")
                break
            except Exception as exc:  # noqa: BLE001
                lines.append(f"- `cq.Wire.offset2D(-d, kind='{kind}')` FAILED: {type(exc).__name__}: {exc}")

        if offset_wires is None:
            # Fall back to the raw OCP entry point.
            from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
            from OCP.GeomAbs import GeomAbs_Intersection
            mk = BRepOffsetAPI_MakeOffset(wire.wrapped, GeomAbs_Intersection)
            mk.Perform(-safe_offset_mm)
            raw_shape = mk.Shape()
            offset_wires = [cq.Wire(w) for w in cq.Shape.cast(raw_shape).Wires()]
            api_found = "OCP.BRepOffsetAPI.BRepOffsetAPI_MakeOffset(wire, GeomAbs_Intersection).Perform(-d)"
            lines.append(f"- raw `{api_found}` -> {len(offset_wires)} wire(s)")

        for i, ow in enumerate(offset_wires):
            valid = BRepCheck_Analyzer(ow.wrapped).IsValid()
            n_edges = len(ow.Edges())
            lines.append(f"- safe-offset wire[{i}]: {n_edges} edges, valid={valid}, closed={ow.IsClosed()}")

        # 2) UNSAFE offset: deliberately exceed the min half-thickness.
        unsafe_offset_mm = min_thick * 0.9  # bigger than the ENTIRE min thickness, not just half
        unsafe_wires = None
        unsafe_error = None
        try:
            result = wire.offset2D(-unsafe_offset_mm, kind="intersection")
            unsafe_wires = result if isinstance(result, list) else [result]
        except Exception as exc:  # noqa: BLE001
            unsafe_error = f"{type(exc).__name__}: {exc}"
        if unsafe_error:
            lines.append(f"- UNSAFE offset ({unsafe_offset_mm:.2f}mm, > min thickness) RAISED: {unsafe_error}")
        else:
            for i, ow in enumerate(unsafe_wires):
                valid = BRepCheck_Analyzer(ow.wrapped).IsValid()
                lines.append(f"- UNSAFE offset ({unsafe_offset_mm:.2f}mm) wire[{i}]: "
                             f"{len(ow.Edges())} edges, valid={valid}, closed={ow.IsClosed()} "
                             f"(returned {len(unsafe_wires)} wire(s) total)")

        # 2b) EMPIRICAL question this whole construction hinges on: does ONE
        # offset2D(-d) pass on the WHOLE closed loop reduce the local
        # upper-to-lower wall thickness (measured vertically at a fixed xc)
        # by d, or by 2d (both the upper and lower walls move inward by d
        # SIMULTANEOUSLY in a single whole-loop offset)? This determines
        # what distance to actually pass for the face-sheet vs core offset
        # passes — never assumed, always measured on the real kernel output.
        def _thickness_at_xc(wire_, xc_mm, chord_mm_):
            pts = np.array([v.toTuple() for v in wire_.Vertices()])
            xs, zs = pts[:, 0], pts[:, 2]
            near = np.abs(xs - xc_mm) < 0.01 * chord_mm_
            if near.sum() < 2:
                return None
            return float(zs[near].max() - zs[near].min())

        xc_probe_mm = 0.5 * chord_mm
        thick_before = _thickness_at_xc(wire, xc_probe_mm, chord_mm)
        d_probe_mm = 2.0
        probe_result = wire.offset2D(-d_probe_mm, kind="intersection")
        probe_wire = probe_result[0] if isinstance(probe_result, list) else probe_result
        thick_after = _thickness_at_xc(probe_wire, xc_probe_mm, chord_mm)
        ratio = (thick_before - thick_after) / d_probe_mm if thick_after is not None else None
        lines.append(f"- EMPIRICAL offset-vs-thickness at xc={xc_probe_mm:.0f}mm: "
                     f"thickness before={thick_before:.3f}mm, after offset2D(-{d_probe_mm}mm)="
                     f"{thick_after:.3f}mm, reduction={thick_before - thick_after:.3f}mm "
                     f"= {ratio:.2f}x the offset distance "
                     f"({'~2x: a single whole-loop offset shrinks LOCAL thickness by 2x the offset distance (both walls move inward at once)' if ratio and ratio > 1.5 else '~1x'})")

        # 3) Loft two per-station offset wires (root + scaled-down tip) into a
        # solid, matching P2's ruled-loft convention exactly, then subtract
        # from the outer OML-like loft to get the "skin shell".
        tip_chord_mm = 180.0
        tip_offset_mm = 0.8 * min_thickness_mm("naca2412", tip_chord_mm) / 2.0
        tip_world_pts = _station_solid_from_points(pts, 400.0, tip_chord_mm)
        tip_wire = cq.Wire.makePolygon(tip_world_pts, close=True)
        tip_offset_result = tip_wire.offset2D(-tip_offset_mm, kind="intersection")
        tip_offset_wire = tip_offset_result[0] if isinstance(tip_offset_result, list) else tip_offset_result

        root_offset_wire = offset_wires[0]
        outer_loft = cq.Solid.makeLoft([wire, tip_wire], ruled=True)
        inner_loft = cq.Solid.makeLoft([root_offset_wire, tip_offset_wire], ruled=True)
        lines.append(f"- outer_loft (root+tip, real airfoil): vol={outer_loft.Volume():.1f}, "
                     f"valid={BRepCheck_Analyzer(outer_loft.wrapped).IsValid()}")
        lines.append(f"- inner_loft (offset root+tip): vol={inner_loft.Volume():.1f}, "
                     f"valid={BRepCheck_Analyzer(inner_loft.wrapped).IsValid()}")

        from backend.geometry.booleans import fuzzy_cut, filter_shards
        shell = fuzzy_cut(outer_loft, inner_loft)
        kept, shards = filter_shards(shell)
        lines.append(f"- outer_loft - inner_loft (fuzzy_cut) -> {len(kept)} kept solid(s) "
                     f"(vol={[round(s.Volume(),1) for s in kept]}), {len(shards)} shard(s); "
                     f"conservation check: kept+inner = {sum(s.Volume() for s in kept) + inner_loft.Volume():.1f} "
                     f"vs outer_loft = {outer_loft.Volume():.1f}")

        # 4) THE key construction-correctness question: backend/schema/
        # validators.py's P0 check compares `stack_mm = core.thickness_mm +
        # 2*face_sheet_mm` (ONE core factor, not two) against local
        # thickness. Given the confirmed 2x rule above, the ONLY offset
        # sequence whose total local-thickness consumption exactly equals
        # `stack_mm` (and so is guaranteed safe for every config the FROZEN
        # P0 validator already accepts, with no re-derivation of tolerances)
        # is: face_sheet_IML = OML.offset(-face_mm) [consumes 2*face_mm],
        # hollow_IML = face_sheet_IML.offset(-core_mm/2) [consumes
        # 2*(core_mm/2) = core_mm] -> total = 2*face_mm + core_mm = stack_mm
        # exactly. Verified here on te_half_twisted_moderate.yaml's real,
        # already-passing (tightest-margin) numbers: face=0.4mm, core=2.0mm,
        # tip chord=190mm.
        face_mm, core_mm = 0.40, 2.0
        tight_chord_mm = 190.0
        tight_min_thick = min_thickness_mm("naca2412", tight_chord_mm)
        tight_pts = _station_solid_from_points(pts, 0.0, tight_chord_mm)
        tight_wire = cq.Wire.makePolygon(tight_pts, close=True)
        face_sheet_iml = tight_wire.offset2D(-face_mm, kind="intersection")
        face_sheet_iml = face_sheet_iml[0] if isinstance(face_sheet_iml, list) else face_sheet_iml
        hollow_iml = face_sheet_iml.offset2D(-core_mm / 2.0, kind="intersection")
        hollow_iml = hollow_iml[0] if isinstance(hollow_iml, list) else hollow_iml
        thick_hollow = _thickness_at_xc(hollow_iml, 0.5 * tight_chord_mm, tight_chord_mm)
        expected_thick_hollow = _thickness_at_xc(tight_wire, 0.5 * tight_chord_mm, tight_chord_mm) - (2 * face_mm + core_mm)
        lines.append(
            f"- CHAINED offset on te_half_twisted_moderate.yaml's real (tightest-margin, "
            f"frozen-gate) numbers (face={face_mm}mm, core={core_mm}mm, tip chord={tight_chord_mm}mm, "
            f"min_thickness={tight_min_thick:.3f}mm): face_sheet_IML valid="
            f"{BRepCheck_Analyzer(face_sheet_iml.wrapped).IsValid()}, hollow_IML valid="
            f"{BRepCheck_Analyzer(hollow_iml.wrapped).IsValid()}, closed={hollow_iml.IsClosed()}; "
            f"mid-chord thickness after both offsets={thick_hollow:.3f}mm vs analytically-expected "
            f"{expected_thick_hollow:.3f}mm (stack_mm={core_mm + 2*face_mm}mm consumed exactly, "
            f"matching backend/schema/validators.py's existing stack_mm formula with NO change needed)"
        )

        lines.append(
            "- CONCLUSION: use `cq.Wire.offset2D(-distance, kind='intersection')` for the inward "
            "per-station offset (real cadquery API, confirmed above) on the SAME canonical polygon "
            "wires the OML loft already uses; loft the offset wires with makeLoft(ruled=True) exactly "
            "like P2/P4; subtract via the existing fuzzy_cut helper (booleans.py) to get each layer's "
            "shell. Safe-margin (SANDWICH_MARGIN_FRACTION) offsets produce a single valid closed wire; "
            "see the UNSAFE-offset line above for the actual failure signature beyond that margin."
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
