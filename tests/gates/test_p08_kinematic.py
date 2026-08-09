"""Gate P08 — Kinematic gate (the decisive R1 gate).

Plan.md P8 pass criteria:
- Sweep TE and droop through ±max_deflection: coarse 1° steps + fine 0.1°
  steps in the outer 20 % of travel
- Collision count = 0 at every step
- Minimum clearance ≥ gap_mm − tolerance and monotonic-trend check
- Swept-volume boolean at both extremes intersect fixed wing = ∅ (F9)

Tests:
1. Module loads with all functions and classes
2. _build_step_angles generates correct step density (coarse + fine)
3. sweep_device returns KinematicResult with steps
4. sweep_device step count matches expected (coarse + fine)
5. Collision count = 0 at all steps (toy geometry)
6. Clearance is measured at all steps
7. Monotonic trend check works
8. check_kinematics returns correct pass/fail
9. check_kinematics reports all_pass = True for valid sweep
10. check_kinematics reports all_pass = False for collision
11. _build_swept_volume returns solid or None
12. _check_swept_intersects_wing works
13. sweep_all_devices returns dict for enabled devices
14. _rotate_device_solid rotates correctly
15. KinematicResult has all required fields
"""
from __future__ import annotations

import pytest

from backend.tolerances import KERNEL_TOLERANCE_MM


@pytest.fixture
def small_config():
    import yaml
    with open("benchmarks/small.yaml") as f:
        d = yaml.safe_load(f)
    return {"te_surface": {"enabled": True, "span_start_frac": 0.60, "span_end_frac": 0.95,
                           "hinge_xc_start": 0.95, "hinge_xc_end": 0.95,
                           "gap_mm": 1.5, "max_deflection_deg": 25,
                           "hinges": {"mode": "generated", "count": 3}},
            "le_droop": {"enabled": False, "span_start_frac": 0.0, "span_end_frac": 0.1,
                         "hinge_xc_start": 0.0, "hinge_xc_end": 0.0,
                         "gap_mm": 1.0, "max_deflection_deg": 1.0,
                         "hinges": {"mode": "generated", "count": 1}},
            **{k: v for k, v in d.items() if k not in ("te_surface", "le_droop")}}


@pytest.fixture
def medium_config():
    import yaml
    with open("benchmarks/medium.yaml") as f:
        d = yaml.safe_load(f)
    return d


# ── 1. Module loads ────────────────────────────────────────────────────────


def test_kinematic_module_loads():
    """Kinematic module loads with all functions and classes."""
    from backend.geometry.kinematic import (
        sweep_device,
        check_kinematics,
        sweep_all_devices,
        KinematicResult,
        SweepStep,
        _build_step_angles,
        _rotate_device_solid,
        _build_swept_volume,
        _check_swept_intersects_wing,
    )

    assert callable(sweep_device)
    assert callable(check_kinematics)
    assert callable(sweep_all_devices)
    assert callable(_build_step_angles)
    assert callable(_rotate_device_solid)
    assert callable(_build_swept_volume)
    assert callable(_check_swept_intersects_wing)


# ── 2. Step angle generation ──────────────────────────────────────────────


def test_build_step_angles_zero():
    """_build_step_angles(0) returns [0.0]."""
    from backend.geometry.kinematic import _build_step_angles
    angles = _build_step_angles(0)
    assert angles == [0.0]


def test_build_step_angles_small():
    """_build_step_angles(5) returns coarse steps with fine in outer 20%."""
    from backend.geometry.kinematic import _build_step_angles

    angles = _build_step_angles(5)
    assert 0.0 in angles
    assert 5.0 in angles
    assert -5.0 in angles
    # Should have more than just 3 points (coarse + fine)
    assert len(angles) > 3


def test_build_step_angles_medium():
    """_build_step_angles(25) returns correct number of steps."""
    from backend.geometry.kinematic import _build_step_angles

    angles = _build_step_angles(25)
    assert 0.0 in angles
    assert 25.0 in angles
    assert -25.0 in angles
    # 25° range: 25 coarse steps each way + fine steps in outer 20% (5°)
    # Outer 20% = 5°, fine 0.1° = 50 steps per side
    # Total should be > 50 steps
    assert len(angles) > 50


