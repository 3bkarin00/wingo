"""Joint retention hardware (plan.md P18).

Generates aluminum housings, Z-bolts, tongue clearance holes, upper-skin lip
cutouts, and COTS hinge pockets for bolted spar retention (D8/D10).

P18 pass criteria:
- Bore chain (lip countersink → housing top → tongue clearance hole →
  bottom boss) coaxial within 0.05 mm per bolt
- **Preload-path continuity**: swept bolt-load column from head seat to boss
  intersects aluminum bodies only, never composite
- Lip flushness: flat lip max deviation from local OML ≤ flush_tol_mm
- Tongue holes are clearance fit (Ø_hole − Ø_bolt within configured band)
- Bolt edge distance ≥ 2×Ø from tongue and housing edges
- Housings fully inside IML with bond-gap clearance
- COTS hinge pocket dims match cots_pin_dia_mm + fit params

Usage:
    from backend.geometry.joint_retention import (
        generate_housing,
        generate_z_bolt,
        check_bore_chain_coaxiality,
        check_preload_path_continuity,
        check_lip_flushness,
        check_clearance_fit,
        check_edge_distance,
        generate_cots_hinge_pocket,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq
import numpy as np

from backend.tolerances import COAXIALITY_TOLERANCE_MM, DEFAULT_LIP_FLUSH_TOL_MM


@dataclass
class HousingConfig:
    """Configuration for an aluminum joint housing."""
    side_wall_mm: float = 4.0
    outer_width_mm: float = 30.0
    outer_depth_mm: float = 20.0
    outer_height_mm: float = 15.0
    boss_dia_mm: float = 8.0
    boss_height_mm: float = 3.0
    boss_thread: str = "M5_placeholder"
    lip_mode: str = "flat_capped"
    flush_tol_mm: float = DEFAULT_LIP_FLUSH_TOL_MM
    countersink_angle_deg: float = 82.0
    countersink_dia_mm: float = 10.0


@dataclass
class BoltConfig:
    """Configuration for a Z-bolt."""
    dia_mm: float = 5.0
    length_mm: float = 15.0
    head_dia_mm: float = 9.0
    head_height_mm: float = 3.0
    head_type: str = "countersunk_flush"
    countersink_angle_deg: float = 82.0
    countersink_dia_mm: float = 10.0


@dataclass
class BoreChainResult:
    """Result of bore chain coaxiality check."""
    is_coaxial: bool
    max_deviation_mm: float = 0.0
    bolts_checked: int = 0
    deviations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PreloadPathResult:
    """Result of preload-path continuity check."""
    is_continuous: bool
    intersects_composite: bool = False
    aluminum_only: bool = True
    sweep_volume_mm3: float = 0.0


@dataclass
class LipFlushnessResult:
    """Result of lip flushness check."""
    is_flush: bool
    max_deviation_mm: float = 0.0
    flush_tol_mm: float = DEFAULT_LIP_FLUSH_TOL_MM


@dataclass
class ClearanceFitResult:
    """Result of tongue clearance fit check."""
    is_clearance: bool
    clearance_mm: float = 0.0
    hole_dia_mm: float = 0.0
    bolt_dia_mm: float = 0.0


@dataclass
class EdgeDistanceResult:
    """Result of bolt edge distance check."""
    meets_min_distance: bool
    min_edge_distance_mm: float = 0.0
    required_min_mm: float = 0.0
    violations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class HousingAssembly:
    """Complete joint housing assembly (housing + bolt + clearance holes)."""
    housing: cq.Shape
    bolt: cq.Shape
    clearance_holes: list[cq.Shape] = field(default_factory=list)
    lip_cutouts: list[cq.Shape] = field(default_factory=list)
    name: str = "HOUSING-DEFAULT"


@dataclass
class JointRetentionResult:
    """Result of joint retention generation."""
    assemblies: list[HousingAssembly] = field(default_factory=list)
    bore_chain: BoreChainResult | None = None
    preload_path: PreloadPathResult | None = None
    lip_flushness: LipFlushnessResult | None = None
    clearance_fit: list[ClearanceFitResult] = field(default_factory=list)
    edge_distance: EdgeDistanceResult | None = None
    cots_pockets: list[cq.Shape] = field(default_factory=list)


# ── 1. Housing generation ─────────────────────────────────────────────────


def generate_housing(
    config: HousingConfig,
    name: str = "HOUSING-DEFAULT",
) -> cq.Shape:
    """Generate an aluminum joint housing (sleeve with side walls + boss).

    Creates a hollow box (sleeve) with structural side walls and an integral
    threaded bottom boss.

    Args:
        config: housing configuration parameters.
        name: housing name.

    Returns:
        CadQuery Shape of the housing solid.
    """
    wall = config.side_wall_mm
    ow, od, oh = config.outer_width_mm, config.outer_depth_mm, config.outer_height_mm
    iw = ow - 2 * wall
    id_ = od - 2 * wall

    # Outer box
    outer = cq.Workplane("XY").box(ow, od, oh)

    # Inner void — slightly shorter to leave bottom boss area
    inner = cq.Workplane("XY").box(iw, id_, oh - 0.5)

    # Cut inner from outer → hollow sleeve
    sleeve = outer.cut(inner)

    # Add bottom boss as a cylinder on the bottom face
    boss_cyl = cq.Workplane("XY", origin=(0, 0, -config.boss_height_mm)) \
        .cylinder(config.boss_dia_mm / 2, config.boss_height_mm)
    housing = sleeve.union(boss_cyl)

    return housing.val()


def generate_countersink_lip(
    housing: cq.Shape,
    bolt_config: BoltConfig,
    plate_thickness_mm: float = 3.0,
) -> cq.Shape:
    """Generate a countersunk lip that penetrates the upper skin.

    The lip is a countersunk cone on top of the housing that seats the
    bolt head flush.

    Args:
        housing: the housing shape.
        bolt_config: bolt configuration.
        plate_thickness_mm: thickness of the upper skin plate the lip penetrates.

    Returns:
        CadQuery Shape of the housing with countersink lip.
    """
    # Countersink cone parameters
    angle_rad = np.radians(bolt_config.countersink_angle_deg)
    hole_radius = bolt_config.dia_mm / 2.0
    cs_radius = bolt_config.countersink_dia_mm / 2.0

    # Cone height based on countersink angle
    if cs_radius > hole_radius:
        cone_height = (cs_radius - hole_radius) / np.tan(angle_rad / 2.0)
    else:
        cone_height = 0.0

    # Create countersink cone pointing up from housing top
    if cone_height > 0:
        cs_top = cq.Workplane("XY", origin=(0, 0, plate_thickness_mm)) \
            .cylinder(cs_radius, cone_height).val()
        # Use Shape-level fuse (boolean union)
        result = housing.fuse(cs_top)
    else:
        result = cq.Shape(housing.wrapped)

    return result


# ── 2. Z-bolt generation ──────────────────────────────────────────────────


def generate_z_bolt(
    config: BoltConfig,
    name: str = "ZBOLT-DEFAULT",
) -> cq.Shape:
    """Generate a Z-bolt (countersunk bolt) geometry.

    The bolt consists of a countersunk head and a cylindrical shank.

    Args:
        config: bolt configuration parameters.
        name: bolt name.

    Returns:
        CadQuery Shape of the bolt solid.
    """
    # Bolt head (countersunk)
    head = cq.Workplane("XY").cylinder(config.head_dia_mm / 2, config.head_height_mm)

    # Bolt shank
    shank = cq.Workplane("XY", origin=(0, 0, -config.length_mm)) \
        .cylinder(config.dia_mm / 2, config.length_mm)

    # Union head + shank
    bolt = head.union(shank)
    return bolt.val()


# ── 3. Tongue clearance hole ──────────────────────────────────────────────


def generate_clearance_hole(
    bolt_dia_mm: float,
    clearance_band_mm: tuple[float, float] = (0.5, 1.5),
    length_mm: float = 20.0,
) -> cq.Shape:
    """Generate a tongue clearance hole (clearance fit around bolt).

    The hole diameter is bolt_dia + clearance, where clearance is within
    the configured band.

    Args:
        bolt_dia_mm: bolt shank diameter.
        clearance_band_mm: (min, max) clearance in mm.
        length_mm: hole depth.

    Returns:
        CadQuery Shape of the clearance hole cylinder.
    """
    # Use mid-band clearance
    clearance = (clearance_band_mm[0] + clearance_band_mm[1]) / 2.0
    hole_dia = bolt_dia_mm + clearance

    hole = cq.Workplane("XY").cylinder(hole_dia / 2, length_mm)
    return hole.val()


def check_clearance_fit(
    bolt_dia_mm: float,
    hole_dia_mm: float,
    min_clearance_mm: float = 0.5,
    max_clearance_mm: float = 2.0,
) -> ClearanceFitResult:
    """Check if a tongue hole is a clearance fit (no interference).

    Args:
        bolt_dia_mm: bolt shank diameter.
        hole_dia_mm: hole diameter.
        min_clearance_mm: minimum acceptable clearance.
        max_clearance_mm: maximum acceptable clearance.

    Returns:
        ClearanceFitResult with check findings.
    """
    clearance = hole_dia_mm - bolt_dia_mm
    is_clearance = min_clearance_mm <= clearance <= max_clearance_mm

    return ClearanceFitResult(
        is_clearance=is_clearance,
        clearance_mm=clearance,
        hole_dia_mm=hole_dia_mm,
        bolt_dia_mm=bolt_dia_mm,
    )


# ── 4. Upper-skin lip cutout ──────────────────────────────────────────────


def generate_lip_cutout(
    housing: cq.Shape,
    bolt_config: BoltConfig,
    skin_thickness_mm: float = 3.0,
) -> cq.Shape:
    """Generate upper-skin lip cutout for bolt penetration.

    Creates a countersunk cutout in the upper skin to accommodate the
    bolt head.

    Args:
        housing: the housing shape (for reference).
        bolt_config: bolt configuration.
        skin_thickness_mm: upper skin thickness.

    Returns:
        CadQuery Shape of the cutout.
    """
    return generate_countersink_lip(housing, bolt_config, skin_thickness_mm)


def check_lip_flushness(
    lip_shape: cq.Shape,
    omc_normal: tuple[float, float, float],
    max_deviation_mm: float = DEFAULT_LIP_FLUSH_TOL_MM,
) -> LipFlushnessResult:
    """Check if a flat lip sits flush against local OML.

    Compares the lip normal to the expected OML normal. A flat lip is flush
    if its deviation from the local surface normal is within tolerance.

    For a flat plate, the normal is along the axis of the smallest dimension.

    Args:
        lip_shape: the lip shape.
        omc_normal: expected OML normal direction (x, y, z).
        max_deviation_mm: flushness tolerance.

    Returns:
        LipFlushnessResult with check findings.
    """
    # Compute lip bounding box extents
    bbox = lip_shape.BoundingBox()
    lip_dx = bbox.xmax - bbox.xmin
    lip_dy = bbox.ymax - bbox.ymin
    lip_dz = bbox.zmax - bbox.zmin

    # For a flat plate, the normal is along the axis of the SMALLEST dimension
    if lip_dz <= lip_dx and lip_dz <= lip_dy:
        lip_normal = (0.0, 0.0, 1.0)
    elif lip_dy <= lip_dx:
        lip_normal = (0.0, 1.0, 0.0)
    else:
        lip_normal = (1.0, 0.0, 0.0)

    # Compute deviation from OML normal
    dot_product = (
        lip_normal[0] * omc_normal[0] +
        lip_normal[1] * omc_normal[1] +
        lip_normal[2] * omc_normal[2]
    )
    # Clamp to [-1, 1] for acos safety
    dot_product = max(-1.0, min(1.0, dot_product))
    angle_deg = np.degrees(np.arccos(dot_product))

    # Convert angular deviation to linear deviation at lip radius
    lip_radius = max(lip_dx, lip_dy) / 4.0  # approximate
    linear_deviation = lip_radius * np.sin(np.radians(angle_deg))

    is_flush = linear_deviation <= max_deviation_mm

    return LipFlushnessResult(
        is_flush=is_flush,
        max_deviation_mm=linear_deviation,
        flush_tol_mm=max_deviation_mm,
    )


# ── 5. Bore chain coaxiality ──────────────────────────────────────────────


def check_bore_chain_coaxiality(
    bore_axes: list[tuple[Any, Any]],
    tolerance_mm: float = COAXIALITY_TOLERANCE_MM,
) -> BoreChainResult:
    """Check bore chain coaxiality for all bolts.

    Each bore chain entry is a pair of (gp_Ax1, gp_Ax1) representing two
    cylindrical bore axes that should be coaxial. Coaxiality is measured as
    the maximum offset between the two axes.

    Args:
        bore_axes: list of (axis1, axis2) pairs to check.
        tolerance_mm: maximum allowed coaxiality deviation.

    Returns:
        BoreChainResult with check findings.
    """
    deviations = []
    max_deviation = 0.0

    for i, (axis1, axis2) in enumerate(bore_axes):
        # Extract direction vectors
        dir1 = axis1.Direction()
        dir2 = axis2.Direction()

        # Check angular alignment
        dot = (dir1.X() * dir2.X() + dir1.Y() * dir2.Y() + dir1.Z() * dir2.Z())
        dot = max(-1.0, min(1.0, dot))
        angle_deg = np.degrees(np.arccos(dot))

        # Extract origin points
        origin1 = axis1.Location()
        origin2 = axis2.Location()

        # Perpendicular offset between two lines
        # Project origin2 onto axis1's direction
        dx = origin2.X() - origin1.X()
        dy = origin2.Y() - origin1.Y()
        dz = origin2.Z() - origin1.Z()

        # Distance from origin2 to axis1 line
        # d_perp = |(origin2 - origin1) × direction1|
        cross_x = dy * dir1.Z() - dz * dir1.Y()
        cross_y = dz * dir1.X() - dx * dir1.Z()
        cross_z = dx * dir1.Y() - dy * dir1.X()
        perp_distance = np.sqrt(cross_x ** 2 + cross_y ** 2 + cross_z ** 2)

        deviation = perp_distance
        if deviation > max_deviation:
            max_deviation = deviation

        deviations.append({
            "bolt_index": i,
            "angular_deviation_deg": angle_deg,
            "perpendicular_offset_mm": perp_distance,
        })

    is_coaxial = max_deviation <= tolerance_mm

    return BoreChainResult(
        is_coaxial=is_coaxial,
        max_deviation_mm=max_deviation,
        bolts_checked=len(bore_axes),
        deviations=deviations,
    )


# ── 6. Preload-path continuity ────────────────────────────────────────────


def check_preload_path_continuity(
    bolt_sweep: cq.Shape,
    aluminum_bodies: list[cq.Shape],
    composite_bodies: list[cq.Shape] | None = None,
) -> PreloadPathResult:
    """Check that the bolt preload path intersects aluminum bodies only.

    The swept bolt-load column (cylinder from head seat to boss bottom)
    must intersect aluminum bodies only, never composite.

    Args:
        bolt_sweep: the swept cylinder representing the bolt load column.
        aluminum_bodies: list of aluminum body shapes.
        composite_bodies: list of composite body shapes (optional).

    Returns:
        PreloadPathResult with check findings.
    """
    sweep_volume = bolt_sweep.Volume()

    # Check intersection with composite bodies
    intersects_composite = False
    if composite_bodies:
        for comp_body in composite_bodies:
            try:
                # Use CadQuery .intersect() for boolean intersection
                intersection = bolt_sweep.intersect(comp_body)
                if not intersection.isNull() and intersection.Volume() > 1e-6:
                    intersects_composite = True
                    break
            except Exception:
                intersects_composite = True
                break

    # Check intersection with aluminum bodies (must intersect at least one)
    intersects_aluminum = False
    for al_body in aluminum_bodies:
        try:
            # Use CadQuery .intersect() for boolean intersection
            intersection = bolt_sweep.intersect(al_body)
            if not intersection.isNull() and intersection.Volume() > 1e-6:
                intersects_aluminum = True
                break
        except Exception:
            continue

    is_continuous = intersects_aluminum and not intersects_composite

    return PreloadPathResult(
        is_continuous=is_continuous,
        intersects_composite=intersects_composite,
        aluminum_only=not intersects_composite,
        sweep_volume_mm3=sweep_volume,
    )


# ── 7. Bolt edge distance ─────────────────────────────────────────────────


def check_edge_distance(
    bolt_centers: list[tuple[float, float]],
    tongue_edges: list[tuple[float, float]],
    housing_edges: list[tuple[float, float]],
    bolt_dia_mm: float,
    min_edge_distance_factor: float = 2.0,
) -> EdgeDistanceResult:
    """Check that bolt edge distance ≥ 2×Ø from tongue and housing edges.

    Args:
        bolt_centers: list of (x, y) bolt center positions.
        tongue_edges: list of (x, y) points along tongue edges.
        housing_edges: list of (x, y) points along housing edges.
        bolt_dia_mm: bolt diameter.
        min_edge_distance_factor: minimum edge distance as multiple of bolt dia.

    Returns:
        EdgeDistanceResult with check findings.
    """
    min_required = min_edge_distance_factor * bolt_dia_mm
    min_distance = float("inf")
    violations = []

    for bx, by in bolt_centers:
        # Distance to tongue edges
        for tx, ty in tongue_edges:
            dist = np.sqrt((bx - tx) ** 2 + (by - ty) ** 2)
            if dist < min_distance:
                min_distance = dist
            if dist < min_required:
                violations.append({
                    "type": "tongue_edge",
                    "bolt": (bx, by),
                    "edge": (tx, ty),
                    "distance_mm": dist,
                })

        # Distance to housing edges
        for hx, hy in housing_edges:
            dist = np.sqrt((bx - hx) ** 2 + (by - hy) ** 2)
            if dist < min_distance:
                min_distance = dist
            if dist < min_required:
                violations.append({
                    "type": "housing_edge",
                    "bolt": (bx, by),
                    "edge": (hx, hy),
                    "distance_mm": dist,
                })

    if min_distance == float("inf"):
        min_distance = 0.0

    meets_min = min_distance >= min_required and len(violations) == 0

    return EdgeDistanceResult(
        meets_min_distance=meets_min,
        min_edge_distance_mm=min_distance,
        required_min_mm=min_required,
        violations=violations,
    )


# ── 8. COTS hinge pocket mode ─────────────────────────────────────────────


def generate_cots_hinge_pocket(
    cots_pin_dia_mm: float,
    fit_gap_mm: float = 0.1,
    pocket_depth_mm: float = 10.0,
    pocket_width_mm: float = 12.0,
) -> cq.Shape:
    """Generate a COTS hinge pocket for a cylindrical pin.

    Creates a counterbore pocket that accepts a COTS hinge pin with
    the specified fit gap. Built as a solid block with bores using
    OCP boolean operations (not CadQuery stack-based cut).

    Args:
        cots_pin_dia_mm: COTS hinge pin diameter.
        fit_gap_mm: clearance fit gap around the pin.
        pocket_depth_mm: pocket depth.
        pocket_width_mm: pocket width (slightly larger than pin for insertion).

    Returns:
        CadQuery Shape of the hinge pocket.
    """
    pin_dia_with_gap = cots_pin_dia_mm + fit_gap_mm

    # Base block
    base = cq.Workplane("XY").box(pocket_width_mm, pocket_width_mm, pocket_depth_mm).val()

    # Pin bore cylinder (going through entire depth)
    pin_bore = cq.Workplane("XY", origin=(0, 0, 0)) \
        .cylinder(pin_dia_with_gap / 2, pocket_depth_mm).val()

    # Counterbore for hinge head (wider, shallower)
    cbore_dia = pocket_width_mm
    cbore_depth = 3.0
    cbore = cq.Workplane("XY", origin=(0, 0, 0)) \
        .cylinder(cbore_dia / 2, cbore_depth).val()

    # Boolean subtract both bores from base
    result = base.cut(pin_bore)
    result = result.cut(cbore)

    return result


# ── 9. Full assembly generation ───────────────────────────────────────────


def generate_joint_retention_assembly(
    housing_config: HousingConfig,
    bolt_config: BoltConfig,
    name: str = "JOINT-RETENTION",
) -> HousingAssembly:
    """Generate a complete joint retention assembly.

    Creates the housing with countersink lip, Z-bolt, and clearance holes.

    Args:
        housing_config: housing configuration.
        bolt_config: bolt configuration.
        name: assembly name.

    Returns:
        HousingAssembly with all components.
    """
    # Generate housing
    housing = generate_housing(housing_config, name=f"{name}-HOUSING")

    # Add countersink lip
    housing_with_lip = generate_countersink_lip(housing, bolt_config)

    # Generate bolt
    bolt = generate_z_bolt(bolt_config, name=f"{name}-BOLT")

    # Generate clearance hole
    clearance = generate_clearance_hole(bolt_config.dia_mm)

    return HousingAssembly(
        housing=housing_with_lip,
        bolt=bolt,
        clearance_holes=[clearance],
        name=name,
    )


def generate_joint_retention_for_body(
    housing_configs: list[HousingConfig],
    bolt_config: BoltConfig,
    body_name: str = "WING",
) -> JointRetentionResult:
    """Generate joint retention hardware for a structural body.

    Args:
        housing_configs: list of housing configurations (one per bolt station).
        bolt_config: bolt configuration.
        body_name: source body name.

    Returns:
        JointRetentionResult with all assemblies and checks.
    """
    assemblies = []
    clearance_results = []

    for i, h_config in enumerate(housing_configs):
        assembly = generate_joint_retention_assembly(
            h_config, bolt_config,
            name=f"{body_name}-JOINT-{i}",
        )
        assemblies.append(assembly)

        # Check clearance fit
        clearance = check_clearance_fit(
            bolt_config.dia_mm,
            bolt_config.countersink_dia_mm,
        )
        clearance_results.append(clearance)

    return JointRetentionResult(
        assemblies=assemblies,
        clearance_fit=clearance_results,
    )
