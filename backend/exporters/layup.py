"""Layup schedule exporter — CSV + JSON.

Generates composite layup schedule files from the wing configuration:
- CSV: human-readable layer stack per body
- JSON: machine-readable with material properties

P13 pass criteria:
- CSV contains all layers with angle, thickness, material
- JSON matches CSV structure with additional metadata
- Layer counts match skin configuration
- Total thickness = sum(plies × ply_thickness) + core_thickness

Usage:
    from backend.exporters.layup import (
        LayupExporter,
        export_layup_csv,
        export_layup_json,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.schema.models import Config


@dataclass
class Ply:
    """A single composite ply."""
    layer_num: int
    angle_deg: float
    material: str
    thickness_mm: float
    body_name: str


@dataclass
class LayupSchedule:
    """Complete layup schedule for all bodies."""
    plies: list[Ply] = field(default_factory=list)
    bodies: list[str] = field(default_factory=list)
    total_thickness_mm: float = 0.0


class LayupExporter:
    """Facade for layup export operations.

    Provides a class-based API for building and exporting layup schedules.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def build_schedule(self) -> LayupSchedule:
        return build_layup_schedule(self.config)

    def export(self, output_dir: str | Path) -> LayupExportResult:
        return export_layup(self.config, output_dir)


@dataclass
class LayupExportResult:
    """Result of exporting layup schedule."""
    csv_path: Path | None = None
    json_path: Path | None = None
    ply_count: int = 0
    body_count: int = 0
    errors: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return len(self.errors) == 0


def _get_ply_thickness(material: str) -> float:
    """Get ply thickness for a material (from provisional lookup).

    In production, this reads from the materials DB. For now, uses
    the provisional values from tolerances.py.
    """
    from backend.tolerances import PLY_THICKNESS_MM_PROVISIONAL
    return PLY_THICKNESS_MM_PROVISIONAL.get(material, 0.20)


def build_layup_schedule(config: Config) -> LayupSchedule:
    """Build the complete layup schedule from the wing configuration.

    Args:
        config: the input Config.

    Returns:
        LayupSchedule with all plies organized by body.
    """
    schedule = LayupSchedule()

    # Skin layup (face sheets + core)
    skin = config.skin
    face_sheet = skin.face_sheet
    core = skin.core

    # Face sheet plies (top and bottom)
    for side in ["top", "bottom"]:
        for i in range(face_sheet.plies):
            schedule.plies.append(Ply(
                layer_num=len(schedule.plies) + 1,
                angle_deg=0.0,  # quasi-isotropic default
                material=face_sheet.material,
                thickness_mm=_get_ply_thickness(face_sheet.material),
                body_name=f"BODY-{side}-SKIN",
            ))

    # Core layer
    schedule.plies.append(Ply(
        layer_num=len(schedule.plies) + 1,
        angle_deg=0.0,
        material=core.material,
        thickness_mm=core.thickness_mm,
        body_name="BODY-CORE",
    ))

    # Spar layup
    for spar in config.spars:
        web = spar.web
        for i in range(web.plies):
            schedule.plies.append(Ply(
                layer_num=len(schedule.plies) + 1,
                angle_deg=0.0,
                material=web.material,
                thickness_mm=_get_ply_thickness(web.material),
                body_name=f"BODY-{spar.name}-SPAR",
            ))

    # Rib layup
    rib = config.ribs
    for i in range(rib.construction.plies):
        schedule.plies.append(Ply(
            layer_num=len(schedule.plies) + 1,
            angle_deg=0.0,
            material=rib.construction.material,
            thickness_mm=_get_ply_thickness(rib.construction.material),
            body_name="BODY-RIBS",
        ))

    # Collect unique body names
    schedule.bodies = sorted(set(p.body_name for p in schedule.plies))

    # Total thickness (skin + core)
    face_total = face_sheet.plies * _get_ply_thickness(face_sheet.material)
    schedule.total_thickness_mm = face_total + core.thickness_mm

    return schedule


def export_layup_csv(
    schedule: LayupSchedule,
    output_path: str | Path,
) -> Path:
    """Export layup schedule to CSV.

    Columns: body_name, layer_num, angle_deg, material, thickness_mm
    """
    output_path = Path(output_path)

    lines = [
        "body_name,layer_num,angle_deg,material,thickness_mm",
    ]

    for ply in schedule.plies:
        lines.append(
            f"{ply.body_name},{ply.layer_num},{ply.angle_deg},"
            f"{ply.material},{ply.thickness_mm}"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def export_layup_json(
    schedule: LayupSchedule,
    output_path: str | Path,
) -> Path:
    """Export layup schedule to JSON.

    Structure:
    {
        "total_thickness_mm": ...,
        "bodies": [...],
        "plies": [
            {
                "body_name": ...,
                "layer_num": ...,
                "angle_deg": ...,
                "material": ...,
                "thickness_mm": ...,
            },
            ...
        ]
    }
    """
    import json

    output_path = Path(output_path)

    data = {
        "total_thickness_mm": schedule.total_thickness_mm,
        "bodies": schedule.bodies,
        "plies": [
            {
                "body_name": p.body_name,
                "layer_num": p.layer_num,
                "angle_deg": p.angle_deg,
                "material": p.material,
                "thickness_mm": p.thickness_mm,
            }
            for p in schedule.plies
        ],
    }

    output_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def export_layup(
    config: Config,
    output_dir: str | Path,
) -> LayupExportResult:
    """Export complete layup schedule (CSV + JSON).

    Args:
        config: the input Config.
        output_dir: directory for output files.

    Returns:
        LayupExportResult with paths and validation status.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    schedule = build_layup_schedule(config)

    csv_path = export_layup_csv(schedule, output_dir / "layup_schedule.csv")
    json_path = export_layup_json(schedule, output_dir / "layup_schedule.json")

    return LayupExportResult(
        csv_path=csv_path,
        json_path=json_path,
        ply_count=len(schedule.plies),
        body_count=len(schedule.bodies),
    )
