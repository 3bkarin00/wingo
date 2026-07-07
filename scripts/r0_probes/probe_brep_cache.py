"""R0 probe: BRep export/import round-trip, for the P4 geometry build cache
(docs/known_issues.md / test architecture decision, see changelog.md).

The cache needs to serialize raw boolean-output shapes (potentially
multi-solid Compounds, pre-shard-filter) to disk and reload them bit-for-bit
equivalent (same volumes, same solid count, same watertightness) so that
`filter_shards` and every downstream assertion runs identically whether the
shape was just built or just loaded. Never assume the API — verify against
the real installed cadquery/OCP.
"""
import cadquery as cq
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Compound
from OCP.BRep import BRep_Builder


def round_trip_via_cq_shape_methods(shape: cq.Shape, path: str) -> cq.Shape | None:
    """Try cadquery's own Shape.exportBrep/importBrep convenience wrappers,
    if this installed version has them."""
    if not (hasattr(shape, "exportBrep") and hasattr(cq.Shape, "importBrep")):
        return None
    shape.exportBrep(path)
    return cq.Shape.importBrep(path)


def round_trip_via_raw_occp(shape: cq.Shape, path: str) -> cq.Shape:
    """Raw OCP BRepTools.Write_s / Read_s, the underlying OCC serialization
    call cadquery's own exportBrep/importBrep wrap (fallback if this
    cadquery version lacks the convenience methods, or to cross-check)."""
    ok = BRepTools.Write_s(shape.wrapped, path)
    assert ok is None or ok is True, f"BRepTools.Write_s returned {ok!r}"

    new_shape = TopoDS_Compound()
    builder = BRep_Builder()
    ok = BRepTools.Read_s(new_shape, path, builder)
    assert ok is True, f"BRepTools.Read_s returned {ok!r}"
    return cq.Shape.cast(new_shape)


def main():
    print(f"cadquery version: {cq.__version__}")
    print(f"cq.Shape has exportBrep: {hasattr(cq.Shape, 'exportBrep')}")
    print(f"cq.Shape has importBrep: {hasattr(cq.Shape, 'importBrep')}")

    # --- Single solid round-trip ---
    box = cq.Workplane("XY").box(10, 20, 30).val()
    assert isinstance(box, cq.Shape)
    print(f"\noriginal box: vol={box.Volume():.4f} solids={len(box.Solids())}")

    path = "/tmp/r0_probe_box.brep"
    loaded = round_trip_via_cq_shape_methods(box, path)
    method = "cq.Shape.exportBrep/importBrep"
    if loaded is None:
        loaded = round_trip_via_raw_occp(box, path)
        method = "OCP.BRepTools.Write_s/Read_s"
    print(f"round-trip method used: {method}")
    print(f"loaded box: vol={loaded.Volume():.4f} solids={len(loaded.Solids())}")
    assert abs(loaded.Volume() - box.Volume()) < 1e-6, "volume mismatch after round-trip"
    assert len(loaded.Solids()) == 1
    print("CONCLUSION (single solid): round-trip preserves volume exactly, solid count 1->1.")

    # --- Multi-solid compound round-trip (shard scenario: 2 disjoint solids) ---
    box_a = cq.Workplane("XY").box(10, 10, 10).val()
    box_b = cq.Workplane("XY").transformed(offset=cq.Vector(1000, 0, 0)).box(0.5, 0.5, 0.5).val()
    compound = cq.Compound.makeCompound([box_a, box_b])
    print(f"\noriginal compound: vol={compound.Volume():.4f} solids={len(compound.Solids())}")

    path2 = "/tmp/r0_probe_compound.brep"
    if method == "cq.Shape.exportBrep/importBrep":
        compound.exportBrep(path2)
        loaded2 = cq.Shape.importBrep(path2)
    else:
        loaded2 = round_trip_via_raw_occp(compound, path2)
    solids2 = loaded2.Solids()
    print(f"loaded compound: vol={loaded2.Volume():.4f} solids={len(solids2)}")
    assert len(solids2) == 2, f"expected 2 solids after round-trip, got {len(solids2)}"
    vols = sorted(s.Volume() for s in solids2)
    assert abs(vols[0] - 0.125) < 1e-6 and abs(vols[1] - 1000.0) < 1e-6, f"shard volumes wrong: {vols}"
    print("CONCLUSION (multi-solid compound): round-trip preserves both solids' volumes and count exactly —"
          " safe to cache pre-shard-filter raw boolean output and re-run filter_shards fresh on load.")


if __name__ == "__main__":
    main()
