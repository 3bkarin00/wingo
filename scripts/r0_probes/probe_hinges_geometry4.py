"""R0 probe round 4 — round 3 found the root cause of round 2's zero-clearance
result: growing the lug's own (cylinder+box) construction PARAMETERS by a
fixed margin does NOT guarantee the resulting fused shape is a superset of
the original grown by margin everywhere (lug∩notch_tool was only 47% of
lug.Volume) — verified the failure was near a box CORNER close to where
sqrt(a²+u²)≈R, consistent with ruled-loft faceting / circular-arc corner
effects that a naive per-parameter growth does not account for.

Round 4 uses a provably-correct alternative: grow the lug's own real
axis-aligned BoundingBox() by margin in all 6 face directions (global X/Y/Z,
not the local a/u/h frame) to build the notch tool. For ANY point p inside
the original bounding box and ANY point q outside the grown box, at least
one axis has |p_i - q_i| > margin, so |p-q| > margin unconditionally — a
pure Minkowski-box argument, independent of the lug's actual (possibly
irregular) shape. This run verifies it holds on the real kernel/real CS
geometry, and re-verifies hole coaxiality after drilling.
"""
from __future__ import annotations

import sys
import time

import cadquery as cq
import numpy as np
import yaml

sys.path.insert(0, ".")

from backend import tolerances
from backend.geometry.booleans import fuzzy_cut, fuzzy_common, filter_shards
from backend.geometry.false_spar import build_false_spar
from backend.geometry.iml import build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.geometry.cove_profile import analytic_section_points, find_station_feet
from backend.geometry.te_cut import cut_te_surface, hinge_frame
from backend.schema.models import Config

t_start = time.perf_counter()
config = Config.model_validate(yaml.safe_load(open("tests/configs/devices/te_half.yaml").read()))
sections = build_planform_sections(config, config.airfoils.resample_points)
oml = build_oml(sections, config.planform.mirror)
res = cut_te_surface(config, oml)
wing_solid, cs_solid = res.wing, res.control_surface
lofts = build_sandwich_lofts(config, sections)
fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
print(f"[{time.perf_counter()-t_start:6.1f}s] built oml/te_cut/false_spar")

p0, p1, h, a, u, axis_len = hinge_frame(config)
gap = config.te_surface.gap_mm
s_mid = axis_len / 2.0
C = p0 + h * s_mid


def pin_cylinder(base, dir_h, length, radius):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*(base - dir_h * (length / 2))), cq.Vector(*dir_h))


def oriented_box(center, dir_a, dir_u, dir_h, len_a, len_u, len_h):
    origin = center - dir_a * (len_a / 2) - dir_u * (len_u / 2) - dir_h * (len_h / 2)
    plane = cq.Plane(origin=cq.Vector(*origin), xDir=cq.Vector(*dir_a), normal=cq.Vector(*dir_u))
    return cq.Workplane(plane).box(len_a, len_u, len_h, centered=(False, False, False)).val()


knuckle_od = 5.0
knuckle_r = knuckle_od / 2
knuckle_len = 10.0
pin_r = 1.0
feet = find_station_feet(analytic_section_points(sections, C, h), C, a, u)
reach = feet.R + tolerances.COVE_CLEARANCE_MM + tolerances.FALSE_SPAR_COVE_STANDOFF_MM + 2.0
margin = gap + 0.05
print(f"feet.R={feet.R:.3f} reach={reach:.3f} margin={margin:.3f}")

knuckle = pin_cylinder(C, h, knuckle_len, knuckle_r)
tab = oriented_box(C - a * (reach / 2), a, u, h, reach, knuckle_od, knuckle_len)
lug = knuckle.fuse(tab)

bb = lug.BoundingBox()
notch_tool = cq.Solid.makeBox(
    bb.xlen + 2 * margin, bb.ylen + 2 * margin, bb.zlen + 2 * margin,
    cq.Vector(bb.xmin - margin, bb.ymin - margin, bb.zmin - margin),
)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug.Volume={lug.Volume():.3f} bb=({bb.xlen:.2f},{bb.ylen:.2f},{bb.zlen:.2f}) "
      f"notch_tool.Volume={notch_tool.Volume():.2f}")

lug_in_notch = fuzzy_common(lug, notch_tool)
lug_in_notch_solids, _ = filter_shards(lug_in_notch, min_volume=1e-9)
vol_in = sum(s.Volume() for s in lug_in_notch_solids)
print(f"lug∩notch_tool={vol_in:.3f} (should == lug.Volume={lug.Volume():.3f})")

