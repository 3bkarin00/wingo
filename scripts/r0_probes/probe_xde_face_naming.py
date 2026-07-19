#!/usr/bin/env python3
"""R0 probe: does an OCP XDE (XCAFDoc) document preserve a NAME ATTACHED TO
AN INDIVIDUAL FACE (not just a top-level shape/solid) through a STEP
write/read round-trip?

Needed for the shared face-naming CENTROID REGISTRY (used by WP1 carriers,
WP2b π-joint bonds, WP2c tab/slot bonds) — the registry's whole point is
tagging individual bond FACES for FEA named-selection export (RIB<nn>_
SPAR<name>_TAB_BOND etc.), which only matters if those per-face names
actually survive STEP XDE round-tripping. P9's own R0 note (plan.md)
already flags XDE naming as "F10 — fictional-API-shaped trap" at the
whole-shape level; this probe specifically tests the FACE-level case, which
P9 never needed (P9 names bodies, not sub-faces).

Technique under test: `XCAFDoc_ShapeTool.AddSubShape(parent_label, face)`
to register a face as a named sub-shape of its parent solid's label, then
`TDataStd_Name.Set_s(face_label, name)` — write via STEPCAFControl_Writer,
re-read via STEPCAFControl_Reader, and check whether the sub-shape's name
is recoverable (walking sub-labels explicitly, not just top-level GetShapes,
since a name that only survives at the top level would NOT be useful for
per-face bond tagging).

Writes findings to docs/r0_findings/p06_ext.md.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FINDINGS = ROOT / "docs" / "r0_findings" / "p06_ext.md"


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("a") as f:
        f.write("\n".join(lines) + "\n\n")


def _collect_names(shape_tool, label, names: list[str]) -> None:
    from OCP.TCollection import TCollection_AsciiString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_LabelSequence

    n = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), n):
        # NOTE (found by this probe): plain str() on the returned
        # TCollection_ExtendedString gives the pybind object repr, not the
        # text — the content is only reachable via
        # TCollection_AsciiString(ext).ToCString(). A first run of this probe
        # used str() and wrongly concluded the name was lost.
        names.append(TCollection_AsciiString(n.Get()).ToCString())
    sub_labels = TDF_LabelSequence()
    shape_tool.GetSubShapes_s(label, sub_labels)
    for i in range(1, sub_labels.Length() + 1):
        _collect_names(shape_tool, sub_labels.Value(i), names)


def main() -> int:
    lines = ["## probe_xde_face_naming.py"]
    try:
        import cadquery as cq
        from OCP.TDocStd import TDocStd_Document
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.XCAFDoc import XCAFDoc_DocumentTool
        from OCP.TDataStd import TDataStd_Name
        from OCP.STEPCAFControl import STEPCAFControl_Writer, STEPCAFControl_Reader
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.Interface import Interface_Static
        from OCP.TDF import TDF_LabelSequence

        box = cq.Solid.makeBox(10, 10, 10)
        target_face = box.Faces()[0]
        target_name = "TEST_TAB_BOND_FACE"
        lines.append(f"- toy body: 10x10x10 box, naming face[0] as '{target_name}' via AddSubShape")

        doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        top_label = shape_tool.AddShape(box.wrapped, False)
        TDataStd_Name.Set_s(top_label, TCollection_ExtendedString("TEST_BODY"))

        face_label = shape_tool.AddSubShape(top_label, target_face.wrapped)
        face_ok = face_label is not None and not face_label.IsNull()
        lines.append(f"- `AddSubShape(top_label, face)` -> label {'created' if face_ok else 'NULL/FAILED'}")
        if face_ok:
            TDataStd_Name.Set_s(face_label, TCollection_ExtendedString(target_name))

        with tempfile.TemporaryDirectory() as tmp:
            step_path = str(Path(tmp) / "probe.step")
            # NOTE (found by this probe): `Write(path)` alone returns
            # IFSelect_RetVoid — nothing was transferred first. The correct
            # single call in this OCP version is `Perform(doc, path)`,
            # which transfers AND writes (returns bool, not an IFSelect enum).
            writer = STEPCAFControl_Writer()
            # NOTE (found by this probe): sub-shape names are DROPPED by the
            # writer unless `write.stepcaf.subshapes.name` is set to 1 — and
            # that Interface_Static param only REGISTERS after the first
            # STEPCAF writer/reader is instantiated (SetIVal on it before
            # that returns False and silently does nothing), so the writer
            # must be constructed BEFORE setting the flag.
            Interface_Static.SetCVal_s("write.step.schema", "AP214")
            sub_w = Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1)
            lines.append(f"- `write.stepcaf.subshapes.name=1` (set AFTER writer init — lazy param registration) -> {sub_w}")
            write_ok = writer.Perform(doc, step_path)
            lines.append(f"- `STEPCAFControl_Writer().Perform(doc, path)` -> {write_ok}")

            if not write_ok:
                lines.append("- CONCLUSION: STEP write failed outright — cannot test round-trip; "
                              "investigate the writer signature interactively before relying on this "
                              "path for the centroid registry's STEP export.")
            else:
                doc2 = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
                reader = STEPCAFControl_Reader()
                # Read-side twin flag — same lazy-registration caveat.
                sub_r = Interface_Static.SetIVal_s("read.stepcaf.subshapes.name", 1)
                lines.append(f"- `read.stepcaf.subshapes.name=1` -> {sub_r}")
                read_status = reader.ReadFile(step_path)
                if read_status != IFSelect_RetDone:
                    lines.append(f"- STEP re-read FAILED: status={read_status}")
                else:
                    reader.Transfer(doc2)
                    shape_tool2 = XCAFDoc_DocumentTool.ShapeTool_s(doc2.Main())
                    top_labels = TDF_LabelSequence()
                    shape_tool2.GetShapes(top_labels)
                    all_names: list[str] = []
                    for i in range(1, top_labels.Length() + 1):
                        _collect_names(shape_tool2, top_labels.Value(i), all_names)
                    survived = target_name in all_names
                    lines.append(f"- re-imported STEP: names found (top-level + sub-shape, recursive)="
                                 f"{all_names}")
                    lines.append(
                        f"- CONCLUSION: face-level sub-shape name "
                        f"{'SURVIVED the STEP XDE round-trip. Full working recipe: AddSubShape + TDataStd_Name, PLUS write.stepcaf.subshapes.name=1 (set after writer init) on write AND read.stepcaf.subshapes.name=1 on read — both flags default OFF, and without the write flag the name never even reaches the STEP file. Names read back via TCollection_AsciiString(name.Get()).ToCString(), never plain str(). This is the technique the WP1/WP2b/WP2c centroid-registry STEP export must use.' if survived else 'DID NOT survive — AddSubShape + TDataStd_Name is not sufficient in this OCP build; needs a different technique before WP1/WP2b/WP2c centroid-registry naming code is written, do not assume it works'}"
                    )

    except Exception as exc:  # noqa: BLE001
        import traceback
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")
        lines.append("```\n" + traceback.format_exc() + "```")
        lines.append("- CONCLUSION: XDE face-level naming API in this OCP build needs interactive "
                      "exploration (`python3 -c` against the real install) before the centroid-registry "
                      "module's STEP export path is implemented — do NOT guess the signature in "
                      "construction code.")
        _append(lines)
        print("\n".join(lines))
        return 1

    _append(lines)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
