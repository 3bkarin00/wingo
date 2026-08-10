"""Gate P18 — Joint retention hardware.

Plan.md P18 pass criteria:
- Bore chain coaxial within 0.05 mm per bolt
- Preload-path continuity: swept bolt-load column intersects aluminum only
- Lip flushness: flat lip max deviation from local OML ≤ flush_tol_mm
- Tongue holes are clearance fit (Ø_hole − Ø_bolt within configured band)
- Bolt edge distance ≥ 2×Ø from tongue and housing edges
- Housings fully inside IML with bond-gap clearance
- COTS hinge pocket dims match cots_pin_dia_mm + fit params

Tests:
1. Module loads with all functions and classes
2. Housing generation produces valid solid
3. Z-bolt generation produces valid solid
4. Countersink lip generation
5. Clearance hole generation
6. Bore chain coaxiality check (pass)
7. Bore chain coaxiality check (fail)
8. Preload-path continuity (aluminum-only)
9. Preload-path continuity (intersects composite → fail)
10. Lip flushness (flush)
11. Lip flushness (not flush)
12. Clearance fit (pass)
13. Clearance fit (interference)
14. Edge distance (meets minimum)
15. Edge distance (violation)
16. COTS hinge pocket generation
17. Full assembly generation
18. BoreChainResult has all required fields
19. PreloadPathResult has all required fields
20. LipFlushnessResult has all required fields
21. ClearanceFitResult has all required fields
22. EdgeDistanceResult has all required fields
23. HousingAssembly has all required fields
24. JointRetentionResult has all required fields
25. generate_joint_retention_for_body produces multiple assemblies
"""
from __future__ import annotations

import cadquery as cq
import pytest

from backend.tolerances import COAXIALITY_TOLERANCE_MM, DEFAULT_LIP_FLUSH_TOL_MM


# ── 1. Module loads ───────────────────────────────────────────────────────


def test_joint_retention_module_loads():
    """Joint retention module loads with all functions and classes."""
    from backend.geometry.joint_retention import (
        generate_housing,
        generate_z_bolt,
        generate_clearance_hole,
        check_clearance_fit,
        check_bore_chain_coaxiality,
        check_preload_path_continuity,
        check_lip_flushness,
        check_edge_distance,
        generate_cots_hinge_pocket,
        generate_joint_retention_assembly,
        generate_joint_retention_for_body,
        HousingConfig,
        BoltConfig,
        BoreChainResult,
        PreloadPathResult,
        LipFlushnessResult,
        ClearanceFitResult,
        EdgeDistanceResult,
        HousingAssembly,
        JointRetentionResult,
    )

    assert callable(generate_housing)
    assert callable(generate_z_bolt)
    assert callable(generate_clearance_hole)
    assert callable(check_clearance_fit)
    assert callable(check_bore_chain_coaxiality)
    assert callable(check_preload_path_continuity)
    assert callable(check_lip_flushness)
    assert callable(check_edge_distance)
    assert callable(generate_cots_hinge_pocket)
    assert callable(generate_joint_retention_assembly)
    assert callable(generate_joint_retention_for_body)


# ── 2. Housing generation ─────────────────────────────────────────────────


def test_generate_housing():
    """generate_housing produces a valid solid with expected volume."""
    from backend.geometry.joint_retention import HousingConfig, generate_housing

    config = HousingConfig(
        side_wall_mm=4.0,
        outer_width_mm=30.0,
        outer_depth_mm=20.0,
        outer_height_mm=15.0,
    )
    housing = generate_housing(config)

    assert housing is not None
    assert not housing.isNull()
    assert housing.Volume() > 0
    # Outer = 30*20*15 = 9000, inner ≈ 22*12*14.5 = 3828, boss ≈ 150
    # Expected ≈ 9000 - 3828 + 150 ≈ 5322
    assert 4000 < housing.Volume() < 6000


# ── 3. Z-bolt generation ──────────────────────────────────────────────────


def test_generate_z_bolt():
    """generate_z_bolt produces a valid solid."""
    from backend.geometry.joint_retention import BoltConfig, generate_z_bolt

    config = BoltConfig(dia_mm=5.0, length_mm=15.0)
    bolt = generate_z_bolt(config)

    assert bolt is not None
    assert not bolt.isNull()
    assert bolt.Volume() > 0


# ── 4. Countersink lip generation ─────────────────────────────────────────


