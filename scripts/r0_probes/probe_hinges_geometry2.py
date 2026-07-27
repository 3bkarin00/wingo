"""R0 probe round 2 for P7 hinges — round 1 (probe_hinges_geometry.py) found
a real design flaw: cutting the lug's knuckle+tab blank against
build_cove_offset_region (or the raw cs_solid) removes the ENTIRE knuckle,
not just the tab's near-axis sliver — CS's real nose material reaches all
the way to r=0 (round 1's own "100% inside cs_solid" result), so a wing lug
knuckle cannot be produced as a SUBTRACTION result at all.

Round 2 tests the fix: cut a GROWN "keyway" copy of the lug's own shape
(knuckle+tab, each dimension grown by gap_mm+margin) out of a DERIVED copy
of cs_solid ("cs_notched" — NOT the frozen P4 cs_solid itself, an additive
P7-only body, same precedent as ribs.py/spar_trim.py deriving new bodies
from P4/P6 outputs without modifying them), then build the lug as the
UN-grown shape. If the grown notch tool is a superset of the un-grown lug
shape by construction, clearance is guaranteed by construction — this run
verifies that numerically on the real kernel, not just by geometric
argument.
"""
from __future__ import annotations

import sys
import time

import cadquery as cq
import yaml

sys.path.insert(0, ".")

from backend.geometry.booleans import fuzzy_cut, fuzzy_common, filter_shards
from backend.geometry.false_spar import build_false_spar
from backend.geometry.iml import build_sandwich_lofts
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.geometry.cove_profile import analytic_section_points, find_station_feet
from backend.geometry.te_cut import cut_te_surface, hinge_frame
from backend.schema.models import Config
from backend import tolerances

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
print(f"gap_mm={gap} station s={s_mid:.2f} C={C}")


def pin_cylinder(base, dir_h, length, radius):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*(base - dir_h * (length / 2))), cq.Vector(*dir_h))


def oriented_box(center, dir_a, dir_u, dir_h, len_a, len_u, len_h):
    origin = center - dir_a * (len_a / 2) - dir_u * (len_u / 2) - dir_h * (len_h / 2)
    plane = cq.Plane(origin=cq.Vector(*origin), xDir=cq.Vector(*dir_a), normal=cq.Vector(*dir_u))
    return cq.Workplane(plane).box(len_a, len_u, len_h, centered=(False, False, False)).val()


def lug_blank(C, knuckle_r, knuckle_len, reach, tab_w, tab_h_dim):
    knuckle = pin_cylinder(C, h, knuckle_len, knuckle_r)
    tab = oriented_box(C - a * (reach / 2), a, u, h, reach, tab_w, tab_h_dim)
    return knuckle.fuse(tab)


knuckle_od = tolerances.HINGE_PIN_DIA_MM + 2 * 1.5 if hasattr(tolerances, "HINGE_PIN_DIA_MM") else 5.0
knuckle_r = knuckle_od / 2
knuckle_len = 10.0

feet = find_station_feet(analytic_section_points(sections, C, h), C, a, u)
reach = feet.R + tolerances.COVE_CLEARANCE_MM + tolerances.FALSE_SPAR_COVE_STANDOFF_MM + 2.0
print(f"feet.R={feet.R:.3f}mm computed reach={reach:.3f}mm")

margin = gap + 0.05  # exactly the configured fit gap + a small kernel-fuzz safety margin

lug = lug_blank(C, knuckle_r, knuckle_len, reach, knuckle_od, knuckle_len)
notch_tool = lug_blank(C, knuckle_r + margin, knuckle_len + 2 * margin, reach + margin, knuckle_od + 2 * margin, knuckle_len + 2 * margin)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug vol={lug.Volume():.2f} notch_tool vol={notch_tool.Volume():.2f}")

cs_notched = fuzzy_cut(cs_solid, notch_tool)
cs_notched_solids, cs_notched_shards = filter_shards(cs_notched, min_volume=1e-6)
print(f"[{time.perf_counter()-t_start:6.1f}s] cs_notched: {len(cs_notched_solids)} solid(s) "
      f"vols={[round(s.Volume(),1) for s in cs_notched_solids]} shards={len(cs_notched_shards)} "
      f"orig_cs_vol={cs_solid.Volume():.1f}")
cs_notched_main = max(cs_notched_solids, key=lambda s: s.Volume())
print(f"watertight={is_watertight(cs_notched_main)}")

from OCP.BRepExtrema import BRepExtrema_DistShapeShape

dist_op = BRepExtrema_DistShapeShape(lug.wrapped, cs_notched_main.wrapped)
dist_op.Perform()
lug_to_cs = dist_op.Value() if dist_op.IsDone() else None
print(f"[{time.perf_counter()-t_start:6.1f}s] lug_to_cs_notched clearance={lug_to_cs} (need >= gap_mm={gap})")

dist_op2 = BRepExtrema_DistShapeShape(lug.wrapped, fs.solid.wrapped)
dist_op2.Perform()
lug_to_fs = dist_op2.Value() if dist_op2.IsDone() else None
print(f"lug_to_false_spar={lug_to_fs}")

lug_fs_overlap = fuzzy_common(lug, fs.solid)
lug_fs_overlap_solids, _ = filter_shards(lug_fs_overlap, min_volume=1e-9)
print(f"lug ∩ false_spar volume={sum(s.Volume() for s in lug_fs_overlap_solids):.3f}mm3 "
      f"({len(lug_fs_overlap_solids)} solids) -- want > 0 (real bond overlap)")

# pin hole through the knuckle only
pin_r = 1.0
pin_hole = pin_cylinder(C, h, knuckle_len * 1.5, pin_r)
lug_drilled = fuzzy_cut(lug, pin_hole)
lug_drilled_solids, lug_drilled_shards = filter_shards(lug_drilled, min_volume=1e-9)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug_drilled: {len(lug_drilled_solids)} solid(s) "
      f"vols={[round(s.Volume(),2) for s in lug_drilled_solids]} shards={len(lug_drilled_shards)} "
      f"watertight={[is_watertight(s) for s in lug_drilled_solids]}")

# extract cylindrical faces of the drilled lug and report their axis line vs true axis (C, h)
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
import numpy as np

lug_main = max(lug_drilled_solids, key=lambda s: s.Volume())
h_unit = h / np.linalg.norm(h)
for face in lug_main.Faces():
    surf = BRepAdaptor_Surface(face.wrapped)
    if surf.GetType() != GeomAbs_Cylinder:
        continue
    cyl = surf.Cylinder()
    d = cyl.Axis().Direction()
    axv = np.array([d.X(), d.Y(), d.Z()])
    loc = cyl.Axis().Location()
    p = np.array([loc.X(), loc.Y(), loc.Z()])
    dotp = abs(float(np.dot(axv, h_unit)))
    if dotp < 0.98:
        continue
    w = C - p
    perp = w - np.dot(w, axv) * axv
    dev = float(np.linalg.norm(perp))
    print(f"  cyl face: radius={cyl.Radius():.3f}mm axis_dev_from_true_axis={dev:.5f}mm dir_dot={dotp:.5f}")

print(f"TOTAL {time.perf_counter()-t_start:6.1f}s")
