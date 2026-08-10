#!/usr/bin/env python3
"""P20 R0 probe — wing shape validation API exploration.

Explores OCP/CQ APIs for:
1. Bounding box extraction
2. Face area/normal checks
3. Symmetry verification (left/right)
4. Cross-section chord/thickness measurement
5. Volume bounds validation
"""
import math
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import yaml
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp, BRepGProp_Face
from OCP.gp import gp_Pnt, gp_Vec

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.geometry.loft import build_oml
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config
from backend import tolerances

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


def test_bounding_box():
    """Test Bnd_Box / BRepBndLib for wing bounding box."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    # Method 1: BRepBndLib
    bnd = Bnd_Box()
    BRepBndLib.Add_s(solid.wrapped, bnd)
    x_min, y_min, z_min, x_max, y_max, z_max = bnd.Get()
    print(f"[BRepBndLib] BB: ({x_min:.1f}, {y_min:.1f}, {z_min:.1f}) to ({x_max:.1f}, {y_max:.1f}, {z_max:.1f})")
    print(f"[BRepBndLib] Span: {y_max - y_min:.1f} mm, Chord: {x_max - x_min:.1f} mm, Thickness: {z_max - z_min:.1f} mm")

    # Method 2: CQ bbox (wrapper)
    bbox = solid.BoundingBox()
    print(f"[CQ bbox] BB: ({bbox.xmin:.1f}, {bbox.ymin:.1f}, {bbox.zmin:.1f}) to ({bbox.xmax:.1f}, {bbox.ymax:.1f}, {bbox.zmax:.1f})")

    return (x_min, y_min, z_min, x_max, y_max, z_max)


def test_face_areas():
    """Test face area extraction via BRepGProp_Face + GProp_GProps."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    areas = []
    for face in solid.Faces():
        sys_prop = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, sys_prop)
        area = sys_prop.Mass()
        areas.append(area)

    print(f"[Face areas] Count: {len(areas)}, Min: {min(areas):.1f}, Max: {max(areas):.1f}, Mean: {np.mean(areas):.1f}")
    degenerate = [a for a in areas if a < 1.0]
    print(f"[Face areas] Degenerate (<1 mm²): {len(degenerate)}")

    return areas


def test_face_normals():
    """Test normal extraction from faces."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    # Sample normals at center of each face
    normals = []
    for face in solid.Faces():
        prop = BRepGProp_Face(face.wrapped)
        u_min, u_max, v_min, v_max = prop.Bounds()
        # Get normal at center
        pnt = gp_Pnt()
        vec = gp_Vec()
        prop.Normal(0.5 * (u_min + u_max), 0.5 * (v_min + v_max), pnt, vec)
        norm = math.sqrt(vec.X()*vec.X() + vec.Y()*vec.Y() + vec.Z()*vec.Z())
        if norm > 0:
            normals.append((vec.X()/norm, vec.Y()/norm, vec.Z()/norm))

    print(f"[Normals] Count: {len(normals)}")
    if normals:
        print(f"[Normals] Sample: {normals[0]}")

    return normals


def test_symmetry_check():
    """Test left/right symmetry for mirrored wings."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    if not config.planform.mirror:
        print("[Symmetry] Config not mirrored, skipping")
        return

    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    # Get all vertices
    vertices = []
    for vert in solid.Vertices():
        vertices.append(np.array([vert.X, vert.Y, vert.Z]))

    if not vertices:
        print("[Symmetry] No vertices found")
        return

    vertices = np.array(vertices)
    half_span = config.planform.span_mm / 2.0

    # Split into left (Y < 0) and right (Y > 0) halves
    left = vertices[vertices[:, 1] < -1.0]  # small margin at root
    right = vertices[vertices[:, 1] > 1.0]

    print(f"[Symmetry] Left vertices: {len(left)}, Right vertices: {len(right)}")

    if len(left) > 0 and len(right) > 0:
        # Reflect left to match right
        left_reflected = left.copy()
        left_reflected[:, 1] = -left_reflected[:, 1]

        # Compute pairwise distances (nearest neighbor)
        max_dist = 0.0
        for pt in right:
            dists = np.linalg.norm(left_reflected - pt, axis=1)
            max_dist = max(max_dist, dists.min())

        print(f"[Symmetry] Max nearest-neighbor distance: {max_dist:.3f} mm")
        print(f"[Symmetry] Tolerance: {tolerances.KERNEL_TOLERANCE_MM:.3f} mm")

    return max_dist


def test_cross_section_chord():
    """Test chord measurement at a given Y station."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    # Get a section's points
    for section in sections[:3]:
        # Chord = max(X) - min(X) at this Y
        x_min = section.points[:, 0].min()
        x_max = section.points[:, 0].max()
        chord_measured = x_max - x_min
        print(f"[Chord] y={section.y_mm:.1f} mm: measured={chord_measured:.1f} mm, declared={section.chord_mm:.1f} mm")

    return True


def test_volume_bounds():
    """Test volume bounds validation."""
    cfg_path = sorted(GOLDEN_DIR.glob("*.yaml"))[0]
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    vol = solid.Volume()
    print(f"[Volume] {vol:.0f} mm³ = {vol/1e6:.2f} cm³")

    # Estimate bounds: span * mean_chord * mean_thickness
    half_span = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    mean_chord = np.mean([s.chord_mm for s in sections])
    mean_thickness = config.skin.core.thickness_mm + 2 * config.skin.face_sheet.plies * 0.05  # rough estimate
    est_vol = 2 * half_span * mean_chord * mean_thickness  # *2 for mirror
    print(f"[Volume] Estimate: {est_vol:.0f} mm³")
    print(f"[Volume] Ratio: {vol / est_vol:.2f}")

    return vol, est_vol


if __name__ == "__main__":
    print("=" * 60)
    print("P20 R0 Probe — Wing Shape Validation")
    print("=" * 60)

    print("\n--- Bounding Box ---")
    test_bounding_box()

    print("\n--- Face Areas ---")
    test_face_areas()

    print("\n--- Face Normals ---")
    test_face_normals()

    print("\n--- Symmetry Check ---")
    test_symmetry_check()

    print("\n--- Cross-Section Chord ---")
    test_cross_section_chord()

    print("\n--- Volume Bounds ---")
    test_volume_bounds()

    print("\n" + "=" * 60)
    print("R0 probe complete")
    print("=" * 60)