def test_countersink_lip():
    """generate_countersink_lip creates a lip on the housing."""
    from backend.geometry.joint_retention import (
        HousingConfig, BoltConfig, generate_housing, generate_countersink_lip,
    )

    config = HousingConfig()
    bolt_config = BoltConfig()
    housing = generate_housing(config)
    lip = generate_countersink_lip(housing, bolt_config)

    assert lip is not None
    assert not lip.isNull()
    # Lip should be larger than housing (adds cone on top)
    assert lip.Volume() >= housing.Volume()


# ── 5. Clearance hole generation ──────────────────────────────────────────


def test_clearance_hole():
    """generate_clearance_hole produces a cylinder with correct diameter."""
    from backend.geometry.joint_retention import generate_clearance_hole

    hole = generate_clearance_hole(
        5.0, clearance_band_mm=(0.5, 1.5), length_mm=20.0
    )

    assert hole is not None
    assert not hole.isNull()
    assert hole.Volume() > 0


# ── 6. Bore chain coaxiality — pass ───────────────────────────────────────


def test_bore_chain_coaxiality_pass():
    """Bore chain coaxiality check passes for coincident axes."""
    from backend.geometry.joint_retention import check_bore_chain_coaxiality
    from OCP.gp import gp_Pnt, gp_Ax1, gp_Dir

    axis1 = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    axis2 = gp_Ax1(gp_Pnt(0, 0, 1), gp_Dir(0, 0, 1))

    result = check_bore_chain_coaxiality([(axis1, axis2)])

    assert result.is_coaxial == True
    assert result.max_deviation_mm == 0.0
    assert result.bolts_checked == 1


# ── 7. Bore chain coaxiality — fail ───────────────────────────────────────


def test_bore_chain_coaxiality_fail():
    """Bore chain coaxiality check fails when deviation > tolerance."""
    from backend.geometry.joint_retention import check_bore_chain_coaxiality
    from OCP.gp import gp_Pnt, gp_Ax1, gp_Dir

    axis1 = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    axis2 = gp_Ax1(gp_Pnt(0.1, 0, 0), gp_Dir(0, 0, 1))

    result = check_bore_chain_coaxiality([(axis1, axis2)], tolerance_mm=0.05)

    assert result.is_coaxial == False
    assert result.max_deviation_mm >= 0.1
    assert result.bolts_checked == 1
    assert len(result.deviations) == 1


# ── 8. Preload-path continuity — aluminum only ───────────────────────────


def test_preload_path_aluminum_only():
    """Preload-path continuity passes when sweep intersects aluminum only."""
    from backend.geometry.joint_retention import check_preload_path_continuity

    sweep = cq.Workplane("XY").cylinder(3, 10).val()
    al_body = cq.Workplane("XY").box(10, 10, 10).val()

    result = check_preload_path_continuity(sweep, [al_body], [])

    assert result.is_continuous == True
    assert result.aluminum_only == True
    assert result.intersects_composite == False
    assert result.sweep_volume_mm3 > 0


# ── 9. Preload-path continuity — intersects composite ────────────────────


def test_preload_path_intersects_composite():
    """Preload-path continuity fails when sweep intersects composite."""
    from backend.geometry.joint_retention import check_preload_path_continuity

    sweep = cq.Workplane("XY").cylinder(3, 10).val()
    al_body = cq.Workplane("XY").box(10, 10, 5).val()
    comp_body = cq.Workplane("XY").box(10, 10, 5).val()

    result = check_preload_path_continuity(sweep, [al_body], [comp_body])

    assert result.is_continuous == False
    assert result.intersects_composite == True
    assert result.aluminum_only == False


# ── 10. Lip flushness — flush ─────────────────────────────────────────────


def test_lip_flushness_flush():
    """Lip flushness check passes when lip normal matches OML normal."""
    from backend.geometry.joint_retention import (
        HousingConfig, BoltConfig, generate_housing, generate_countersink_lip,
        check_lip_flushness,
    )

    config = HousingConfig()
    bolt_config = BoltConfig()
    housing = generate_housing(config)
    lip = generate_countersink_lip(housing, bolt_config)

    result = check_lip_flushness(lip, (0.0, 0.0, 1.0))

    assert result.is_flush == True
    assert result.max_deviation_mm <= result.flush_tol_mm


# ── 11. Lip flushness — not flush ─────────────────────────────────────────


def test_lip_flushness_not_flush():
    """Lip flushness check fails when lip normal deviates significantly."""
    from backend.geometry.joint_retention import (
        HousingConfig, BoltConfig, generate_housing, generate_countersink_lip,
        check_lip_flushness,
    )

    config = HousingConfig()
    bolt_config = BoltConfig()
    housing = generate_housing(config)
    lip = generate_countersink_lip(housing, bolt_config)

    result = check_lip_flushness(lip, (1.0, 0.0, 0.0))

    assert result.is_flush == False


