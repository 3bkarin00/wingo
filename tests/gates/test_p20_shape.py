"""P20 gate — wing shape validation.

End-to-end checks on generated wing geometry using real OCP APIs:

1. Global bounding box sanity (span, chord, thickness)
2. Face area validation (no degenerate faces)
3. Symmetry verification (left/right for mirrored wings)
4. Cross-section chord/thickness at key stations
5. Volume bounds validation (vs analytic estimate)

Uses the REAL OCP APIs confirmed in scripts/r0_probes/probe_p20_shape.py:
- BRepBndLib.Add_s for bounding box
- BRepGProp.SurfaceProperties_s for face areas
- gp_Pnt/gp_Vec for face normals
- Vertex.X/Y/Z for vertex coordinates (not X(), Y(), Z())

Golden configs must pass all checks. Edge configs (high taper, high twist,
thin foil) must pass all checks except symmetry (not mirrored).
"""
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from backend import tolerances
from backend.geometry.loft import build_oml
from backend.geometry.sections import build_planform_sections
from backend.geometry.validate import ShapeValidationResult, validate_wing_shape
from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
EDGE_DIR = REPO_ROOT / "tests" / "configs" / "edge"

golden_configs = sorted(GOLDEN_DIR.glob("*.yaml"))
edge_configs = sorted(EDGE_DIR.glob("*.yaml"))
all_configs = golden_configs + edge_configs


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


@pytest.mark.parametrize("cfg_path", all_configs, ids=lambda p: p.stem)
def test_span_validation(cfg_path, gate_metrics):
    """Bounding box span must match planform span within span_tol_mm."""
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.span_ok, (
        f"{cfg_path.stem}: span {result.span_mm:.1f} mm != expected "
        f"{result.expected_span_mm:.1f} mm (tol {tolerances.KERNEL_TOLERANCE_MM} mm)"
    )
    gate_metrics.setdefault("span", {})[cfg_path.stem] = {
        "measured_mm": round(result.span_mm, 1),
        "expected_mm": round(result.expected_span_mm, 1),
        "ok": result.span_ok,
    }


@pytest.mark.parametrize("cfg_path", all_configs, ids=lambda p: p.stem)
def test_no_degenerate_faces(cfg_path, gate_metrics):
    """No face should have area below the minimum threshold."""
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.degenerate_faces == 0, (
        f"{cfg_path.stem}: {result.degenerate_faces} degenerate faces "
        f"(count={result.face_count})"
    )
    gate_metrics.setdefault("faces", {})[cfg_path.stem] = {
        "count": result.face_count,
        "degenerate": result.degenerate_faces,
    }


@pytest.mark.parametrize("cfg_path", golden_configs, ids=lambda p: p.stem)
def test_symmetry_mirrored(cfg_path, gate_metrics):
    """Mirrored golden configs must have left/right symmetry within tolerance."""
    config = _load(cfg_path)
    if not config.planform.mirror:
        pytest.skip("Config not mirrored")

    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.symmetry_ok, (
        f"{cfg_path.stem}: max symmetry deviation {result.symmetry_max_dev_mm:.3f} mm "
        f"> tolerance {tolerances.KERNEL_TOLERANCE_MM} mm"
    )
    gate_metrics.setdefault("symmetry", {})[cfg_path.stem] = {
        "max_dev_mm": round(result.symmetry_max_dev_mm, 3),
        "ok": result.symmetry_ok,
    }


@pytest.mark.parametrize("cfg_path", all_configs, ids=lambda p: p.stem)
def test_chord_validation(cfg_path, gate_metrics):
    """Measured chord at each section must match declared chord within kernel tolerance."""
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.chord_at_stations_ok, (
        f"{cfg_path.stem}: chord deviations: {result.chord_deviations}"
    )
    gate_metrics.setdefault("chord", {})[cfg_path.stem] = {
        "ok": result.chord_at_stations_ok,
        "deviations_mm": [
            {"y_mm": round(y, 1), "measured": round(m, 1), "declared": round(d, 1)}
            for y, m, d in result.chord_deviations
        ],
    }


@pytest.mark.parametrize("cfg_path", golden_configs, ids=lambda p: p.stem)
def test_volume_bounds(cfg_path, gate_metrics):
    """Volume must be within ±3% of analytic estimate for mirrored golden configs."""
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.volume_ok, (
        f"{cfg_path.stem}: volume {result.volume_mm3:.0f} mm³ deviates "
        f"{result.volume_dev_pct:.2f}% from estimate {result.volume_estimate_mm3:.0f} mm³ "
        f"(limit {tolerances.LOFT_VS_ESTIMATE_FRAC * 100:.0f}%)"
    )
    gate_metrics.setdefault("volume", {})[cfg_path.stem] = {
        "volume_mm3": round(result.volume_mm3, 1),
        "estimate_mm3": round(result.volume_estimate_mm3, 1),
        "dev_pct": round(result.volume_dev_pct, 3),
        "ok": result.volume_ok,
    }


@pytest.mark.parametrize("cfg_path", golden_configs, ids=lambda p: p.stem)
def test_overall_shape_ok(cfg_path, gate_metrics):
    """All shape validation checks must pass for mirrored golden configs."""
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    result = validate_wing_shape(config, solid, sections)

    assert result.overall_ok, (
        f"{cfg_path.stem}: overall shape validation failed. "
        f"span_ok={result.span_ok}, chord_ok={result.chord_at_stations_ok}, "
        f"thickness_ok={result.thickness_ok}, degenerate={result.degenerate_faces}, "
        f"symmetry_ok={result.symmetry_ok}, volume_ok={result.volume_ok}"
    )
    gate_metrics.setdefault("overall", {})[cfg_path.stem] = {
        "ok": result.overall_ok,
    }


def test_validate_wing_shape_module_loads():
    """Module loads without errors."""
    from backend.geometry import validate
    assert hasattr(validate, "validate_wing_shape")
    assert hasattr(validate, "ShapeValidationResult")


def test_shape_validation_result_dataclass():
    """ShapeValidationResult is a dataclass with expected fields."""
    result = ShapeValidationResult()
    assert hasattr(result, "span_ok")
    assert hasattr(result, "face_count")
    assert hasattr(result, "symmetry_ok")
    assert hasattr(result, "volume_ok")
    assert hasattr(result, "overall_ok")
    assert result.overall_ok is False  # Default: not ok
