"""Hinge geometry — generated mode (plan.md P7).

Generates hinge holes (cylindrical cutouts) coaxial with the hinge axis,
and lug/tang features on the moving body (TE surface / LE droop).

Generated mode:
- Hinge holes are cylinders centered on the hinge axis, spaced evenly along
  the axis based on ``hinges.count``.
- Lug features are protrusions on the moving body that fit into the holes.
- Tang features are recesses on the fixed body that receive the lugs.
- Coaxiality is by construction: all holes are built around the hinge axis
  line, so measured coaxiality is 0 mm (within the 0.05 mm tolerance).
- Lug/tang clearance to the moving body is the configured fit gap
  (``gap_mm`` from the device window).

Usage:
    from backend.geometry.hinges import generate_hinge_holes, generate_lug_tang

    hinge_axis = ref.hinge_axes["te"]
    holes = generate_hinge_holes(hinge_axis, count=3, pin_dia_mm=6.0)
    lugs = generate_lug_tang(hinge_axis, count=3, pin_dia_mm=6.0, fit_gap_mm=1.5)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq
import numpy as np

from backend.tolerances import COAXIALITY_TOLERANCE_MM

# Default hinge pin diameter (mm) — used when cots_pin_dia_mm is not set.
# Scaled for typical wing sizes; adjust from the real COTS catalog in P18.
DEFAULT_HINGE_PIN_DIA_MM = 6.0

# Lug/tang protrusion dimensions as fractions of pin diameter.
LUG_PROTRUSION_FRAC = 0.4   # lug extends 40% of pin dia beyond the hole
TANG_CLEARANCE_FRAC = 0.15  # tang recess is 15% pin dia deeper than lug


@dataclass
class HingeHole:
    """A single hinge hole (cylindrical cutout)."""
    center: tuple[float, float, float]
    axis_direction: tuple[float, float, float]
    radius_mm: float
    length_mm: float


@dataclass
class LugTang:
    """Lug (on moving body) + tang (on fixed body) for one hinge location."""
    position: tuple[float, float, float]
    lug_protrusion_mm: float
    tang_depth_mm: float
    pin_dia_mm: float


@dataclass
class HingeGeometry:
    """Complete hinge geometry for one device (TE or LE)."""
    hinge_axis: cq.Edge  # the reference hinge axis line
    holes: list[HingeHole] = field(default_factory=list)
    lugs: list[LugTang] = field(default_factory=list)
    pin_dia_mm: float = 0.0
    count: int = 0
    fit_gap_mm: float = 0.0

    def solid_hole_cutouts(self) -> list[cq.Solid]:
        """Return cylindrical solids for boolean cut (hole removal)."""
        solids = []
        for h in self.holes:
            # Create a cylinder centered on the hinge axis
            axis_vec = cq.Vector(*h.axis_direction)
            center_vec = cq.Vector(*h.center)
            # Cylinder axis is along the hinge axis direction
            cyl = cq.Solid.makeCylinder(
                h.radius_mm, h.length_mm,
                center_vec, axis_vec,
            )
            solids.append(cyl)
        return solids

    def solid_lug_features(self) -> list[cq.Solid]:
        """Return lug solids (protrusions on the moving body)."""
        solids = []
        for lt in self.lugs:
            pos = cq.Vector(*lt.position)
            # Lug is a cylinder slightly larger than the hole
            cyl = cq.Solid.makeCylinder(
                lt.pin_dia_mm / 2.0 + lt.lug_protrusion_mm / 2.0,
                lt.lug_protrusion_mm,
                pos,
                cq.Vector(0, 0, 1),  # local Z (perpendicular to hinge axis)
            )
            solids.append(cyl)
        return solids

    def solid_tang_features(self) -> list[cq.Solid]:
        """Return tang solids (recesses on the fixed body)."""
        solids = []
        for lt in self.lugs:
            pos = cq.Vector(*lt.position)
            # Tang is a cylinder slightly larger than the lug
            cyl = cq.Solid.makeCylinder(
                lt.pin_dia_mm / 2.0 + lt.lug_protrusion_mm / 2.0 + lt.tang_depth_mm,
                lt.tang_depth_mm,
                pos,
                cq.Vector(0, 0, 1),
            )
            solids.append(cyl)
        return solids


def generate_hinge_holes(
    hinge_axis: cq.Edge,
    count: int,
    pin_dia_mm: float | None = None,
) -> list[HingeHole]:
    """Generate hinge hole definitions along the hinge axis.

    Holes are cylinders centered on the hinge axis, spaced evenly along it.
    Coaxiality is by construction: all hole axes coincide with the hinge axis.

    Args:
        hinge_axis: straight edge defining the hinge axis line.
        count: number of hinge locations.
        pin_dia_mm: hinge pin diameter (default: 6.0 mm).

    Returns:
        List of HingeHole definitions.
    """
    if pin_dia_mm is None:
        pin_dia_mm = DEFAULT_HINGE_PIN_DIA_MM

    # Get the two endpoints of the hinge axis line
    axis_vertices = hinge_axis.Vertices()
    if len(axis_vertices) < 2:
        raise ValueError("Hinge axis must be a line with at least 2 vertices")

    p1 = axis_vertices[0].toTuple()
    p2 = axis_vertices[1].toTuple()

    # Axis direction (unit vector)
    direction = cq.Vector(p2) - cq.Vector(p1)
    axis_len = direction.Length
    dir_unit = direction.normalized()

    # Generate evenly-spaced hole centers along the axis
    holes = []
    for i in range(count):
        t = (i + 0.5) / count  # 0.5/count to 1-0.5/count (evenly spaced, centered)
        center = cq.Vector(p1) + direction * t
        # Each hole extends slightly beyond the axis (length = pin_dia * 2 + margin)
        hole_length = pin_dia_mm * 2.0 + 2.0  # 2 mm margin each side
        holes.append(HingeHole(
            center=center.toTuple(),
            axis_direction=tuple(dir_unit.toTuple()),
            radius_mm=pin_dia_mm / 2.0,
            length_mm=hole_length,
        ))

    return holes


def generate_lug_tang(
    hinge_axis: cq.Edge,
    count: int,
    pin_dia_mm: float | None = None,
    fit_gap_mm: float | None = None,
) -> list[LugTang]:
    """Generate lug/tang feature definitions for hinge locations.

    Lug features protrude from the moving body; tang features are recesses
    on the fixed body. The fit gap is the clearance between lug/tang and
    the moving body surface.

    Args:
        hinge_axis: straight edge defining the hinge axis line.
        count: number of hinge locations.
        pin_dia_mm: hinge pin diameter (default: 6.0 mm).
        fit_gap_mm: clearance fit gap (default: 1.5 mm).

    Returns:
        List of LugTang definitions.
    """
    if pin_dia_mm is None:
        pin_dia_mm = DEFAULT_HINGE_PIN_DIA_MM
    if fit_gap_mm is None:
        fit_gap_mm = 1.5

    # Get the two endpoints of the hinge axis line
    axis_vertices = hinge_axis.Vertices()
    if len(axis_vertices) < 2:
        raise ValueError("Hinge axis must be a line with at least 2 vertices")

    p1 = axis_vertices[0].toTuple()
    p2 = axis_vertices[1].toTuple()

    # Axis direction (unit vector)
    direction = cq.Vector(p2) - cq.Vector(p1)
    dir_unit = direction.normalized()

    lugs = []
    for i in range(count):
        t = (i + 0.5) / count
        position = cq.Vector(p1) + direction * t

        lug_protrusion = pin_dia_mm * LUG_PROTRUSION_FRAC
        # Tang depth = lug protrusion + fit gap (ensures lug/tang clearance >= fit_gap)
        tang_depth = lug_protrusion + fit_gap_mm

        lugs.append(LugTang(
            position=position.toTuple(),
            lug_protrusion_mm=lug_protrusion,
            tang_depth_mm=tang_depth,
            pin_dia_mm=pin_dia_mm,
        ))

    return lugs


def build_hinge_geometry(
    config: Any,
    hinge_axis: cq.Edge,
    device_name: str = "te",
) -> HingeGeometry:
    """Build complete hinge geometry for a device (TE or LE).

    Args:
        config: wing configuration.
        hinge_axis: the reference hinge axis edge.
        device_name: "te" or "le" to look up device config.

    Returns:
        HingeGeometry with holes, lugs, and tangs.
    """
    # Look up the device window config
    device = None
    if device_name == "te" and config.te_surface and config.te_surface.enabled:
        device = config.te_surface
    elif device_name == "le" and config.le_droop and config.le_droop.enabled:
        device = config.le_droop

    if device is None:
        return HingeGeometry(hinge_axis=hinge_axis)

    # Determine pin diameter
    pin_dia = device.hinges.cots_pin_dia_mm or DEFAULT_HINGE_PIN_DIA_MM
    count = device.hinges.count
    fit_gap = device.gap_mm  # use device gap as fit gap

    holes = generate_hinge_holes(hinge_axis, count, pin_dia_mm=pin_dia)
    lugs = generate_lug_tang(hinge_axis, count, pin_dia_mm=pin_dia, fit_gap_mm=fit_gap)

    return HingeGeometry(
        hinge_axis=hinge_axis,
        holes=holes,
        lugs=lugs,
        pin_dia_mm=pin_dia,
        count=count,
        fit_gap_mm=fit_gap,
    )


def measure_coaxiality(
    hinge_axis: cq.Edge,
    hole_centers: list[tuple[float, float, float]],
) -> float:
    """Measure coaxiality of hole centers against the hinge axis.

    Coaxiality = max distance from each hole center to the hinge axis line.
    By construction, this should be 0 mm (all holes are centered on the axis).

    Args:
        hinge_axis: the reference hinge axis edge.
        hole_centers: list of (x, y, z) hole center coordinates.

    Returns:
        Maximum coaxiality deviation in mm.
    """
    axis_vertices = hinge_axis.Vertices()
    if len(axis_vertices) < 2:
        raise ValueError("Hinge axis must be a line with at least 2 vertices")

    p1 = cq.Vector(*axis_vertices[0].toTuple())
    p2 = cq.Vector(*axis_vertices[1].toTuple())
    axis_dir = (p2 - p1).normalized()

    max_dev = 0.0
    for center in hole_centers:
        c = cq.Vector(*center)
        # Distance from point to line = |(c - p1) x axis_dir|
        to_point = c - p1
        cross = to_point.cross(axis_dir)
        dist = cross.Length
        max_dev = max(max_dev, dist)

    return max_dev


def measure_lug_clearance(
    hinge_axis: cq.Edge,
    lugs: list[LugTang],
    fit_gap_mm: float,
) -> float:
    """Measure minimum lug clearance to the moving body.

    Clearance = tang_depth_mm - lug_protrusion_mm (the gap between lug
    surface and tang surface). Must be >= fit_gap_mm.

    Args:
        hinge_axis: the reference hinge axis edge.
        lugs: list of LugTang definitions.
        fit_gap_mm: configured fit gap.

    Returns:
        Minimum clearance in mm (should be >= fit_gap_mm).
    """
    min_clearance = float("inf")
    for lt in lugs:
        # Clearance = how much deeper the tang is than the lug protrudes
        clearance = lt.tang_depth_mm - lt.lug_protrusion_mm
        min_clearance = min(min_clearance, clearance)
    return min_clearance
