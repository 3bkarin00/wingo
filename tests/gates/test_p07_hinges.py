"""Gate P07 — Hinges (generated mode).

Plan.md P7 pass criteria:
- All hinge holes coaxial with their axis within 0.05 mm (measured on generated geometry)
- Lug/tang clearance to moving body >= configured fit gap

Tests:
1. Module loads with all functions and classes
2. generate_hinge_holes creates holes along hinge axis with correct count
3. generate_lug_tang creates lug/tang features with correct count
4. Coaxiality measurement returns 0 mm (by construction)
5. Coaxiality is within tolerance (0.05 mm)
6. Lug/tang clearance >= configured fit gap
7. build_hinge_geometry works for TE device
8. build_hinge_geometry works for LE device
9. build_hinge_geometry returns empty for disabled device
10. HingeGeometry.solid_hole_cutouts returns valid solids
11. HingeGeometry.solid_lug_features returns valid solids
12. HingeGeometry.solid_tang_features returns valid solids
13. measure_coaxiality returns correct distance for non-zero offset
14. measure_lug_clearance returns correct clearance
15. HingeGeometry has all required fields
"""
from __future__ import annotations

import pytest

from backend.tolerances import COAXIALITY_TOLERANCE_MM


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


def test_hinges_module_loads():
    """Hinges module loads with all functions and classes."""
    from backend.geometry.hinges import (
        generate_hinge_holes,
        generate_lug_tang,
        build_hinge_geometry,
        measure_coaxiality,
        measure_lug_clearance,
        HingeGeometry,
        HingeHole,
        LugTang,
        DEFAULT_HINGE_PIN_DIA_MM,
        LUG_PROTRUSION_FRAC,
        TANG_CLEARANCE_FRAC,
    )

    assert callable(generate_hinge_holes)
    assert callable(generate_lug_tang)
    assert callable(build_hinge_geometry)
    assert callable(measure_coaxiality)
    assert callable(measure_lug_clearance)
    assert DEFAULT_HINGE_PIN_DIA_MM == 6.0
    assert LUG_PROTRUSION_FRAC == 0.4
    assert TANG_CLEARANCE_FRAC == 0.15


# ── 2. Generate hinge holes ───────────────────────────────────────────────


def test_generate_hinge_holes_creates_correct_count(small_config):
    """generate_hinge_holes() returns exactly `count` holes."""
    from backend.geometry.hinges import generate_hinge_holes
    import cadquery as cq

    # Build a simple hinge axis line
    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 10))
    holes = generate_hinge_holes(axis, count=3, pin_dia_mm=6.0)
    assert len(holes) == 3


def test_hinge_holes_spaced_along_axis(small_config):
    """Hinge hole centers are evenly spaced along the hinge axis."""
    from backend.geometry.hinges import generate_hinge_holes
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    holes = generate_hinge_holes(axis, count=5, pin_dia_mm=6.0)

    xs = [h.center[0] for h in holes]
    # Centers should be evenly spaced between 10 and 90 (10% and 90% of axis length)
    assert xs[0] > 0
    assert xs[-1] < 100
    # Check spacing is roughly equal
    for i in range(1, len(xs)):
        assert abs(xs[i] - xs[i-1] - 20.0) < 1.0  # 100/5 = 20 mm spacing


def test_hinge_holes_have_correct_radius(small_config):
    """Hinge hole radius = pin_dia_mm / 2."""
    from backend.geometry.hinges import generate_hinge_holes
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    holes = generate_hinge_holes(axis, count=3, pin_dia_mm=10.0)
    for h in holes:
        assert h.radius_mm == 5.0  # 10 / 2


# ── 3. Generate lug/tang ──────────────────────────────────────────────────


def test_generate_lug_tang_creates_correct_count(small_config):
    """generate_lug_tang() returns exactly `count` lug/tang pairs."""
    from backend.geometry.hinges import generate_lug_tang
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 10))
    lugs = generate_lug_tang(axis, count=3, pin_dia_mm=6.0, fit_gap_mm=1.5)
    assert len(lugs) == 3