def test_build_step_angles_symmetric():
    """_build_step_angles returns symmetric angles about 0."""
    from backend.geometry.kinematic import _build_step_angles

    angles = _build_step_angles(10)
    # Check symmetry: for every positive angle, there should be a matching negative
    neg_angles = [a for a in angles if a < 0]
    pos_angles = [a for a in angles if a > 0]
    assert len(neg_angles) == len(pos_angles)


# ── 3. Sweep device returns result ────────────────────────────────────────


def test_sweep_device_returns_result(small_config):
    """sweep_device() returns a KinematicResult with steps."""
    from backend.geometry.kinematic import sweep_device, KinematicResult
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.loft import build_oml
    from backend.geometry.reference import build_hinge_axes
    from backend.schema.models import Config
    import cadquery as cq

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    solid = build_oml(sections, cfg.planform.mirror)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    # Create a simple test device (small box near the TE)
    axis = ref["te"]
    vertices = axis.Vertices()
    p1 = vertices[0].toTuple()
    p2 = vertices[1].toTuple()
    mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2, (p1[2]+p2[2])/2)

    device = cq.Workplane("XY").box(5, 10, 2).translate((mid[0], mid[1], mid[2])).val()

    result = sweep_device(solid, device, axis, max_deflection_deg=1.0)
    assert isinstance(result, KinematicResult)
    assert len(result.steps) > 0


# ── 4. Step count matches expected ────────────────────────────────────────


def test_sweep_device_step_count(small_config):
    """sweep_device() produces the expected number of steps."""
    from backend.geometry.kinematic import sweep_device, _build_step_angles
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.loft import build_oml
    from backend.geometry.reference import build_hinge_axes
    from backend.schema.models import Config
    import cadquery as cq

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    solid = build_oml(sections, cfg.planform.mirror)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    axis = ref["te"]
    vertices = axis.Vertices()
    p1 = vertices[0].toTuple()
    mid = (p1[0], p1[1], p1[2])

    device = cq.Workplane("XY").box(5, 10, 2).translate((mid[0], mid[1], mid[2])).val()

    max_defl = 1.0
    expected_angles = _build_step_angles(max_defl)
    result = sweep_device(solid, device, axis, max_deflection_deg=max_defl)

    assert len(result.steps) == len(expected_angles)


# ── 5. Collision count for toy geometry ───────────────────────────────────


def test_sweep_device_no_collision_toy(small_config):
    """sweep_device() collision count = 0 for toy geometry far from wing."""
    from backend.geometry.kinematic import sweep_device
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.loft import build_oml
    from backend.geometry.reference import build_hinge_axes
    from backend.schema.models import Config
    import cadquery as cq

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    solid = build_oml(sections, cfg.planform.mirror)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    axis = ref["te"]

    # Create a device far away from the wing (no collision possible)
    device = cq.Workplane("XY").box(1, 1, 1).translate((1000, 1000, 1000)).val()

    result = sweep_device(solid, device, axis, max_deflection_deg=1.0)
    assert result.collision_count == 0


# ── 6. Clearance measured ─────────────────────────────────────────────────


def test_sweep_device_clearance_measured(small_config):
    """sweep_device() measures clearance at all steps."""
    from backend.geometry.kinematic import sweep_device
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.loft import build_oml
    from backend.geometry.reference import build_hinge_axes
    from backend.schema.models import Config
    import cadquery as cq

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    solid = build_oml(sections, cfg.planform.mirror)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    axis = ref["te"]

    # Device far away — clearance should be large
    device = cq.Workplane("XY").box(1, 1, 1).translate((1000, 1000, 1000)).val()

    result = sweep_device(solid, device, axis, max_deflection_deg=1.0)
    for step in result.steps:
        assert step.min_clearance_mm < float("inf")


# ── 7. Monotonic trend ────────────────────────────────────────────────────


