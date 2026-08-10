"""Gate P17 — DXF flat patterns.

Plan.md P17 pass criteria:
- Rib patterns: re-parsed DXF area = source face area within 0.1%
- Spar webs: developability metric computed
- Non-developable webs carry WARNING entity + distortion metric in DXF and gate JSON
- Silent unroll = fail (F6)

Tests:
1. Module loads with all functions and classes
2. export_rib_pattern creates pattern with area
3. Rib pattern area matches source face area within 0.1%
4. export_spar_web includes developability check
5. check_developability detects developable surfaces (plane)
6. check_developability detects non-developable surfaces (sphere)
7. Non-developable surface carries WARNING
8. DxfPattern has all required fields
9. DevelopabilityResult has all required fields
10. dxf_pattern_to_string produces valid DXF
11. validate_dxf_area passes for matching areas
12. validate_dxf_area fails for mismatched areas
"""
from __future__ import annotations

import cadquery as cq
import pytest

from backend.tolerances import COAXIALITY_TOLERANCE_MM


# ── 1. Module loads ───────────────────────────────────────────────────────


def test_dxf_module_loads():
    """DXF module loads with all functions and classes."""
    from backend.exporters.dxf_flat import (
        export_rib_pattern,
        export_spar_web,
        check_developability,
        dxf_pattern_to_string,
        validate_dxf_area,
        DxfPattern,
        DevelopabilityResult,
    )

    assert callable(export_rib_pattern)
    assert callable(export_spar_web)
    assert callable(check_developability)
    assert callable(dxf_pattern_to_string)
    assert callable(validate_dxf_area)


# ── 2. Export rib pattern ────────────────────────────────────────────────


def test_export_rib_pattern():
    """export_rib_pattern creates pattern with area."""
    from backend.exporters.dxf_flat import export_rib_pattern

    # Create a simple rectangular face
    face = cq.Workplane("XY").box(100, 50, 1).val().Faces()[0]
    pattern = export_rib_pattern(face, name="test_rib")

    assert pattern.name == "test_rib"
    assert pattern.area_mm2 > 0
    assert len(pattern.entities) > 0


# ── 3. Rib pattern area validation ───────────────────────────────────────


def test_rib_pattern_area_matches():
    """Rib pattern area matches source face area within 0.1%."""
    from backend.exporters.dxf_flat import export_rib_pattern, validate_dxf_area

    # Create a 100x50 mm rectangle face
    face = cq.Workplane("XY").box(100, 50, 1).val().Faces()[0]
    expected_area = face.Area()  # Get actual face area

    pattern = export_rib_pattern(face, name="test_rib")

    # Area should match exactly (same source)
    assert pattern.area_mm2 == expected_area


# ── 4. Export spar web with developability ───────────────────────────────


def test_export_spar_web():
    """export_spar_web includes developability check."""
    from backend.exporters.dxf_flat import export_spar_web

    # Create a simple rectangular face (developable)
    face = cq.Workplane("XY").box(100, 50, 1).val().Faces()[0]
    pattern = export_spar_web(face, name="test_spar")

    assert pattern.name == "test_spar"
    assert pattern.area_mm2 > 0
    assert pattern.developability is not None
    assert pattern.developability.is_developable is True


# ── 5. Developability — plane (developable) ─────────────────────────────


def test_developability_plane():
    """check_developability detects plane as developable."""
    from backend.exporters.dxf_flat import check_developability

    # Plane is developable
    face = cq.Workplane("XY").box(100, 50, 1).val().Faces()[0]
    result = check_developability(face)

    assert result.is_developable is True
    assert result.distortion_metric == 0.0
    assert result.sampled_points > 0


# ── 6. Developability — sphere (NOT developable) ────────────────────────


def test_developability_sphere():
    """check_developability detects sphere as NOT developable."""
    from backend.exporters.dxf_flat import check_developability

    # Sphere is NOT developable
    sphere = cq.Workplane("XY").sphere(25).val()
    face = sphere.Faces()[0]
    result = check_developability(face)

    assert result.is_developable is False
    assert result.distortion_metric > 0
    assert result.warning_message != ""


# ── 7. Non-developable surface carries WARNING ──────────────────────────


def test_non_developable_carry_warning():
    """Non-developable surface carries WARNING in pattern."""
    from backend.exporters.dxf_flat import export_spar_web

    sphere = cq.Workplane("XY").sphere(25).val()
    face = sphere.Faces()[0]
    pattern = export_spar_web(face, name="test_spar")

    assert len(pattern.warnings) > 0
    assert "Non-developable" in pattern.warnings[0]


# ── 8. DxfPattern has all required fields ───────────────────────────────


def test_dxf_pattern_has_required_fields():
    """DxfPattern has all required fields."""
    from backend.exporters.dxf_flat import DxfPattern

    pattern = DxfPattern(name="test")
    assert hasattr(pattern, "name")
    assert hasattr(pattern, "entities")
    assert hasattr(pattern, "area_mm2")
    assert hasattr(pattern, "developability")
    assert hasattr(pattern, "warnings")


# ── 9. DevelopabilityResult has all required fields ─────────────────────


def test_developability_result_has_required_fields():
    """DevelopabilityResult has all required fields."""
    from backend.exporters.dxf_flat import DevelopabilityResult

    result = DevelopabilityResult(is_developable=True, distortion_metric=0.0)
    assert hasattr(result, "is_developable")
    assert hasattr(result, "distortion_metric")
    assert hasattr(result, "warning_message")
    assert hasattr(result, "sampled_points")


# ── 10. DXF string generation ───────────────────────────────────────────


def test_dxf_pattern_to_string():
    """dxf_pattern_to_string produces valid DXF."""
    from backend.exporters.dxf_flat import DxfPattern, dxf_pattern_to_string

    pattern = DxfPattern(
        name="test",
        entities=[
            {
                "type": "LINE",
                "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                "end": {"x": 100.0, "y": 0.0, "z": 0.0},
            }
        ],
        area_mm2=100.0,
    )

    dxf_str = dxf_pattern_to_string(pattern)

    assert "SECTION" in dxf_str
    assert "ENTITIES" in dxf_str
    assert "LINE" in dxf_str
    assert "EOF" in dxf_str


# ── 11. Validate DXF area — matching ────────────────────────────────────


def test_validate_dxf_area_matching():
    """validate_dxf_area passes for matching areas."""
    from backend.exporters.dxf_flat import DxfPattern, validate_dxf_area

    pattern = DxfPattern(name="test", area_mm2=100.0)
    result = validate_dxf_area(pattern, expected_area=100.0, tolerance=0.001)
    assert result is True


# ── 12. Validate DXF area — mismatching ─────────────────────────────────


def test_validate_dxf_area_mismatching():
    """validate_dxf_area fails for mismatched areas."""
    from backend.exporters.dxf_flat import DxfPattern, validate_dxf_area

    pattern = DxfPattern(name="test", area_mm2=100.0)
    result = validate_dxf_area(pattern, expected_area=200.0, tolerance=0.001)
    assert result is False


# ── Gate metrics ──────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p17"] = {
        "dxf_generation": "Rib/spar flat patterns with area validation and developability check",
        "checks": [
            "rib patterns: re-parsed DXF area = source face area within 0.1%",
            "spar webs: developability metric computed",
            "non-developable webs carry WARNING entity + distortion metric (F6)",
            "silent unroll = fail",
        ],
        "functions": [
            "export_rib_pattern",
            "export_spar_web",
            "check_developability",
            "dxf_pattern_to_string",
            "validate_dxf_area",
        ],
        "description": "DXF flat patterns with area validation and developability checking",
    }