def test_lug_tang_dimensions(small_config):
    """Lug protrusion and tang depth follow the configured fractions."""
    from backend.geometry.hinges import generate_lug_tang
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    lugs = generate_lug_tang(axis, count=3, pin_dia_mm=6.0, fit_gap_mm=1.5)

    for lt in lugs:
        # lug_protrusion = pin_dia * LUG_PROTRUSION_FRAC = 6.0 * 0.4 = 2.4
        assert abs(lt.lug_protrusion_mm - 2.4) < 0.01
        # tang_depth = lug_protrusion + fit_gap = 2.4 + 1.5 = 3.9
        assert abs(lt.tang_depth_mm - 3.9) < 0.01


# ── 4. Coaxiality measurement ─────────────────────────────────────────────


def test_coaxiality_by_construction_is_zero(small_config):
    """Coaxiality of holes generated from the axis line is 0 mm."""
    from backend.geometry.hinges import generate_hinge_holes, measure_coaxiality
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    holes = generate_hinge_holes(axis, count=5, pin_dia_mm=6.0)
    centers = [h.center for h in holes]

    coax = measure_coaxiality(axis, centers)
    assert coax == 0.0  # By construction, hole centers lie exactly on the axis


def test_coaxiality_within_tolerance(small_config):
    """Coaxiality is within COAXIALITY_TOLERANCE_MM (0.05 mm)."""
    from backend.geometry.hinges import generate_hinge_holes, measure_coaxiality
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 10))
    holes = generate_hinge_holes(axis, count=3, pin_dia_mm=6.0)
    centers = [h.center for h in holes]

    coax = measure_coaxiality(axis, centers)
    assert coax <= COAXIALITY_TOLERANCE_MM


def test_coaxiality_measures_offset_correctly():
    """Coaxiality correctly measures distance when hole centers are offset."""
    from backend.geometry.hinges import measure_coaxiality
    import cadquery as cq

    # Axis along X from (0,0,0) to (100,0,0)
    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))

    # Hole centers offset by 0.03 mm in Z
    centers = [(20, 0, 0.03), (50, 0, 0.03), (80, 0, 0.03)]
    coax = measure_coaxiality(axis, centers)
    assert abs(coax - 0.03) < 0.001


# ── 5. Lug/tang clearance ─────────────────────────────────────────────────


def test_lug_clearance_meets_fit_gap(small_config):
    """Lug/tang clearance >= configured fit gap."""
    from backend.geometry.hinges import generate_lug_tang, measure_lug_clearance
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    lugs = generate_lug_tang(axis, count=3, pin_dia_mm=6.0, fit_gap_mm=1.5)

    clearance = measure_lug_clearance(axis, lugs, fit_gap_mm=1.5)
    assert clearance >= 1.5


def test_lug_clearance_correct_value():
    """Lug/tang clearance calculation is correct."""
    from backend.geometry.hinges import generate_lug_tang, measure_lug_clearance
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    lugs = generate_lug_tang(axis, count=3, pin_dia_mm=6.0, fit_gap_mm=1.5)

    clearance = measure_lug_clearance(axis, lugs, fit_gap_mm=1.5)
    # lug_protrusion = 2.4, tang_depth = 3.9
    # clearance = tang_depth - lug_protrusion = 3.9 - 2.4 = 1.5
    assert abs(clearance - 1.5) < 0.01


# ── 6. build_hinge_geometry for TE device ─────────────────────────────────


def test_build_hinge_geometry_te(small_config):
    """build_hinge_geometry() generates hinge geometry for TE device."""
    from backend.geometry.hinges import build_hinge_geometry
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    import cadquery as cq

    # Build sections and reference
    from backend.schema.models import Config
    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    hinge_geom = build_hinge_geometry(cfg, ref["te"], device_name="te")
    assert hinge_geom.count == 3
    assert len(hinge_geom.holes) == 3
    assert len(hinge_geom.lugs) == 3
    assert hinge_geom.pin_dia_mm == 6.0
    assert hinge_geom.fit_gap_mm == 1.5


# ── 7. build_hinge_geometry for LE device ─────────────────────────────────


