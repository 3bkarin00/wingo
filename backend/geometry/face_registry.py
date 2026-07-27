"""Face-naming centroid registry (plan.md §8.8 "Face naming for FEA").

OCC booleans destroy face identity, so bond faces (π leg inner faces, base
undersides, tab sides, slot walls, hinge-carrier mating faces) cannot be
tracked by reference through construction. Instead:

1. AT CREATION TIME, construction code records (expected centroid, normal,
   area, target name) for every bond face — `FaceRegistry.record(...)` /
   `record_face(...)`.
2. AFTER ALL BOOLEANS on a body are done, `match(body)` iterates the body's
   final faces and matches each registry entry (centroid within
   FACE_REGISTRY_CENTROID_TOL_MM, |normal·normal| >=
   FACE_REGISTRY_NORMAL_DOT_MIN, area within FACE_REGISTRY_AREA_TOL_FRAC).
   An UNMATCHED ENTRY IS A HARD FAILURE (RuntimeError listing every miss) —
   a boolean ate a bond face, which is a real construction bug, never
   skipped silently.
3. `write_step_with_names(...)` exports bodies + matched faces through the
   XDE path R0-verified in docs/r0_findings/p06_ext.md
   (probe_xde_face_naming.py): AddShape/AddSubShape + TDataStd_Name, with
   `write.stepcaf.subshapes.name=1` set AFTER the writer is constructed
   (the Interface_Static param only registers once STEPCAF machinery
   loads — setting it earlier silently does nothing) and
   `STEPCAFControl_Writer.Perform(doc, path)` (Write() alone transfers
   nothing). `read_step_names(...)` is the matching read-side helper the
   gates use to assert survival (read.stepcaf.subshapes.name=1 +
   TCollection_AsciiString(...).ToCString(), never plain str()).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances


@dataclass
class RegistryEntry:
    name: str
    centroid: np.ndarray  # (3,)
    normal: np.ndarray    # (3,) unit
    area_mm2: float


@dataclass
class FaceRegistry:
    entries: list[RegistryEntry] = field(default_factory=list)

    def record(self, name: str, centroid, normal, area_mm2: float) -> None:
        n = np.asarray(normal, dtype=float)
        self.entries.append(RegistryEntry(
            name=name, centroid=np.asarray(centroid, dtype=float),
            normal=n / np.linalg.norm(n), area_mm2=float(area_mm2),
        ))

    def record_face(self, name: str, face: cq.Face) -> None:
        """Record an actual just-built cq.Face (most call sites)."""
        c = face.Center()
        n = face.normalAt()
        self.record(name, [c.x, c.y, c.z], [n.x, n.y, n.z], face.Area())

    def match(self, body: cq.Shape) -> dict[str, cq.Face]:
        """Match every entry against `body`'s final faces (module docstring
        step 2). Raises RuntimeError listing every unmatched entry."""
        faces = body.Faces()
        props = []
        for f in faces:
            c = f.Center()
            try:
                n = f.normalAt()
                nv = np.array([n.x, n.y, n.z])
                nv = nv / np.linalg.norm(nv)
            except Exception:  # noqa: BLE001 — degenerate face; can't be a bond face
                continue
            props.append((f, np.array([c.x, c.y, c.z]), nv, f.Area()))

        matched: dict[str, cq.Face] = {}
        missing: list[str] = []
        for e in self.entries:
            best = None
            for f, c, nv, a in props:
                if np.linalg.norm(c - e.centroid) > tolerances.FACE_REGISTRY_CENTROID_TOL_MM:
                    continue
                if abs(float(np.dot(nv, e.normal))) < tolerances.FACE_REGISTRY_NORMAL_DOT_MIN:
                    continue
                if abs(a - e.area_mm2) > tolerances.FACE_REGISTRY_AREA_TOL_FRAC * e.area_mm2:
                    continue
                d = np.linalg.norm(c - e.centroid)
                if best is None or d < best[0]:
                    best = (d, f)
            if best is None:
                missing.append(e.name)
            else:
                matched[e.name] = best[1]
        if missing:
            raise RuntimeError(
                "centroid registry: a boolean ate these bond face(s) — real construction "
                f"bug, never skipped: {missing}"
            )
        return matched


def write_step_with_names(
    bodies: list[tuple[str, cq.Shape, dict[str, cq.Face]]], path: str
) -> None:
    """STEP XDE export with body names AND face-level bond names (module
    docstring step 3). `bodies` = [(body_name, shape, {face_name: face})]."""
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for body_name, shape, face_names in bodies:
        top = shape_tool.AddShape(shape.wrapped, False)
        TDataStd_Name.Set_s(top, TCollection_ExtendedString(body_name))
        for face_name, face in face_names.items():
            sub = shape_tool.AddSubShape(top, face.wrapped)
            if sub.IsNull():
                raise RuntimeError(
                    f"XDE AddSubShape failed for '{face_name}' — face is not a sub-shape "
                    f"of body '{body_name}' (was it taken from a different shape instance?)"
                )
            TDataStd_Name.Set_s(sub, TCollection_ExtendedString(face_name))

    writer = STEPCAFControl_Writer()  # MUST exist before the flag registers (R0 finding)
    if not Interface_Static.SetIVal_s("write.stepcaf.subshapes.name", 1):
        raise RuntimeError("write.stepcaf.subshapes.name did not register — OCP build changed?")
    if not writer.Perform(doc, path):
        raise RuntimeError(f"STEPCAFControl_Writer.Perform failed for {path}")


def read_step_names(path: str) -> set[str]:
    """All names (body + face level) recoverable from a STEP file — the
    gates' round-trip assertion helper."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    reader = STEPCAFControl_Reader()
    Interface_Static.SetIVal_s("read.stepcaf.subshapes.name", 1)
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError(f"STEP re-read failed: {path}")
    reader.Transfer(doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    names: set[str] = set()

    def _collect(label) -> None:
        n = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), n):
            names.add(TCollection_AsciiString(n.Get()).ToCString())
        subs = TDF_LabelSequence()
        shape_tool.GetSubShapes_s(label, subs)
        for i in range(1, subs.Length() + 1):
            _collect(subs.Value(i))

    tops = TDF_LabelSequence()
    shape_tool.GetShapes(tops)
    for i in range(1, tops.Length() + 1):
        _collect(tops.Value(i))
    return names


def count_step_bodies(path: str) -> int:
    """Top-level (free, non-sub-shape) body count on STEP re-import — P9's
    own pass criterion ("body count identical", plan.md §9 P9), separate
    from read_step_names's name-survival check. R0-verified
    (docs/r0_findings/p09.md, probe_step_body_count.py):
    XCAFDoc_ShapeTool.GetFreeShapes matches the written body count exactly
    on a toy assembly (cross-checked against the non-XDE
    STEPControl_Reader.NbRootsForTransfer(), same result)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError(f"STEP re-read failed: {path}")
    reader.Transfer(doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free_labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free_labels)
    return free_labels.Length()