cs_notched = fuzzy_cut(cs_solid, notch_tool)
cs_notched_solids, cs_notched_shards = filter_shards(cs_notched, min_volume=1e-6)
cs_notched_main = max(cs_notched_solids, key=lambda s: s.Volume())
print(f"[{time.perf_counter()-t_start:6.1f}s] cs_notched: {len(cs_notched_solids)} solid(s) "
      f"shards={len(cs_notched_shards)} watertight={is_watertight(cs_notched_main)} "
      f"vol={cs_notched_main.Volume():.1f} (orig cs={cs_solid.Volume():.1f})")

from OCP.BRepExtrema import BRepExtrema_DistShapeShape

dist_op = BRepExtrema_DistShapeShape(lug.wrapped, cs_notched_main.wrapped)
dist_op.Perform()
lug_to_cs = dist_op.Value() if dist_op.IsDone() else None
print(f"lug_to_cs_notched clearance={lug_to_cs} (need >= gap_mm={gap})")

dist_op2 = BRepExtrema_DistShapeShape(lug.wrapped, fs.solid.wrapped)
dist_op2.Perform()
print(f"lug_to_false_spar={dist_op2.Value()}")
overlap = fuzzy_common(lug, fs.solid)
overlap_solids, _ = filter_shards(overlap, min_volume=1e-9)
print(f"lug ∩ false_spar volume={sum(s.Volume() for s in overlap_solids):.3f}mm3 (want > 0)")

# --- tang (unaffected by the notch, different y) ---
s_tang = s_mid + 20.0
C_tang = p0 + h * s_tang
knuckle_t = pin_cylinder(C_tang, h, knuckle_len, knuckle_r)
tang_raw = fuzzy_common(knuckle_t, cs_solid)
tang_solids, tang_shards = filter_shards(tang_raw, min_volume=1e-6)
tang = max(tang_solids, key=lambda s: s.Volume())
dist_op3 = BRepExtrema_DistShapeShape(tang.wrapped, wing_solid.wrapped)
dist_op3.Perform()
print(f"tang volume={tang.Volume():.2f} shards={len(tang_shards)} watertight={is_watertight(tang)} "
      f"tang_to_wing_clearance={dist_op3.Value()}")

# --- drill pin holes and check coaxiality ---
pin_hole_lug = pin_cylinder(C, h, knuckle_len * 1.5, pin_r)
lug_drilled = fuzzy_cut(lug, pin_hole_lug)
lug_drilled_solids, lug_drilled_shards = filter_shards(lug_drilled, min_volume=1e-9)
lug_main = max(lug_drilled_solids, key=lambda s: s.Volume())
print(f"lug_drilled: {len(lug_drilled_solids)} solid(s) shards={len(lug_drilled_shards)} "
      f"vol={lug_main.Volume():.2f} watertight={is_watertight(lug_main)}")

pin_hole_tang = pin_cylinder(C_tang, h, knuckle_len * 1.5, pin_r)
tang_drilled = fuzzy_cut(tang, pin_hole_tang)
tang_drilled_solids, tang_drilled_shards = filter_shards(tang_drilled, min_volume=1e-9)
tang_main = max(tang_drilled_solids, key=lambda s: s.Volume())
print(f"tang_drilled: {len(tang_drilled_solids)} solid(s) shards={len(tang_drilled_shards)} "
      f"vol={tang_main.Volume():.2f} watertight={is_watertight(tang_main)}")

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

h_unit = h / np.linalg.norm(h)


def report_coax(label, solid, true_point):
    for face in solid.Faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surf.Cylinder()
        d = cyl.Axis().Direction()
        axv = np.array([d.X(), d.Y(), d.Z()])
        if abs(abs(float(np.dot(axv, h_unit))) - 1.0) > 0.02:
            continue
        loc = cyl.Axis().Location()
        p = np.array([loc.X(), loc.Y(), loc.Z()])
        w = true_point - p
        perp = w - np.dot(w, axv) * axv
        dev = float(np.linalg.norm(perp))
        print(f"  {label} cyl face: radius={cyl.Radius():.3f}mm axis_dev={dev:.5f}mm")


report_coax("lug", lug_main, C)
report_coax("tang", tang_main, C_tang)

print(f"TOTAL {time.perf_counter()-t_start:6.1f}s")
