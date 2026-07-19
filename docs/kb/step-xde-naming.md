---
title: Plain STEP export drops all names — the XDE document path is required, and its flags are order-sensitive
tags: [occ, step, export, naming, f10, p09]
source: "backend/geometry/face_registry.py write_step_with_names/read_step_names; docs/r0_findings/p06_ext.md, p09.md"
phase: p09
confidence: verified
last_updated: 2026-07-19
---

A plain `cq.exporters.export(shape, path, exportType="STEP")` carries no
name metadata at all (F10, plan.md's own "fictional-API-shaped trap"
category — P9's R0 explicitly exists to catch this BEFORE construction
code is written). Names (body-level AND face-level sub-shape) only survive
through the OCP XDE document path:

```python
doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
top = shape_tool.AddShape(shape.wrapped, False)
TDataStd_Name.Set_s(top, TCollection_ExtendedString(body_name))
sub = shape_tool.AddSubShape(top, face.wrapped)   # raises/None if `face`
TDataStd_Name.Set_s(sub, TCollection_ExtendedString(face_name))  # isn't really a sub-shape of `top`

writer = STEPCAFControl_Writer()   # MUST exist BEFORE the flag registers
Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1)  # default OFF
writer.Perform(doc, path)          # NOT .Write() — .Write() transfers nothing
```

Non-obvious, R0-found gotchas (each one would silently produce a nameless
STEP if missed):
- `write.stepcaf.subshapes.name` / `read.stepcaf.subshapes.name` both
  default OFF and only register as valid `Interface_Static` params AFTER a
  `STEPCAFControl_Writer`/`Reader` has been constructed — setting them
  earlier is a silent no-op, not an error.
- `STEPCAFControl_Writer.Perform(doc, path)` is the real write call;
  `.Write()` exists but transfers nothing.
- Names read back via `TCollection_AsciiString(name_attr.Get()).ToCString()`
  — never plain `str()` on the OCP name object.
- Body COUNT on re-import (a separate P9 criterion from name survival) is
  `XCAFDoc_ShapeTool.GetFreeShapes(label_seq)` — cross-checked against the
  non-XDE `STEPControl_Reader.NbRootsForTransfer()`, same result on a
  3-body toy assembly (`probe_step_body_count.py`).
