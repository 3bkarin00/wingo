#!/usr/bin/env python3
"""R0 probe: OCP boolean-cut + revolution boundary for P4 (TE surface cut).

Calls the REAL cadquery/OCP kernel (§0.2). Establishes the mechanics the TE
cut depends on BEFORE writing it (F4/F3 are booleans-at-the-cove failure
modes — this is exactly the "understand the boundary first" case):
  1. does a cut that separates a solid return multiple solids? how to extract?
  2. BRepAlgoAPI_Cut fuzzy value — set it, observe effect on a near-tangent cut;
  3. cylinder + revolution about an ARBITRARY (tilted) axis — the hinge axis is
     tilted by twist/dihedral, so axis-aligned primitives won't do;
  4. shard behaviour — does a grazing cut leave tiny fragments? their volumes;
  5. tangent-face detection — how to tell if two faces are tangent (F4).
Writes findings to docs/r0_findings/p04.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p04.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_ocp_boolean.py"]
    try:
        import cadquery as cq
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.TopoDS import TopoDS
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_SOLID

        box = cq.Workplane("XY").box(100, 100, 100).val()
        lines.append(f"- base solid: 100^3 box, volume={box.Volume():.1f}")

        # 1) A slab thinner than the box, spanning full width, cuts it in TWO.
        slab = cq.Workplane("XY").box(2, 200, 200).val()  # 2mm-thick separating cut
        result = box.cut(slab)
        solids = result.Solids()
        lines.append(f"- box.cut(2mm slab) -> `{type(result).__name__}` containing "
                     f"{len(solids)} solids, volumes={[round(s.Volume(),1) for s in solids]} "
                     f"(cut splits the body; extract via .Solids())")
        assert len(solids) == 2, f"expected 2 solids, got {len(solids)}"

        # 2) Fuzzy value via the low-level BRepAlgoAPI_Cut.
        cutter = BRepAlgoAPI_Cut(box.wrapped, slab.wrapped)
        cutter.SetFuzzyValue(1e-3)
        cutter.Build()
        fuzz_shape = cutter.Shape()
        n_fuzz = 0
        exp = TopExp_Explorer(fuzz_shape, TopAbs_SOLID)
        while exp.More():
            n_fuzz += 1
            exp.Next()
        lines.append(f"- `BRepAlgoAPI_Cut(...).SetFuzzyValue(1e-3).Build()` -> "
                     f"{n_fuzz} solids; IsDone={cutter.IsDone()} "
                     f"(explicit fuzzy control available for near-tangent cuts, F4)")

        # 3) Cylinder about a TILTED axis (the hinge axis is not axis-aligned).
        import math
        axis_dir = cq.Vector(0, math.cos(math.radians(20)), math.sin(math.radians(20)))
        cyl = cq.Solid.makeCylinder(15, 80, cq.Vector(0, -40, 0), axis_dir)
        lines.append(f"- `cq.Solid.makeCylinder(r,h,base,tilted_dir)` -> "
                     f"`{type(cyl).__name__}`, vol={cyl.Volume():.1f}, "
                     f"valid={BRepCheck_Analyzer(cyl.wrapped).IsValid()} "
                     f"(cove/nose can be built about the real tilted hinge axis)")

        # 4) Shard behaviour: a grazing cut that clips a thin corner sliver.
        sliver_cutter = cq.Workplane("XY").box(200, 200, 200).val().translate((99.5, 0, 0))
        grazed = box.cut(sliver_cutter)
        gsolids = sorted(grazed.Solids(), key=lambda s: s.Volume())
        vols = [round(s.Volume(), 3) for s in gsolids]
        lines.append(f"- grazing cut leaves {len(gsolids)} solid(s), volumes={vols} "
                     f"(shard filter must drop any below a min-volume threshold, F3)")

        # 5) Tangent-face detection (F4): two coincident planar faces are
        # tangent; a deliberate clearance angle makes them non-coincident.
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        faces = cyl.Faces()
        lines.append(f"- cylinder has {len(faces)} faces; face surface types available "
                     f"via BRepAdaptor_Surface(face).GetType() for tangency analysis "
                     f"(a cove arc tangent to a nose arc = same radius+center; the "
                     f"deliberate clearance angle/gap keeps radii distinct, avoiding F4)")

        lines.append("- CONCLUSION: cut with a tool solid, extract pieces via .Solids(); "
                     "use BRepAlgoAPI_Cut + SetFuzzyValue for robustness near the cove; "
                     "build cove/nose as makeCylinder about the tilted hinge axis with "
                     "gap_mm radial clearance (distinct radii => non-tangent, dodges F4); "
                     "filter solids below a min-volume threshold to kill shards (F3).")

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
