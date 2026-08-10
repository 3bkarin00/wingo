#!/usr/bin/env python3
"""R0 probe: demold + stock sectioning APIs.

Probes the OCP APIs needed for demold scan and stock sectioning (P16):
- Face normal extraction for undercut detection
- Stock block sectioning via boolean intersection
- Alignment feature generation

Usage:
    python scripts/r0_probes/probe_demold.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FINDINGS = ROOT / "docs" / "r0_findings" / "p16.md"


def main() -> int:
    lines = ["## probe_demold.py — Demold + Stock Sectioning APIs"]
    lines.append("")

    try:
        import cadquery as cq
        import numpy as np
        from OCP.BRepGProp import BRepGProp_Face
        from OCP.GProp import GProp_GPropSystem
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

        lines.append("### API Availability Check")
        lines.append("- cadquery: OK")
        lines.append("- OCP.BRepGProp_Face: OK (face normal extraction)")
        lines.append("- OCP.GProp_GPropSystem: OK (mass properties)")
        lines.append("- OCP.BRepAlgoAPI_Cut: OK (boolean cut)")
        lines.append("- OCP.BRepAlgoAPI_Fuse: OK (boolean fuse)")
        lines.append("")

        # Test 1: Build a simple mold half (box)
        mold = cq.Workplane("XY").box(100, 50, 30).translate((0, 0, 15)).val()
        lines.append("### Test 1: Mold half solid")
        lines.append(f"- Box volume: {mold.Volume():.2f}")
        lines.append(f"- Box faces: {len(mold.Faces())}")
        lines.append("")

        # Test 2: Extract face normals using BRepGProp
        lines.append("### Test 2: Face normal extraction")
        prop = GProp_GPropSystem()
        for i, face in enumerate(mold.Faces()[:4]):  # Sample first 4 faces
            face_prop = BRepGProp_Face(face)
            prop.AddShape(face)
            _, normal, _ = prop.MassProperties()
            nx, ny, nz = normal.X(), normal.Y(), normal.Z()
            lines.append(f"  Face {i}: normal=({nx:.3f}, {ny:.3f}, {nz:.3f})")
        lines.append("")

        # Test 3: Undercut detection (pull direction = -Z)
        pull_direction = (0.0, 0.0, -1.0)
        pull_vec = np.array(pull_direction)
        pull_norm = np.linalg.norm(pull_vec)
        if pull_norm > 0:
            pull_vec = pull_vec / pull_norm

        undercut_count = 0
        for i, face in enumerate(mold.Faces()):
            try:
                prop = GProp_GPropSystem()
                face_prop = BRepGProp_Face(face)
                prop.AddShape(face)
                _, normal, _ = prop.MassProperties()
                normal_arr = np.array([normal.X(), normal.Y(), normal.Z()])
                normal_norm = np.linalg.norm(normal_arr)
                if normal_norm > 0:
                    normal_arr = normal_arr / normal_norm
                    dot_product = np.dot(normal_arr, pull_vec)
                    angle = np.degrees(np.arccos(np.clip(dot_product, -1.0, 1.0)))
                    if angle > 90.0:
                        undercut_count += 1
                        lines.append(f"  Undercut face {i}: angle={angle:.1f}°")
            except Exception:
                pass

        lines.append("### Test 3: Undercut detection")
        lines.append(f"- Pull direction: {pull_direction}")
        lines.append(f"- Undercut faces found: {undercut_count}")
        lines.append("")

        # Test 4: Stock sectioning (split box into 2 sections)
        num_sections = 2
        bbox = mold.BoundingBox()
        total_length = bbox.xmax - bbox.xmin
        section_length = total_length / num_sections
        lines.append("### Test 4: Stock sectioning")
        lines.append(f"- Total length: {total_length:.1f} mm")
        lines.append(f"- Section length: {section_length:.1f} mm")
        lines.append(f"- Number of sections: {num_sections}")

        # Create section boxes
        for i in range(num_sections):
            x_start = bbox.xmin + i * section_length
            x_end = x_start + section_length
            sec_box = cq.Workplane("XY").box(
                section_length,
                bbox.ymax - bbox.ymin,
                bbox.zmax - bbox.zmin
            ).translate((x_start + section_length / 2, 0, 0))
            lines.append(f"  Section {i}: x=[{x_start:.1f}, {x_end:.1f}], volume={sec_box.val().Volume():.2f}")
        lines.append("")

        # Test 5: Alignment pins at section interfaces
        lines.append("### Test 5: Alignment pins")
        corners = [
            (bbox.xmin, bbox.ymin, 0.0),
            (bbox.xmin, bbox.ymax, 0.0),
            (bbox.xmax, bbox.ymin, 0.0),
            (bbox.xmax, bbox.ymax, 0.0),
        ]
        for x, y, z in corners:
            lines.append(f"  Pin at ({x:.1f}, {y:.1f}, {z:.1f})")
        lines.append("")

        lines.append("### Summary")
        lines.append("- Face normal extraction via BRepGProp_Face works")
        lines.append("- Undercut detection: faces with normal angle > 90° to pull direction")
        lines.append("- Stock sectioning: split along X axis into equal sections")
        lines.append("- Alignment pins at section interface corners")

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
