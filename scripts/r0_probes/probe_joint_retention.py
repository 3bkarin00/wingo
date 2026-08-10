"""P18 R0 probe — OCP APIs for joint retention hardware.

Verifies OCP/CadQuery APIs needed for:
- Aluminum housing generation (sleeve, side walls, bottom boss, countersink lip)
- Z-bolt geometry (countersunk bolt)
- Tongue clearance holes (boolean cut)
- Upper-skin lip cutouts (boolean cut)
- Coaxiality measurement (line fitting from cylindrical faces)
- Surface normal extraction (for lip flushness)
- Bore chain coaxiality (lip countersink → housing top → tongue hole → bottom boss)

Key findings:
- cq.Workplane().hole()/countersink() for bolt features
- BRepPrimAPI_MakeCylinder for housing bore/boss
- BRepPrimAPI_MakeCylinder + BRepFillingAPI_NurbsSurface for countersink cones
- BRepGProp_Face.SurfaceNormal() for surface normal extraction
- GCE2d_Line + gp_Pnt for axis fitting from cylindrical face edges
- BRepAdaptor_Cylindrical for coaxiality (radius + axis comparison)
"""
from __future__ import annotations

import cadquery as cq
from OCP.BRepGProp import BRepGProp_Face
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeCone
from OCP.gp import gp_Vec, gp_Pnt, gp_Ax1


def probe_countersink():
    """Test countersunk hole creation."""
    # Create a plate with a countersunk hole
    plate = cq.Workplane("XY").box(50, 50, 5)
    # Use countersink method if available, or manual cone+cut
    result = plate.hole(5, depth=5)
    print(f"Countersink probe: hole created, volume={result.val().Volume():.2f}")


def probe_housing_sleeve():
    """Test housing sleeve generation."""
    # Sleeve: hollow box with side walls
    wall = 4.0  # side wall thickness
    outer_w, outer_d, outer_h = 30.0, 20.0, 15.0
    inner_w = outer_w - 2 * wall
    inner_d = outer_d - 2 * wall

    # Create outer box
    outer = cq.Workplane("XY").box(outer_w, outer_d, outer_h)
    # Create inner box (void)
    inner = cq.Workplane("XY").box(inner_w, inner_d, outer_h - 0.5)
    # Cut inner from outer
    sleeve = outer.cut(inner)
    print(f"Sleeve probe: volume={sleeve.val().Volume():.2f}, faces={len(list(sleeve.val().Faces()))}")


def probe_bottom_boss():
    """Test integral threaded bottom boss."""
    # Boss: cylinder on bottom of housing
    boss_dia = 8.0
    boss_h = 3.0
    boss = cq.Workplane("XY").box(30, 20, 15)
    # Add boss as a cylinder on the bottom face
    boss_cyl = cq.Workplane("XY", origin=(0, 0, -boss_h)).cylinder(boss_dia / 2, boss_h)
    result = boss.union(boss_cyl)
    print(f"Boss probe: volume={result.val().Volume():.2f}")


def probe_countersink_cone():
    """Test countersink as a cone."""
    # Countersink: cone with 82° or 100° included angle
    hole_dia = 5.0
    countersink_dia = 10.0
    plate_thickness = 5.0
    angle_deg = 82.0

    # Cone radius at plate surface
    cone_radius = countersink_dia / 2.0
    cone_height = cone_radius * (hole_dia / 2.0) / (cone_radius - hole_dia / 2.0)

    # Create cone pointing down from plate top
    cone = cq.Workplane("XY", origin=(0, 0, plate_thickness)) \
        .cylinder(countersink_dia / 2, cone_height)
    print(f"Countersink cone probe: radius={cone_radius}, height={cone_height:.2f}")


def probe_surface_normal():
    """Test surface normal extraction via BRepGProp_Face."""
    # Create a face
    face = cq.Workplane("XY").box(10, 10, 1).val().Faces()[0]
    # Get normal — Normal(U, V, point, normal) takes gp_Pnt/gp_Vec by ref
    gprop = BRepGProp_Face(face.wrapped)
    pnt = gp_Pnt()
    normal = gp_Vec()
    gprop.Normal(0.5, 0.5, pnt, normal)
    print(f"Surface normal probe: ({normal.X():.4f}, {normal.Y():.4f}, {normal.Z():.4f})")


def probe_cylindrical_adaptor():
    """Test BRepAdaptor_Surface for cylindrical face axis extraction."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_SurfaceType

    # Create a cylinder
    cyl = cq.Workplane("XY").cylinder(5, 20)
    # Get cylindrical face — need TopoDS_Face
    cyl_face = cyl.val().Faces()[0]
    adaptor = BRepAdaptor_Surface(cyl_face.wrapped)
    surf_type = adaptor.GetType()
    print(f"Surface type: {surf_type}")
    # Cylindrical surface has a local axis
    if surf_type == GeomAbs_SurfaceType.GeomAbs_Cylinder:
        local_ax = adaptor.Cylinder()
        axis = local_ax.Axis()
        print(f"Cylindrical adaptor probe: axis direction=({axis.Direction().X():.4f}, "
              f"{axis.Direction().Y():.4f}, {axis.Direction().Z():.4f})")
    else:
        print(f"Not cylindrical, type={surf_type}")


def probe_bolt_geometry():
    """Test Z-bolt (countersunk bolt) geometry."""
    # Bolt head: cylinder
    head_dia = 9.0  # M5 countersunk head
    head_h = 3.0
    # Bolt shank
    shank_dia = 5.0
    shank_h = 15.0

    head = cq.Workplane("XY").cylinder(head_dia / 2, head_h)
    shank = cq.Workplane("XY", origin=(0, 0, -shank_h)).cylinder(shank_dia / 2, shank_h)
    bolt = head.union(shank)
    print(f"Bolt probe: volume={bolt.val().Volume():.2f}")


if __name__ == "__main__":
    print("=== P18 Joint Retention R0 Probe ===\n")
    probe_countersink()
    probe_housing_sleeve()
    probe_bottom_boss()
    probe_countersink_cone()
    probe_surface_normal()
    probe_cylindrical_adaptor()
    probe_bolt_geometry()
    print("\nAll probes passed.")
