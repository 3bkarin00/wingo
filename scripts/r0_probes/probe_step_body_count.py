#!/usr/bin/env python3
"""R0 probe: how to recover TOP-LEVEL BODY COUNT from a re-imported STEP
file, for P9's own pass criterion ("exported STEP re-imported into OCC:
body count identical" — plan.md §9 P9) on top of the already-verified
name-survival recipe (face_registry.py, docs/r0_findings/p06_ext.md).

Checks two independent APIs on a toy 3-body assembly written via
face_registry.write_step_with_names:
  - XDE: XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()).GetFreeShapes(labels)
    -> label count, read back through STEPCAFControl_Reader (the SAME
    reader read_step_names already uses).
  - Plain: STEPControl_Reader.NbRootsForTransfer() (no XDE at all) as a
    simpler, independent cross-check.

Writes findings to docs/r0_findings/p09.md (appended under its own
heading, same file the export-API probe already wrote to).
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
    lines = ["## probe_step_body_count.py (P9 — body count on STEP re-import)"]
    try:
        import tempfile

        import cadquery as cq

        from backend.geometry.face_registry import write_step_with_names

        bodies = [
            (f"TEST_BODY_{i}", cq.Solid.makeBox(10, 10, 10, cq.Vector(i * 20, 0, 0)), {})
            for i in range(3)
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "probe.step")
            write_step_with_names(bodies, path)

            # --- XDE: GetFreeShapes -----------------------------------------
            try:
                from OCP.STEPCAFControl import STEPCAFControl_Reader
                from OCP.TCollection import TCollection_ExtendedString
                from OCP.TDF import TDF_LabelSequence
                from OCP.TDocStd import TDocStd_Document
                from OCP.XCAFDoc import XCAFDoc_DocumentTool

                doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
                reader = STEPCAFControl_Reader()
                reader.SetColorMode(False)
                reader.SetNameMode(True)
                status = reader.ReadFile(path)
                transfer_ok = reader.Transfer(doc) if status == 1 else False
                shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
                free_labels = TDF_LabelSequence()
                shape_tool.GetFreeShapes(free_labels)
                xde_count = free_labels.Length()
                lines.append(
                    f"- XDE GetFreeShapes: ReadFile status={status}, Transfer={transfer_ok}, "
                    f"free_labels.Length()={xde_count} (expected {len(bodies)})"
                )
            except Exception as exc:  # noqa: BLE001
                import traceback
                lines.append(f"- XDE GetFreeShapes FAILED: {type(exc).__name__}: {exc}")
                lines.append("```\n" + traceback.format_exc() + "```")
                xde_count = None

            # --- Plain STEPControl_Reader ------------------------------------
            try:
                from OCP.STEPControl import STEPControl_Reader

                plain_reader = STEPControl_Reader()
                plain_status = plain_reader.ReadFile(path)
                n_roots = plain_reader.NbRootsForTransfer()
                plain_reader.TransferRoots()
                n_shapes = plain_reader.NbShapes()
                lines.append(
                    f"- Plain STEPControl_Reader: ReadFile status={plain_status}, "
                    f"NbRootsForTransfer()={n_roots}, NbShapes() after TransferRoots()={n_shapes} "
                    f"(expected {len(bodies)} roots)"
                )
            except Exception as exc:  # noqa: BLE001
                import traceback
                lines.append(f"- Plain STEPControl_Reader FAILED: {type(exc).__name__}: {exc}")
                lines.append("```\n" + traceback.format_exc() + "```")
                n_roots = None

        lines.append(
            f"- CONCLUSION: body count via "
            f"{'XDE GetFreeShapes (confirmed, count=' + str(xde_count) + ')' if xde_count == len(bodies) else 'XDE GetFreeShapes MISMATCH or failed'}"
            f"; plain STEPControl_Reader.NbRootsForTransfer() "
            f"{'confirmed, count=' + str(n_roots) if n_roots == len(bodies) else 'MISMATCH or failed'}."
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