def test_monotonic_trend_check():
    """Monotonic trend check works correctly."""
    from backend.geometry.kinematic import KinematicResult, SweepStep

    # Monotonic: clearance increases with |angle|
    result = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[
            SweepStep(angle_deg=-10.0, min_clearance_mm=5.0),
            SweepStep(angle_deg=-5.0, min_clearance_mm=3.0),
            SweepStep(angle_deg=0.0, min_clearance_mm=1.0),
            SweepStep(angle_deg=5.0, min_clearance_mm=3.0),
            SweepStep(angle_deg=10.0, min_clearance_mm=5.0),
        ],
    )
    assert result.monotonic_trend is True

    # Non-monotonic: clearance decreases at some point
    result2 = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[
            SweepStep(angle_deg=-10.0, min_clearance_mm=5.0),
            SweepStep(angle_deg=-5.0, min_clearance_mm=3.0),
            SweepStep(angle_deg=0.0, min_clearance_mm=1.0),
            SweepStep(angle_deg=5.0, min_clearance_mm=0.5),  # decreases!
            SweepStep(angle_deg=10.0, min_clearance_mm=5.0),
        ],
    )
    assert result2.monotonic_trend is False


# ── 8. check_kinematics pass ──────────────────────────────────────────────


def test_check_kinematics_pass():
    """check_kinematics() returns all_pass = True for valid sweep."""
    from backend.geometry.kinematic import check_kinematics, KinematicResult, SweepStep

    result = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[SweepStep(angle_deg=0.0, min_clearance_mm=2.0)],
        collision_count=0,
        min_clearance_mm=2.0,
        swept_intersects_wing_at_max=False,
        swept_intersects_wing_at_min=False,
        monotonic_trend=True,
    )

    checks = check_kinematics(result, gap_mm=1.5)
    assert checks["all_pass"] is True
    assert checks["collision_free"] is True
    assert checks["clearance_ok"] is True
    assert checks["monotonic_trend"] is True


def test_check_kinematics_collision_fail():
    """check_kinematics() returns all_pass = False for collision."""
    from backend.geometry.kinematic import check_kinematics, KinematicResult, SweepStep

    result = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[SweepStep(angle_deg=0.0, min_clearance_mm=2.0)],
        collision_count=1,  # collision!
        min_clearance_mm=2.0,
        swept_intersects_wing_at_max=False,
        swept_intersects_wing_at_min=False,
        monotonic_trend=True,
    )

    checks = check_kinematics(result, gap_mm=1.5)
    assert checks["all_pass"] is False
    assert checks["collision_free"] is False


def test_check_kinematics_clearance_fail():
    """check_kinematics() returns all_pass = False for insufficient clearance."""
    from backend.geometry.kinematic import check_kinematics, KinematicResult, SweepStep

    result = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[SweepStep(angle_deg=0.0, min_clearance_mm=0.5)],
        collision_count=0,
        min_clearance_mm=0.5,
        swept_intersects_wing_at_max=False,
        swept_intersects_wing_at_min=False,
        monotonic_trend=True,
    )

    checks = check_kinematics(result, gap_mm=1.5)
    assert checks["all_pass"] is False
    assert checks["clearance_ok"] is False


# ── 9. check_kinematics swept volume ──────────────────────────────────────


def test_check_kinematics_swept_volume_fail():
    """check_kinematics() returns all_pass = False for swept volume intersection."""
    from backend.geometry.kinematic import check_kinematics, KinematicResult, SweepStep

    result = KinematicResult(
        device_name="test",
        max_deflection_deg=10.0,
        steps=[SweepStep(angle_deg=0.0, min_clearance_mm=2.0)],
        collision_count=0,
        min_clearance_mm=2.0,
        swept_intersects_wing_at_max=True,  # intersection!
        swept_intersects_wing_at_min=False,
        monotonic_trend=True,
    )

    checks = check_kinematics(result, gap_mm=1.5)
    assert checks["all_pass"] is False
    assert checks["swept_volume_no_wing_intersection_at_max"] is False


# ── 10. Build swept volume ────────────────────────────────────────────────


def test_build_swept_volume_returns_solid():
    """_build_swept_volume() returns a solid for valid inputs."""
    from backend.geometry.kinematic import _build_swept_volume
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    device = cq.Workplane("XY").box(5, 10, 2).translate((50, 0, 0)).val()

    swept = _build_swept_volume(device, axis, -5.0, 5.0)
    assert swept is not None
    assert swept.Volume() > 0


def test_build_swept_volume_returns_none_for_invalid():
    """_build_swept_volume() returns None for invalid inputs."""
    from backend.geometry.kinematic import _build_swept_volume
    import cadquery as cq

    # Create an axis with only 1 vertex (invalid)
    # Use a single vertex edge — makeLine with same points raises, so use a point
    vertex = cq.Vertex.makeVertex(0, 0, 0)
    device = cq.Workplane("XY").box(5, 10, 2).translate((50, 0, 0)).val()

    # A Vertex has only 1 Vertex when queried for Vertices, so < 2 check triggers
    swept = _build_swept_volume(device, vertex, -5.0, 5.0)
    assert swept is None


