"""R0 probe round 3 — round 2 found lug_to_cs_notched clearance = EXACTLY
0.0mm despite growing the notch tool's every parameter by margin=gap+0.05mm
around the lug's own shape. Isolate WHERE the zero-distance point is and
which piece (knuckle vs tab) causes it, and verify the containment
assumption (lug ⊂ notch_tool) directly rather than through the cs_solid
boolean.
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
feet = find_station_feet(analytic_section_points(sections, C, h), C, a, u)
reach = feet.R + tolerances.COVE_CLEARANCE_MM + tolerances.FALSE_SPAR_COVE_STANDOFF_MM + 2.0
margin = gap + 0.05
print(f"feet.R={feet.R:.3f} reach={reach:.3f} margin={margin:.3f}")

knuckle = pin_cylinder(C, h, knuckle_len, knuckle_r)
tab = oriented_box(C - a * (reach / 2), a, u, h, reach, knuckle_od, knuckle_len)
lug = knuckle.fuse(tab)

knuckle_n = pin_cylinder(C, h, knuckle_len + 2 * margin, knuckle_r + margin)
tab_n = oriented_box(C - a * ((reach + margin) / 2), a, u, h, reach + margin, knuckle_od + 2 * margin, knuckle_len + 2 * margin)
notch_tool = knuckle_n.fuse(tab_n)

# --- containment: is lug fully inside notch_tool? ---
lug_in_notch = fuzzy_common(lug, notch_tool)
lug_in_notch_solids, _ = filter_shards(lug_in_notch, min_volume=1e-9)
vol_in = sum(s.Volume() for s in lug_in_notch_solids)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug.Volume={lug.Volume():.3f} lug∩notch_tool={vol_in:.3f} "
      f"(should equal lug.Volume if fully contained)")

# --- isolate knuckle vs tab distance to cs_notched ---
cs_notched = fuzzy_cut(cs_solid, notch_tool)
cs_notched_solids, _ = filter_shards(cs_notched, min_volume=1e-6)
cs_notched_main = max(cs_notched_solids, key=lambda s: s.Volume())
print(f"[{time.perf_counter()-t_start:6.1f}s] cs_notched built, vol={cs_notched_main.Volume():.1f}")

from OCP.BRepExtrema import BRepExtrema_DistShapeShape


def report_dist(label, shape1, shape2):
    op = BRepExtrema_DistShapeShape(shape1.wrapped, shape2.wrapped)
    op.Perform()
    d = op.Value() if op.IsDone() else None
    pt1 = pt2 = None
    if op.IsDone() and op.NbSolution() >= 1:
        p1_ = op.PointOnShape1(1)
        p2_ = op.PointOnShape2(1)
        pt1 = (p1_.X(), p1_.Y(), p1_.Z())
        pt2 = (p2_.X(), p2_.Y(), p2_.Z())
    print(f"  {label}: dist={d} pt_on_1={pt1} pt_on_2={pt2}")
    if pt1 is not None:
        local_a = float(np.dot(np.array(pt1) - C, a))
        local_u = float(np.dot(np.array(pt1) - C, u))
        local_h = float(np.dot(np.array(pt1) - C, h))
        print(f"    -> local (a,u,h) relative to C = ({local_a:.3f}, {local_u:.3f}, {local_h:.3f})")


report_dist("knuckle -> cs_notched", knuckle, cs_notched_main)
report_dist("tab -> cs_notched", tab, cs_notched_main)
report_dist("lug(fused) -> cs_notched", lug, cs_notched_main)
report_dist("lug(fused) -> cs_solid(raw)", lug, cs_solid)

print(f"TOTAL {time.perf_counter()-t_start:6.1f}s")