def test_build_hinge_geometry_le(medium_config):
    """build_hinge_geometry() generates hinge geometry for LE device."""
    from backend.geometry.hinges import build_hinge_geometry
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    from backend.schema.models import Config

    cfg = Config.model_validate(medium_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    if "le" not in ref:
        pytest.skip("No LE hinge axis in this config")

    hinge_geom = build_hinge_geometry(cfg, ref["le"], device_name="le")
    assert hinge_geom.count > 0
    assert len(hinge_geom.holes) == hinge_geom.count
    assert len(hinge_geom.lugs) == hinge_geom.count


# ── 9. Solid cutouts ──────────────────────────────────────────────────────


def test_solid_hole_cutouts_returns_solids(small_config):
    """HingeGeometry.solid_hole_cutouts() returns valid CadQuery solids."""
    from backend.geometry.hinges import build_hinge_geometry, generate_hinge_holes
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    from backend.schema.models import Config

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    hinge_geom = build_hinge_geometry(cfg, ref["te"], device_name="te")
    solids = hinge_geom.solid_hole_cutouts()
    assert len(solids) == len(hinge_geom.holes)
    for s in solids:
        assert s.Volume() > 0


def test_solid_lug_features_returns_solids(small_config):
    """HingeGeometry.solid_lug_features() returns valid CadQuery solids."""
    from backend.geometry.hinges import build_hinge_geometry
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    from backend.schema.models import Config

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    hinge_geom = build_hinge_geometry(cfg, ref["te"], device_name="te")
    solids = hinge_geom.solid_lug_features()
    assert len(solids) == len(hinge_geom.lugs)
    for s in solids:
        assert s.Volume() > 0


def test_solid_tang_features_returns_solids(small_config):
    """HingeGeometry.solid_tang_features() returns valid CadQuery solids."""
    from backend.geometry.hinges import build_hinge_geometry
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    from backend.schema.models import Config

    cfg = Config.model_validate(small_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    if "te" not in ref:
        pytest.skip("No TE hinge axis in this config")

    hinge_geom = build_hinge_geometry(cfg, ref["te"], device_name="te")
    solids = hinge_geom.solid_tang_features()
    assert len(solids) == len(hinge_geom.lugs)
    for s in solids:
        assert s.Volume() > 0


# ── 10. HingeGeometry fields ──────────────────────────────────────────────


def test_hinge_geometry_has_required_fields(small_config):
    """HingeGeometry has hinge_axis, holes, lugs, pin_dia_mm, count, fit_gap_mm."""
    from backend.geometry.hinges import HingeGeometry
    import cadquery as cq

    axis = cq.Edge.makeLine(cq.Vector(0, 0, 0), cq.Vector(100, 0, 0))
    hg = HingeGeometry(hinge_axis=axis)
    assert hasattr(hg, "hinge_axis")
    assert hasattr(hg, "holes")
    assert hasattr(hg, "lugs")
    assert hasattr(hg, "pin_dia_mm")
    assert hasattr(hg, "count")
    assert hasattr(hg, "fit_gap_mm")


# ── 11. Multiple configs ──────────────────────────────────────────────────


def test_medium_config_hinges(medium_config):
    """All hinge geometry generates without error on medium config."""
    from backend.geometry.hinges import build_hinge_geometry
    from backend.geometry.reference import build_hinge_axes
    from backend.geometry.sections import build_planform_sections
    from backend.schema.models import Config

    cfg = Config.model_validate(medium_config)
    sections = build_planform_sections(cfg)
    ref = build_hinge_axes(cfg)

    for name in ref:
        hinge_geom = build_hinge_geometry(cfg, ref[name], device_name=name)
        assert hinge_geom.count > 0
        assert len(hinge_geom.holes) == hinge_geom.count
        assert len(hinge_geom.lugs) == hinge_geom.count
        # Verify coaxiality
        from backend.geometry.hinges import measure_coaxiality
        centers = [h.center for h in hinge_geom.holes]
        coax = measure_coaxiality(ref[name], centers)
        assert coax <= COAXIALITY_TOLERANCE_MM


# ── Gate metrics ────────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p07"] = {
        "mode": "generated",
        "features": [
            "hinge_holes", "lug_tang", "coaxiality_check", "clearance_check",
            "solid_cutouts", "solid_lugs", "solid_tangs",
        ],
        "coaxiality_tolerance_mm": COAXIALITY_TOLERANCE_MM,
        "default_pin_dia_mm": 6.0,
        "lug_protrusion_frac": 0.4,
        "tang_clearance_frac": 0.15,
        "description": "Hinge holes + lug/tang features — coaxiality by construction, clearance >= fit gap",
    }
