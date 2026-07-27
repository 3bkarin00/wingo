#!/usr/bin/env python3
"""R0 probe: TRIPLE chained 2D offset for the 3-layer sandwich panel (P6).

Follow-up to probe_ocp_offset.py after a product-review correction: a
sandwich panel is outer face sheet / core / inner face sheet PER WALL —
the first construction delivered only an outer face and a half-thickness
core (no inner face sheet). The correct per-station offset chain is
full-value:

    face_IML   = OML.offset2D(-face_mm)    # outer face sheet, wall = face_mm
    core_IML   = face_IML.offset2D(-core_mm)   # core, wall = core_mm
    hollow_IML = core_IML.offset2D(-face_mm)   # inner face sheet, wall = face_mm

Per-wall consumption = face+core+face = stack_mm (exactly the FROZEN P0
per-wall formula); TOTAL local thickness consumed = 2*stack_mm. Several
frozen configs' aft-of-x/c=0.9 region is thinner than 2*stack_mm at the
tip, so the innermost offsets are expected to self-clip there
(kind="intersection"). What this probe must establish on the REAL kernel
before implementation:
  1. does the triple chain produce valid closed wires at an UNCLIPPED
     station (root), with mid-chord thickness consumption == 2*stack_mm?
  2. at te_half_twisted_moderate's tip (190mm chord, 2*stack=5.6mm vs
     min sampled thickness 5.5mm — the walls just merge aft): does the
     hollow wire come back as ONE valid closed wire (clipped), or
     multiple/invalid?
  3. harsher over-pack (te_half's stack 3.8 on a 190mm chord,
     2*stack=7.6mm vs 5.5mm): failure signature?
  4. does a ruled loft between an UNCLIPPED root wire and a CLIPPED tip
     wire produce a valid solid, and do the ring subtractions stay
     watertight/shard-free with volume conservation?
Appends findings to docs/r0_findings/p06.md.
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


def main() -> int:
    lines = ["## probe_ocp_offset_3layer.py"]
    try:
        import cadquery as cq
        import numpy as np
        from OCP.BRepCheck import BRepCheck_Analyzer

        from backend.geometry.airfoil_resolver import resolve_airfoil
        from backend.airfoils.naca_thickness import min_thickness_mm

        pts = resolve_airfoil("naca2412", 199, te_thickness_frac=0.008)

        def station_wire(chord_mm, y_mm=0.0):
            world = [cq.Vector(float(x) * chord_mm, y_mm, float(z) * chord_mm) for x, z in pts]
            return cq.Wire.makePolygon(world, close=True)

        def off(w, d):
            r = w.offset2D(-d, kind="intersection")
            return r if isinstance(r, list) else [r]

        def describe(tag, wires):
            parts = []
            for i, w in enumerate(wires):
                parts.append(f"wire[{i}]: {len(w.Edges())} edges, "
                             f"valid={BRepCheck_Analyzer(w.wrapped).IsValid()}, closed={w.IsClosed()}")
            return f"- {tag}: {len(wires)} wire(s) — " + "; ".join(parts)

        def thickness_at_xc(w, xc_mm, chord_mm):
            arr = np.array([v.toTuple() for v in w.Vertices()])
            near = np.abs(arr[:, 0] - xc_mm) < 0.01 * chord_mm
            if near.sum() < 2:
                return None
            return float(arr[near, 2].max() - arr[near, 2].min())

        # 1) UNCLIPPED chain at te_half_twisted_moderate's root (300mm).
        face_mm, core_mm = 0.40, 2.0
        stack = 2 * face_mm + core_mm
        root = station_wire(300.0)
        f_root = off(root, face_mm)
        c_root = off(f_root[0], core_mm)
        h_root = off(c_root[0], face_mm)
        lines.append(describe("root(300mm) face_IML", f_root))
        lines.append(describe("root(300mm) core_IML", c_root))
        lines.append(describe("root(300mm) hollow_IML", h_root))
        t0 = thickness_at_xc(root, 150.0, 300.0)
        t3 = thickness_at_xc(h_root[0], 150.0, 300.0)
        lines.append(f"- root mid-chord thickness: outer={t0:.3f}mm, after triple chain={t3:.3f}mm, "
                     f"consumed={t0 - t3:.3f}mm vs expected 2*stack_mm={2 * stack:.3f}mm")

        # 2) te_half_twisted_moderate tip (190mm): 2*stack=5.6 vs min_t=5.50 —
        # innermost wire should clip in the aft band.
        tip_min_t = min_thickness_mm("naca2412", 190.0)
        tip = station_wire(190.0, y_mm=1045.0)
        f_tip = off(tip, face_mm)
        c_tip = off(f_tip[0], core_mm)
        h_tip = off(c_tip[0], face_mm)
        lines.append(f"- tip(190mm) min sampled thickness={tip_min_t:.3f}mm vs 2*stack={2 * stack:.3f}mm "
                     f"(walls merge aft of ~x/c=0.9 by construction)")
        lines.append(describe("tip(190mm) face_IML", f_tip))
        lines.append(describe("tip(190mm) core_IML", c_tip))
        lines.append(describe("tip(190mm) hollow_IML (expected CLIPPED)", h_tip))

        # 3) Harsher over-pack: te_half's stack (face=0.4, core=3.0 -> 3.8;
        # 2*stack=7.6) applied to the same 190mm section.
        h2 = off(off(off(tip, 0.4)[0], 3.0)[0], 0.4)
        lines.append(describe("tip(190mm) hollow_IML @ core=3.0 (2*stack=7.6 vs 5.5)", h2))

        # 4) Ruled loft unclipped-root + clipped-tip, then ring subtractions.
        from backend.geometry.booleans import fuzzy_cut, fuzzy_common, filter_shards

        outer_loft = cq.Solid.makeLoft([root, tip], ruled=True)
        face_loft = cq.Solid.makeLoft([f_root[0], f_tip[0]], ruled=True)
        core_loft = cq.Solid.makeLoft([c_root[0], c_tip[0]], ruled=True)
        hollow_loft = cq.Solid.makeLoft([h_root[0], h_tip[0]], ruled=True)
        for tag, s in (("outer", outer_loft), ("face_IML", face_loft),
                       ("core_IML", core_loft), ("hollow_IML (clipped tip)", hollow_loft)):
            lines.append(f"- loft {tag}: vol={s.Volume():.1f}, "
                         f"valid={BRepCheck_Analyzer(s.wrapped).IsValid()}")

        rings = {
            "face_outer_ring": fuzzy_cut(outer_loft, face_loft),
            "core_ring": fuzzy_cut(face_loft, core_loft),
            "face_inner_ring": fuzzy_cut(core_loft, hollow_loft),
        }
        total = 0.0
        for tag, shape in rings.items():
            kept, shards = filter_shards(shape)
            vol = sum(s.Volume() for s in kept)
            total += vol
            lines.append(f"- {tag}: {len(kept)} kept solid(s), {len(shards)} shard(s), vol={vol:.1f}")
        total += hollow_loft.Volume()
        lines.append(f"- conservation: rings+hollow = {total:.1f} vs outer_loft = {outer_loft.Volume():.1f} "
                     f"(delta {abs(total - outer_loft.Volume()):.2f})")

        lines.append(
            "- CONCLUSION: see per-line results above — the implementation may proceed with the "
            "full-value triple chain (face_mm, core_mm, face_mm) iff every wire family above came "
            "back as ONE valid closed wire and the clipped-tip loft/booleans are valid and conserve "
            "volume; the aft wall-merge on over-packed frozen configs is a documented consequence of "
            "the corrected 3-layer panel, to be revisited with ramped drop-offs (D11) / the P6 gate's "
            "IML audit."
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
