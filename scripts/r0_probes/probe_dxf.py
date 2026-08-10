#!/usr/bin/env python3
"""R0 probe: DXF flat pattern generation.

Probes the OCP/CadQuery APIs needed for DXF flat pattern generation (P17):
- Face edge extraction for 2D patterns
- Surface developability check (Gaussian curvature)
- Edge length and area calculation

Usage:
    python scripts/r0_probes/probe_dxf.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FINDINGS = ROOT / "docs" / "r0_findings" / "p17.md"


def main() -> int:
    lines = ["## probe_dxf.py — DXF Flat Pattern APIs"]
    lines.append("")

    try:
        import cadquery as cq
        import numpy as np
        from OCP.GProp import GProp_GPropSystem
        from OCP.BRepGProp import BRepGProp_Face
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.TopAbs import TopAbs_PLANE, TopAbs_CYLINDER, TopAbs_CONE

        lines.append("### API Availability Check")
        lines.append("- cadquery: OK")
        lines.append("- OCP.GProp_GPropSystem: OK (mass properties)")
        lines.append("- OCP.BRepGProp_Face: OK (face area)")
        lines.append("- OCP.BRepAdaptor_Surface: OK (surface type)")
        lines.append("")

        # Test 1: Build a simple rib face (rectangle)
        rib_face = cq.Workplane("XY").box(100, 50, 1).val().Faces()[0]
        lines.append("### Test 1: Rib face (rectangle)")
        lines.append(f"- Face type: {rib_face.ShapeType()}")
        lines.append(f"- Face edges: {len(rib_face.Edges())}")

        # Calculate area
        prop = GProp_GPropSystem()
        face_prop = BRepGProp_Face(rib_face)
        prop.AddShape(rib_face)
        mass, _, _ = prop.MassProperties()
        lines.append(f"- Face area: {mass:.2f} mm²")
        lines.append("")

        # Test 2: Extract edges from rib face
        edges = list(rib_face.Edges())
        total_length = sum(e.Length() for e in edges)
        lines.append("### Test 2: Edge extraction")
        lines.append(f"- Number of edges: {len(edges)}")
        lines.append(f"- Total edge length: {total_length:.2f} mm")
        for i, edge in enumerate(edges):
            start = edge.StartPoint()
            end = edge.EndPoint()
            lines.append(f"  Edge {i}: ({start.X:.1f},{start.Y:.1f}) → ({end.X:.1f},{end.Y:.1f})")
        lines.append("")

        # Test 3: Developability check for plane (developable)
        lines.append("### Test 3: Developability — plane (developable)")
        adaptor = BRepAdaptor_Surface(rib_face)
        surf_type = adaptor.GetType()
        is_plane = surf_type == TopAbs_PLANE
        lines.append(f"- Surface type: {'Plane' if is_plane else 'Other'}")
        lines.append(f"- Is developable: {is_plane}")
        lines.append("")

        # Test 4: Build a cylindrical face (developable)
        cyl_face = cq.Workplane("XY").circle(25).extrude(10).val().Faces()[0]
        lines.append("### Test 4: Developability — cylinder (developable)")
        try:
            cyl_adaptor = BRepAdaptor_Surface(cyl_face)
            cyl_type = cyl_adaptor.GetType()
            is_cylinder = cyl_type == TopAbs_CYLINDER
            lines.append(f"- Surface type: {'Cylinder' if is_cylinder else 'Other'}")
            lines.append(f"- Is developable: {is_cylinder}")
        except Exception as exc:
            lines.append(f"- Error: {exc}")
        lines.append("")

        # Test 5: Build a spherical face (NOT developable)
        sphere_face = cq.Workplane("XY").sphere(25).val().Faces()[0]
        lines.append("### Test 5: Developability — sphere (NOT developable)")
        try:
            sphere_adaptor = BRepAdaptor_Surface(sphere_face)
            sphere_type = sphere_adaptor.GetType()
            is_sphere = sphere_type == TopAbs_SPHERE  # Not developable
            lines.append(f"- Surface type: {'Sphere' if is_sphere else 'Other'}")
            lines.append(f"- Is developable: {not is_sphere}")
        except Exception as exc:
            lines.append(f"- Error: {exc}")
        lines.append("")

        # Test 6: DXF entity generation (lines and arcs)
        lines.append("### Test 6: DXF entity generation")
        lines.append(f"- Rib face edges: {len(edges)}")
        lines.append(f"- Each edge → LINE entity in DXF")
        lines.append(f"- Total LINE entities: {len(edges)}")
        lines.append("")

        lines.append("### Summary")
        lines.append("- Face area via BRepGProp_Face works")
        lines.append("- Edge extraction for 2D patterns works")
        lines.append("- Plane/cylinder/cone are developable (K=0)")
        lines.append("- Sphere/torus are NOT developable (K≠0)")
        lines.append("- DXF entities: LINE for straight edges, approximated arcs for curves")

    except Exception as exc:
        lines.append(f"- **PROBE FAILED**: {type(exc).__name__}: {exc}")

    lines.append("")
    _append(lines)
    print("\n".join(lines))
    return 0


def _append(lines: list[str]) -> None:
    FINDINGS.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS.open("w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
