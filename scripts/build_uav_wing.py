#!/usr/bin/env python3
"""Build the UAV Test Wing from YAML data and export STEP/STL.

Usage:
    python scripts/build_uav_wing.py

Outputs:
    artifacts/jobs/uav_test_wing/step/ — STEP file
    artifacts/jobs/uav_test_wing/stl/  — STL file
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cadquery as cq

# ── Add project root to path ────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.schema.models import (
    Config,
    Planform,
    Segment,
    Station,
    Airfoils,
    Skin,
    FaceSheet,
    Core,
    Spar,
    SparWeb,
    Tongue,
    Ribs,
    RibConstruction,
    LighteningHoles,
    Output,
)
from backend.geometry.multires import build_at_quality


def build_uav_wing() -> Path:
    """Build the UAV Test Wing and return the output directory."""

    # ── Configuration from YAML ───────────────────────────────────────────
    # span: 2.40m → 2400mm, half_span: 1.20m
    # Stations y: 0.00-1.20 → y_frac: 0.00-1.00 (divide by half_span 1.20)
    # Chords in meters → mm (multiply by 1000)

    config = Config(
        planform=Planform(
            span_mm=2400,
            segments=[
                Segment(name="root", y_end_frac=0.167, dihedral_deg=0, sweep_le_deg=0),
                Segment(name="inner", y_end_frac=0.5, dihedral_deg=3, sweep_le_deg=5),
                Segment(name="mid", y_end_frac=0.833, dihedral_deg=3, sweep_le_deg=5),
                Segment(name="tip", y_end_frac=1.0, dihedral_deg=3, sweep_le_deg=5),
            ],
            stations=[
                Station(y_frac=0.00, chord_mm=400, twist_deg=2.0, airfoil="naca2412"),
                Station(y_frac=0.167, chord_mm=363, twist_deg=1.8, airfoil="naca2412"),
                Station(y_frac=0.333, chord_mm=326, twist_deg=1.5, airfoil="naca2412"),
                Station(y_frac=0.50, chord_mm=289, twist_deg=1.5, airfoil="naca2412"),
                Station(y_frac=0.667, chord_mm=252, twist_deg=0.7, airfoil="naca2412"),
                Station(y_frac=0.833, chord_mm=215, twist_deg=0.3, airfoil="naca2412"),
                Station(y_frac=1.00, chord_mm=180, twist_deg=0.0, airfoil="naca2412"),
            ],
            twist_axis_xc=0.25,
            mirror=True,
        ),
        airfoils=Airfoils(
            sources=["naca4", "uiuc"],
            resample_points=199,
            te_min_thickness_mm=0.8,
        ),
        skin=Skin(
            face_sheet=FaceSheet(material="CFRP twill", plies=4),
            core=Core(material="rohacell_31", thickness_mm=2),
            ramp_ratio=3.0,
        ),
        spars=[
            Spar(
                name="main",
                xc_root=0.25,
                xc_tip=0.25,
                web=SparWeb(material="CFRP twill", plies=4),
                tongue=Tongue(
                    cross_section="rect_hollow",
                    engagement_mm=20,
                    clearance_mm=0.2,
                    wall_mm=2,
                ),
            ),
            Spar(
                name="rear",
                xc_root=0.70,
                xc_tip=0.70,
                web=SparWeb(material="CFRP twill", plies=3),
                tongue=Tongue(
                    cross_section="rect_hollow",
                    engagement_mm=20,
                    clearance_mm=0.2,
                    wall_mm=2,
                ),
            ),
        ],
        ribs=Ribs(
            count=9,
            construction=RibConstruction(material="CFRP twill", plies=3),
            lightening_holes=LighteningHoles(enabled=True, margin_mm=8),
        ),
        output=Output(formats=["step", "stl"]),
    )

    # ── Build geometry ────────────────────────────────────────────────────
    print("=" * 60)
    print("UAV Test Wing — Building 3D Geometry")
    print("=" * 60)
    print(f"  Span:        2400 mm")
    print(f"  Stations:    {len(config.planform.stations)}")
    print(f"  Airfoil:     {config.planform.stations[0].airfoil}")
    print(f"  Quality:     high (199-point airfoils)")
    print()

    t0 = time.perf_counter()
    result = build_at_quality(config, quality="high")
    elapsed = time.perf_counter() - t0

    # ── Metrics ───────────────────────────────────────────────────────────
    print("Build complete:")
    for k, v in result.metrics.items():
        if isinstance(v, (int, float)):
            print(f"  {k}: {v}")
    print()

    # ── Export ────────────────────────────────────────────────────────────
    output_dir = _PROJECT_ROOT / "artifacts" / "jobs" / "uav_test_wing"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export STEP
    step_path = output_dir / "uav_test_wing.step"
    result.solid.exportStep(str(step_path))
    print(f"  STEP: {step_path} ({Path(step_path).stat().st_size / 1024:.0f} KB)")

    # Export STL
    stl_path = output_dir / "uav_test_wing.stl"
    result.solid.exportStl(str(stl_path))
    print(f"  STL:  {stl_path} ({Path(stl_path).stat().st_size / 1024:.0f} KB)")

    # Save config as JSON for reference
    config_path = output_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config.model_dump(mode="json", exclude_none=True), f, indent=2)
    print(f"  Config: {config_path}")

    print()
    print(f"  Total time: {elapsed:.1f}s")
    print("=" * 60)

    return output_dir


if __name__ == "__main__":
    output_dir = build_uav_wing()
    print(f"\nWing files saved to: {output_dir}")
    print("Open the STEP file in your CAD viewer to inspect the 3D model.")
