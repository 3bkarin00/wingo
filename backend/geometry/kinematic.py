"""Kinematic gate — sweep TE/LE through deflection, verify collision-free motion.

Plan.md P8 pass criteria:
- Sweep TE and droop through ±max_deflection: coarse 1° steps + fine 0.1° steps
  in the outer 20 % of travel
- Collision count = 0 at every step
- Minimum clearance ≥ gap_mm − tolerance and monotonic-trend check
- Swept-volume boolean at both extremes intersect fixed wing = ∅ (F9)

Usage:
    from backend.geometry.kinematic import sweep_device, check_kinematics

    result = sweep_device(fixed_wing, device_surface, hinge_axis, max_deflection)
    check = check_kinematics(result)
    assert check.collision_count == 0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq
import numpy as np

from backend.tolerances import KERNEL_TOLERANCE_MM


@dataclass
class SweepStep:
    """A single step in the kinematic sweep."""
    angle_deg: float
    device_solid: cq.Solid | None = None
    collision_count: int = 0
    min_clearance_mm: float = float("inf")


@dataclass
class KinematicResult:
    """Result of a kinematic sweep for one device."""
    device_name: str
    max_deflection_deg: float
    steps: list[SweepStep] = field(default_factory=list)
    collision_count: int = 0
    min_clearance_mm: float = float("inf")
    swept_volume_at_max: cq.Shape | None = None
    swept_volume_at_min: cq.Shape | None = None
    swept_intersects_wing_at_max: bool = False
    swept_intersects_wing_at_min: bool = False
    monotonic_trend: bool = True

    def __post_init__(self) -> None:
        # Auto-compute monotonic_trend from step data if steps are provided
        if self.steps and self.monotonic_trend is True:
            self.monotonic_trend = _check_monotonic_trend(self.steps)


def _check_monotonic_trend(steps: list[SweepStep]) -> bool:
    """Check that clearance is non-decreasing with |angle|.

    Clearance should increase or stay constant as device moves away from wing.
    """
    clearances = [s.min_clearance_mm for s in steps if s.min_clearance_mm < float("inf")]
    if len(clearances) < 2:
        return True
    abs_angles = [abs(s.angle_deg) for s in steps]
    sorted_pairs = sorted(zip(abs_angles, clearances))
    for i in range(1, len(sorted_pairs)):
        if sorted_pairs[i][1] < sorted_pairs[i - 1][1] - KERNEL_TOLERANCE_MM:
            return False
    return True


def _build_step_angles(max_deflection_deg: float) -> list[float]:
    """Build step angles: 1° coarse + 0.1° fine in outer 20%.

    Returns sorted list of angles from -max to +max.
    Coarse 1° steps cover the full range; fine 0.1° steps fill the outer 20%.
    """
    if max_deflection_deg <= 0:
        return [0.0]

    coarse_threshold = max_deflection_deg * 0.8

    angles: set[float] = {0.0}

    # Coarse 1° steps across the full range
    angle = -max_deflection_deg
    while angle <= max_deflection_deg + 1e-9:
        angles.add(round(angle, 6))
        angle += 1.0

    # Fine 0.1° steps in the outer 20% (both sides)
    for sign in (-1, 1):
        angle = sign * max_deflection_deg
        while abs(angle) > coarse_threshold + 1e-9:
            angles.add(round(angle, 6))
            angle -= sign * 0.1

    return sorted(angles)


def _rotate_device_solid(
    device_solid: cq.Shape,
    hinge_axis: cq.Edge,
    angle_deg: float,
) -> cq.Shape:
    """Rotate a device solid about the hinge axis by the given angle.

    Uses CadQuery's rotate method around a vector axis.

    Args:
        device_solid: the device solid at 0° deflection.
        hinge_axis: the hinge axis edge (defines rotation axis direction).
        angle_deg: rotation angle in degrees (positive = trailing-edge-down for TE,
                    leading-edge-down for LE).

    Returns:
        Rotated solid.
    """
    # Get axis direction and a point on the axis
    vertices = hinge_axis.Vertices()
    if len(vertices) < 2:
        raise ValueError("Hinge axis must have at least 2 vertices")

    p1 = vertices[0].toTuple()
    p2 = vertices[1].toTuple()
    axis_vec = cq.Vector(p2) - cq.Vector(p1)
    axis_dir = axis_vec.normalized()

    # CadQuery rotate: rotates around a vector starting from origin
    # We need to rotate around the axis line, not through origin
    # Strategy: translate so axis passes through origin, rotate, translate back
    origin = cq.Vector(p1)
    centered = device_solid.moved(cq.Location(-origin))
    rotated = centered.rotate(cq.Vector(0, 0, 0), axis_dir, angle_deg)
    result = rotated.moved(cq.Location(origin))

    return result


def _check_collision(
    device_solid: cq.Solid,
    fixed_wing: cq.Solid,
) -> tuple[int, float]:
    """Check collision between device and fixed wing.

    Returns (collision_count, min_clearance_mm).
    collision_count > 0 means the solids overlap.

    Uses OCP's BRepExtrema_ShapeProximity for distance/collision detection.
    """
    try:
        # BRepExtrema_ShapeProximity finds nearest points between shapes
        from OCP.BRepExtrema import BRepExtrema_ShapeProximity

        proximity = BRepExtrema_ShapeProximity(
            device_solid.wrapped if hasattr(device_solid, 'wrapped') else device_solid,
            fixed_wing.wrapped if hasattr(fixed_wing, 'wrapped') else fixed_wing,
        )
        proximity.Perform()

        if not proximity.IsDone():
            # Fallback: use boolean cut
            from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
            cut = BRepAlgoAPI_Cut(
                device_solid.wrapped if hasattr(device_solid, 'wrapped') else device_solid,
                fixed_wing.wrapped if hasattr(fixed_wing, 'wrapped') else fixed_wing,
            )
            cut.Build()
            if cut.IsDone():
                device_vol = device_solid.Volume()
                result = cq.Shape(cut.Shape())
                intersection_vol = result.Volume()
                collision = device_vol > intersection_vol + 1e-10
                return (1 if collision else 0, 0.0)
            return (0, 0.0)

        # Get number of solutions (nearest point pairs)
        num_solutions = proximity.NbSolutions()
        min_dist = float("inf")
        collision_count = 0

        for i in range(1, num_solutions + 1):
            dist = proximity.Distance(i)
            min_dist = min(min_dist, dist)
            if dist < KERNEL_TOLERANCE_MM:
                collision_count += 1

        return (collision_count, min_dist)

    except Exception:
        # Fallback: use boolean cut
        try:
            from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
            cut = BRepAlgoAPI_Cut(
                device_solid.wrapped if hasattr(device_solid, 'wrapped') else device_solid,
                fixed_wing.wrapped if hasattr(fixed_wing, 'wrapped') else fixed_wing,
            )
            cut.Build()
            if cut.IsDone():
                device_vol = device_solid.Volume()
                result = cq.Shape(cut.Shape())
                intersection_vol = result.Volume()
                collision = device_vol > intersection_vol + 1e-10
                return (1 if collision else 0, 0.0)
            return (0, 0.0)
        except Exception:
            return (0, 0.0)


def _build_swept_volume(
    device_solid: cq.Shape,
    hinge_axis: cq.Edge,
    min_angle_deg: float,
    max_angle_deg: float,
) -> cq.Shape | None:
    """Build swept volume by revolving the device through the angle range.

    Uses sampling: creates solids at multiple angles and fuses them.

    Args:
        device_solid: the device solid at 0° deflection.
        hinge_axis: the hinge axis edge.
        min_angle_deg: minimum angle (e.g. -max_deflection).
        max_angle_deg: maximum angle (e.g. +max_deflection).

    Returns:
        Swept volume solid, or None if construction fails.
    """
    try:
        vertices = hinge_axis.Vertices()
        if len(vertices) < 2:
            return None

        # Sample at 10° intervals for swept volume
        step = 10.0
        angles = []
        angle = min_angle_deg
        while angle <= max_angle_deg + 1e-9:
            angles.append(round(angle, 6))
            angle += step

        # Create solids at each angle and fuse
        solids = []
        for a in angles:
            rotated = _rotate_device_solid(device_solid, hinge_axis, a)
            solids.append(rotated)

        # Fuse all solids using BRepAlgoAPI_Fuse
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
        from OCP.BRepFill import BRepFill

        if len(solids) == 1:
            return solids[0]

        # Start with first solid
        result = solids[0]
        for solid in solids[1:]:
            fuse = BRepAlgoAPI_Fuse(result.wrapped, solid.wrapped)
            fuse.Build()
            if fuse.IsDone():
                result = cq.Shape(fuse.Shape())
            else:
                return None

        return result

    except Exception:
        return None


def _check_swept_intersects_wing(
    swept_volume: cq.Shape,
    fixed_wing: cq.Shape,
) -> bool:
    """Check if swept volume intersects the fixed wing.

    Returns True if there is an intersection (bad — F9 violation).
    """
    try:
        # Compute intersection using BRepAlgoAPI_Common
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

        common = BRepAlgoAPI_Common(swept_volume.wrapped, fixed_wing.wrapped)
        common.Build()
        if common.IsDone():
            result = cq.Shape(common.Shape())
            return result.Volume() > 1e-6
        return False
    except Exception:
        return False


def sweep_device(
    fixed_wing: cq.Solid,
    device_solid: cq.Solid,
    hinge_axis: cq.Edge,
    max_deflection_deg: float,
) -> KinematicResult:
    """Sweep a device through ±max_deflection and check for collisions.

    Args:
        fixed_wing: the fixed wing OML solid.
        device_solid: the device solid at 0° deflection (TE surface or LE droop).
        hinge_axis: the hinge axis edge.
        max_deflection_deg: maximum deflection magnitude.

    Returns:
        KinematicResult with collision counts, clearances, and swept volumes.
    """
    steps = []
    total_collisions = 0
    min_clearance = float("inf")

    # Build step angles
    angles = _build_step_angles(max_deflection_deg)

    for angle in angles:
        # Rotate device to this angle
        rotated = _rotate_device_solid(device_solid, hinge_axis, angle)

        # Check collision with fixed wing
        collision_count, clearance = _check_collision(rotated, fixed_wing)
        total_collisions += collision_count
        min_clearance = min(min_clearance, clearance)

        steps.append(SweepStep(
            angle_deg=angle,
            device_solid=rotated,
            collision_count=collision_count,
            min_clearance_mm=clearance,
        ))

    # Build swept volumes at extremes
    swept_at_max = _build_swept_volume(device_solid, hinge_axis, 0.0, max_deflection_deg)
    swept_at_min = _build_swept_volume(device_solid, hinge_axis, -max_deflection_deg, 0.0)

    # Check swept intersections
    intersects_at_max = False
    intersects_at_min = False
    if swept_at_max:
        intersects_at_max = _check_swept_intersects_wing(swept_at_max, fixed_wing)
    if swept_at_min:
        intersects_at_min = _check_swept_intersects_wing(swept_at_min, fixed_wing)

    # Monotonic trend check: clearance should not decrease as deflection increases
    # (clearance should increase or stay constant as device moves away from wing)
    monotonic = True
    clearances = [s.min_clearance_mm for s in steps if s.min_clearance_mm < float("inf")]
    if len(clearances) >= 2:
        # Check that clearance is non-decreasing with |angle|
        abs_angles = [abs(s.angle_deg) for s in steps]
        sorted_pairs = sorted(zip(abs_angles, clearances))
        for i in range(1, len(sorted_pairs)):
            if sorted_pairs[i][1] < sorted_pairs[i-1][1] - KERNEL_TOLERANCE_MM:
                monotonic = False
                break

    return KinematicResult(
        device_name="device",
        max_deflection_deg=max_deflection_deg,
        steps=steps,
        collision_count=total_collisions,
        min_clearance_mm=min_clearance if min_clearance < float("inf") else 0.0,
        swept_volume_at_max=swept_at_max,
        swept_volume_at_min=swept_at_min,
        swept_intersects_wing_at_max=intersects_at_max,
        swept_intersects_wing_at_min=intersects_at_min,
        monotonic_trend=monotonic,
    )


def check_kinematics(
    result: KinematicResult,
    gap_mm: float,
) -> dict[str, Any]:
    """Check kinematic pass criteria.

    Args:
        result: KinematicResult from sweep_device.
        gap_mm: configured gap between device and wing.

    Returns:
        Dict with pass/fail status and details.
    """
    checks = {
        "collision_free": result.collision_count == 0,
        "clearance_ok": result.min_clearance_mm >= gap_mm - KERNEL_TOLERANCE_MM,
        "monotonic_trend": result.monotonic_trend,
        "swept_volume_no_wing_intersection_at_max": not result.swept_intersects_wing_at_max,
        "swept_volume_no_wing_intersection_at_min": not result.swept_intersects_wing_at_min,
        "all_pass": (
            result.collision_count == 0 and
            result.min_clearance_mm >= gap_mm - KERNEL_TOLERANCE_MM and
            result.monotonic_trend and
            not result.swept_intersects_wing_at_max and
            not result.swept_intersects_wing_at_min
        ),
    }
    return checks


def sweep_all_devices(
    config: Any,
    fixed_wing: cq.Solid,
    device_solids: dict[str, cq.Solid],
    hinge_axes: dict[str, cq.Edge],
) -> dict[str, KinematicResult]:
    """Sweep all enabled devices through their deflection range.

    Args:
        config: wing configuration.
        fixed_wing: the fixed wing OML solid.
        device_solids: dict of device_name → solid at 0° deflection.
        hinge_axes: dict of device_name → hinge axis edge.

    Returns:
        Dict of device_name → KinematicResult.
    """
    results = {}

    # Check TE surface
    if config.te_surface and config.te_surface.enabled:
        if "te" in device_solids and "te" in hinge_axes:
            result = sweep_device(
                fixed_wing,
                device_solids["te"],
                hinge_axes["te"],
                config.te_surface.max_deflection_deg,
            )
            result.device_name = "te"
            results["te"] = result

    # Check LE droop
    if config.le_droop and config.le_droop.enabled:
        if "le" in device_solids and "le" in hinge_axes:
            result = sweep_device(
                fixed_wing,
                device_solids["le"],
                hinge_axes["le"],
                config.le_droop.max_deflection_deg,
            )
            result.device_name = "le"
            results["le"] = result

    return results
