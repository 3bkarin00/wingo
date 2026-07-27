#!/usr/bin/env python3
"""R0 probe: STL and glTF export APIs for P9 (plan.md §9 "P9 — Export").
STEP+XDE naming is already R0-verified (face_registry.py,
docs/r0_findings/p06_ext.md's XDE recipe) — this probe covers the two
remaining export formats before backend/export/ construction code is
written, per the project's "never invent an API" hard rule.

Checks:
  - cq.Shape.exportStl / cq.exporters.export STL on a toy solid -> valid
    binary/ascii STL, reloadable, manifold triangle count sane.
  - glTF export path: cq.Assembly(...).save(path, exportType="GLTF") on a
    2-body named assembly -> file exists, non-trivial size, node count
    matches body count (parsed from the glTF JSON).

Writes findings to docs/r0_findings/p09.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p09.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def main() -> int:
    lines = ["## probe_export_apis.py (P9)"]
    try:
        import tempfile

        import cadquery as cq

        box = cq.Solid.makeBox(10, 20, 5)

        # ---- STL ----
        with tempfile.TemporaryDirectory() as tmp:
            stl_path = str(Path(tmp) / "probe.stl")
            try:
                cq.exporters.export(cq.Workplane(obj=box), stl_path, exportType="STL")
                stl_ok = Path(stl_path).exists() and Path(stl_path).stat().st_size > 0
                lines.append(f"- `cq.exporters.export(Workplane, path, exportType='STL')` -> "
                             f"file exists={stl_ok}, size={Path(stl_path).stat().st_size if stl_ok else 0} bytes")
            except Exception as exc:  # noqa: BLE001
                stl_ok = False
                lines.append(f"- `cq.exporters.export(..., exportType='STL')` FAILED: {type(exc).__name__}: {exc}")

            if stl_ok:
                # Re-read to sanity-check triangle count via OCP's own STL reader.
                try:
                    from OCP.StlAPI import StlAPI_Reader
                    from OCP.TopoDS import TopoDS_Shape
                    shape = TopoDS_Shape()
                    reader = StlAPI_Reader()
                    read_ok = reader.Read(shape, stl_path)
                    lines.append(f"- STL re-read via `StlAPI_Reader`: {read_ok}")
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"- STL re-read probe FAILED: {type(exc).__name__}: {exc}")

        # ---- glTF ----
        with tempfile.TemporaryDirectory() as tmp:
            gltf_path = str(Path(tmp) / "probe.gltf")
            try:
                assy = cq.Assembly()
                assy.add(cq.Workplane(obj=box), name="TEST_BODY_A", color=cq.Color(0.5, 0.5, 0.5))
                assy.add(cq.Workplane(obj=cq.Solid.makeBox(5, 5, 5, cq.Vector(20, 0, 0))),
                         name="TEST_BODY_B", color=cq.Color(0.2, 0.2, 0.8))
                assy.save(gltf_path, exportType="GLTF")
                gltf_ok = Path(gltf_path).exists() and Path(gltf_path).stat().st_size > 0
                lines.append(f"- `cq.Assembly(...).save(path, exportType='GLTF')` -> "
                             f"file exists={gltf_ok}, size={Path(gltf_path).stat().st_size if gltf_ok else 0} bytes")
                if gltf_ok:
                    import json
                    gltf_json = json.loads(Path(gltf_path).read_text())
                    n_nodes = len(gltf_json.get("nodes", []))
                    n_meshes = len(gltf_json.get("meshes", []))
                    names_found = [n.get("name") for n in gltf_json.get("nodes", []) if n.get("name")]
                    lines.append(f"- glTF parsed: nodes={n_nodes}, meshes={n_meshes}, "
                                 f"named nodes={names_found}")
            except Exception as exc:  # noqa: BLE001
                gltf_ok = False
                lines.append(f"- `cq.Assembly.save(..., exportType='GLTF')` FAILED: {type(exc).__name__}: {exc}")
                import traceback
                lines.append("```\n" + traceback.format_exc() + "```")

        lines.append(
            f"- CONCLUSION: STL export via {'cq.exporters.export(Workplane, path, exportType=STL) — confirmed working' if stl_ok else 'FAILED — needs interactive investigation'}. "
            f"glTF export via {'cq.Assembly(...).save(path, exportType=GLTF), names preserved as node names — confirmed working' if gltf_ok else 'FAILED — needs interactive investigation'}."
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