# ── 12. Clearance fit — pass ──────────────────────────────────────────────


def test_clearance_fit_pass():
    """Clearance fit check passes for acceptable clearance."""
    from backend.geometry.joint_retention import check_clearance_fit

    result = check_clearance_fit(bolt_dia_mm=5.0, hole_dia_mm=6.0)

    assert result.is_clearance == True
    assert result.clearance_mm == 1.0
    assert result.hole_dia_mm == 6.0
    assert result.bolt_dia_mm == 5.0


# ── 13. Clearance fit — interference ──────────────────────────────────────


def test_clearance_fit_interference():
    """Clearance fit check fails for interference (hole < bolt)."""
    from backend.geometry.joint_retention import check_clearance_fit

    result = check_clearance_fit(bolt_dia_mm=5.0, hole_dia_mm=4.0)

    assert result.is_clearance == False
    assert result.clearance_mm == -1.0


# ── 14. Edge distance — meets minimum ─────────────────────────────────────


def test_edge_distance_meets_minimum():
    """Edge distance check passes when all bolts ≥ 2×Ø from edges."""
    from backend.geometry.joint_retention import check_edge_distance

    bolt_centers = [(10.0, 10.0)]
    tongue_edges = [(0.0, 0.0), (5.0, 0.0)]
    housing_edges = [(0.0, 0.0), (0.0, 5.0)]

    result = check_edge_distance(
        bolt_centers, tongue_edges, housing_edges,
        bolt_dia_mm=5.0, min_edge_distance_factor=2.0,
    )

    assert result.meets_min_distance == True
    assert result.required_min_mm == 10.0


# ── 15. Edge distance — violation ─────────────────────────────────────────


def test_edge_distance_violation():
    """Edge distance check fails when bolt too close to edge."""
    from backend.geometry.joint_retention import check_edge_distance

    bolt_centers = [(1.0, 1.0)]
    tongue_edges = [(0.0, 0.0)]
    housing_edges = [(0.0, 0.0)]

    result = check_edge_distance(
        bolt_centers, tongue_edges, housing_edges,
        bolt_dia_mm=5.0, min_edge_distance_factor=2.0,
    )

    assert result.meets_min_distance == False
    assert len(result.violations) > 0
    assert result.required_min_mm == 10.0


# ── 16. COTS hinge pocket ─────────────────────────────────────────────────


def test_cots_hinge_pocket():
    """generate_cots_hinge_pocket produces a valid pocket."""
    from backend.geometry.joint_retention import generate_cots_hinge_pocket

    pocket = generate_cots_hinge_pocket(
        cots_pin_dia_mm=6.0,
        fit_gap_mm=0.1,
    )

    assert pocket is not None
    assert not pocket.isNull()
    assert pocket.Volume() > 0


# ── 17. Full assembly generation ──────────────────────────────────────────


def test_generate_assembly():
    """generate_joint_retention_assembly produces a complete assembly."""
    from backend.geometry.joint_retention import (
        HousingConfig, BoltConfig, generate_joint_retention_assembly,
    )

    h_config = HousingConfig()
    b_config = BoltConfig()
    assembly = generate_joint_retention_assembly(h_config, b_config)

    assert assembly.housing is not None
    assert not assembly.housing.isNull()
    assert assembly.bolt is not None
    assert not assembly.bolt.isNull()
    assert len(assembly.clearance_holes) > 0
    assert assembly.name != ""


# ── 18. BoreChainResult fields ────────────────────────────────────────────


def test_bore_chain_result_fields():
    """BoreChainResult has all required fields."""
    from backend.geometry.joint_retention import BoreChainResult

    result = BoreChainResult(is_coaxial=True, max_deviation_mm=0.0)
    assert hasattr(result, "is_coaxial")
    assert hasattr(result, "max_deviation_mm")
    assert hasattr(result, "bolts_checked")
    assert hasattr(result, "deviations")


# ── 19. PreloadPathResult fields ──────────────────────────────────────────


def test_preload_path_result_fields():
    """PreloadPathResult has all required fields."""
    from backend.geometry.joint_retention import PreloadPathResult

    result = PreloadPathResult(is_continuous=True)
    assert hasattr(result, "is_continuous")
    assert hasattr(result, "intersects_composite")
    assert hasattr(result, "aluminum_only")
    assert hasattr(result, "sweep_volume_mm3")


# ── 20. LipFlushnessResult fields ─────────────────────────────────────────