# ── 11. Check swept intersects wing ───────────────────────────────────────


def test_check_swept_intersects_wing():
    """_check_swept_intersects_wing() correctly detects intersection."""
    from backend.geometry.kinematic import _check_swept_intersects_wing
    import cadquery as cq

    # Two overlapping boxes — use .solids().vals() to get actual Solid objects
    box1 = cq.Workplane("XY").box(10, 10, 10).solids().vals()[0]
    box2 = cq.Workplane("XY").box(10, 10, 10).translate((5, 0, 0)).solids().vals()[0]

    assert _check_swept_intersects_wing(box1, box2) is True

    # Two non-overlapping boxes
    box3 = cq.Workplane("XY").box(10, 10, 10).solids().vals()[0]
    box4 = cq.Workplane("XY").box(10, 10, 10).translate((100, 0, 0)).solids().vals()[0]

    assert _check_swept_intersects_wing(box3, box4) is False


# ── 12. Rotate device solid ──────────────────────────────────────────────


def test_rotate_device_solid():
    """_rotate_device_solid() rotates a solid about the hinge axis."""
    from backend.geometry.kinematic import _rotate_device_solid
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    device = cq.Workplane("XY").box(5, 10, 2).translate((50, 0, 5)).val()

    rotated = _rotate_device_solid(device, axis, 90.0)
    assert rotated is not None
    assert rotated.Volume() == device.Volume()  # volume preserved


# ── 13. KinematicResult fields ────────────────────────────────────────────


def test_kinematic_result_has_required_fields():
    """KinematicResult has all required fields."""
    from backend.geometry.kinematic import KinematicResult

    result = KinematicResult(device_name="test", max_deflection_deg=10.0)
    assert hasattr(result, "device_name")
    assert hasattr(result, "max_deflection_deg")
    assert hasattr(result, "steps")
    assert hasattr(result, "collision_count")
    assert hasattr(result, "min_clearance_mm")
    assert hasattr(result, "swept_volume_at_max")
    assert hasattr(result, "swept_volume_at_min")
    assert hasattr(result, "swept_intersects_wing_at_max")
    assert hasattr(result, "swept_intersects_wing_at_min")
    assert hasattr(result, "monotonic_trend")


# ── 14. Sweep all devices ─────────────────────────────────────────────────


def test_sweep_all_devices_returns_dict(small_config):
    """sweep_all_devices() returns a dict for enabled devices."""
    from backend.geometry.kinematic import sweep_all_devices
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.loft import build_oml
    from backend.geometry.reference import build_hinge_axes
    from backend.schema.models import Config
    import cadquery as cq

    cfg = Config.model_validate(small_config)
    # Reduce max_deflection for faster tests
    cfg.te_surface.max_deflection_deg = 1.0
    sections = build_planform_sections(cfg)
    solid = build_oml(sections, cfg.planform.mirror)
    ref = build_hinge_axes(cfg)

    # Create toy device solids
    device_solids = {}
    for name, axis in ref.items():
        vertices = axis.Vertices()
        p1 = vertices[0].toTuple()
        device_solids[name] = cq.Workplane("XY").box(1, 1, 1).translate((p1[0], p1[1], p1[2])).val()

    results = sweep_all_devices(cfg, solid, device_solids, ref)
    assert isinstance(results, dict)
    # TE is enabled, LE is disabled
    assert "te" in results


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p08"] = {
        "sweep_steps": "coarse 1° + fine 0.1° in outer 20%",
        "checks": [
            "collision_count == 0",
            "min_clearance >= gap_mm - tolerance",
            "monotonic_trend",
            "swept_volume_no_wing_intersection",
        ],
        "functions": [
            "sweep_device",
            "check_kinematics",
            "sweep_all_devices",
            "_build_step_angles",
            "_rotate_device_solid",
            "_build_swept_volume",
            "_check_swept_intersects_wing",
        ],
        "description": "Kinematic gate — sweep TE/LE through ±max_deflection, verify collision-free motion",
    }