def test_lip_flushness_result_fields():
    """LipFlushnessResult has all required fields."""
    from backend.geometry.joint_retention import LipFlushnessResult

    result = LipFlushnessResult(is_flush=True)
    assert hasattr(result, "is_flush")
    assert hasattr(result, "max_deviation_mm")
    assert hasattr(result, "flush_tol_mm")


# ── 21. ClearanceFitResult fields ─────────────────────────────────────────


def test_clearance_fit_result_fields():
    """ClearanceFitResult has all required fields."""
    from backend.geometry.joint_retention import ClearanceFitResult

    result = ClearanceFitResult(is_clearance=True)
    assert hasattr(result, "is_clearance")
    assert hasattr(result, "clearance_mm")
    assert hasattr(result, "hole_dia_mm")
    assert hasattr(result, "bolt_dia_mm")


# ── 22. EdgeDistanceResult fields ─────────────────────────────────────────


def test_edge_distance_result_fields():
    """EdgeDistanceResult has all required fields."""
    from backend.geometry.joint_retention import EdgeDistanceResult

    result = EdgeDistanceResult(meets_min_distance=True)
    assert hasattr(result, "meets_min_distance")
    assert hasattr(result, "min_edge_distance_mm")
    assert hasattr(result, "required_min_mm")
    assert hasattr(result, "violations")


# ── 23. HousingAssembly fields ────────────────────────────────────────────


def test_housing_assembly_fields():
    """HousingAssembly has all required fields."""
    from backend.geometry.joint_retention import HousingAssembly

    assembly = HousingAssembly(
        housing=cq.Workplane("XY").box(1, 1, 1).val(),
        bolt=cq.Workplane("XY").box(1, 1, 1).val(),
    )
    assert hasattr(assembly, "housing")
    assert hasattr(assembly, "bolt")
    assert hasattr(assembly, "clearance_holes")
    assert hasattr(assembly, "lip_cutouts")
    assert hasattr(assembly, "name")


# ── 24. JointRetentionResult fields ───────────────────────────────────────


def test_joint_retention_result_fields():
    """JointRetentionResult has all required fields."""
    from backend.geometry.joint_retention import JointRetentionResult

    result = JointRetentionResult()
    assert hasattr(result, "assemblies")
    assert hasattr(result, "bore_chain")
    assert hasattr(result, "preload_path")
    assert hasattr(result, "lip_flushness")
    assert hasattr(result, "clearance_fit")
    assert hasattr(result, "edge_distance")
    assert hasattr(result, "cots_pockets")


# ── 25. generate_joint_retention_for_body ─────────────────────────────────


def test_generate_for_body():
    """generate_joint_retention_for_body produces multiple assemblies."""
    from backend.geometry.joint_retention import (
        HousingConfig, BoltConfig, generate_joint_retention_for_body,
    )

    configs = [
        HousingConfig(outer_width_mm=30.0),
        HousingConfig(outer_width_mm=25.0),
    ]
    bolt_config = BoltConfig()

    result = generate_joint_retention_for_body(configs, bolt_config, "WING-TEST")

    assert len(result.assemblies) == 2
    assert len(result.clearance_fit) == 2
    assert all(a.name.startswith("WING-TEST") for a in result.assemblies)


# ── Gate metrics ──────────────────────────────────────────────────────────


def test_phase_metrics(gate_metrics):
    """Record phase metrics for the gate artifact."""
    gate_metrics["p18"] = {
        "joint_retention": "Aluminum housings, Z-bolts, preload path, COTS hinge pockets",
        "checks": [
            "bore chain coaxial within 0.05 mm per bolt",
            "preload-path continuity: swept bolt-load column intersects aluminum only",
            "lip flushness: flat lip max deviation from local OML ≤ flush_tol_mm",
            "tongue holes are clearance fit (Ø_hole − Ø_bolt within configured band)",
            "bolt edge distance ≥ 2×Ø from tongue and housing edges",
            "housings fully inside IML with bond-gap clearance",
            "COTS hinge pocket dims match cots_pin_dia_mm + fit params",
        ],
        "functions": [
            "generate_housing",
            "generate_z_bolt",
            "generate_countersink_lip",
            "generate_clearance_hole",
            "generate_lip_cutout",
            "check_bore_chain_coaxiality",
            "check_preload_path_continuity",
            "check_lip_flushness",
            "check_clearance_fit",
            "check_edge_distance",
            "generate_cots_hinge_pocket",
            "generate_joint_retention_assembly",
            "generate_joint_retention_for_body",
        ],
        "description": "Joint retention hardware — aluminum housings, Z-bolts, preload path",
    }
