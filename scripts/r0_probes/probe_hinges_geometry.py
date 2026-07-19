"""R0 probe for P7 (Hinges, generated mode) — empirically verify, against the
REAL kernel and a real config (te_half.yaml), the geometric assumptions the
hinges.py design depends on before writing it:

1. Does the CS nose_region solid (hence control_surface) actually enclose the
   true hinge-axis LINE itself (r=0), at a station well inside the device
   window? (If not, a "tang" knuckle centered on the axis wouldn't be
   embedded in real CS material as assumed.)
2. Is the wing solid genuinely absent near the axis (confirming a "lug" needs
   a reaching tab out to the false spar, not just a centered knuckle)?
3. Does build_cove_offset_region(extra_radius_mm=0.0) — the same function
   P6 already uses for cove-fidelity IML cuts — give a solid that, when used
   to fuzzy_cut a candidate lug blank, leaves the lug standing clear of the
   real cs_solid by roughly COVE_CLEARANCE_MM (5mm, already proven >=
   gap_mm in production code — export_viewer_data.py's false-spar check)?
4. Does a straight -a-direction reach from the knuckle actually penetrate the
   real false_spar solid (confirming the lug-mount-to-false-spar idea)?

No new third-party API beyond what P4/P6 already R0-verified (makeCylinder
was already probed in probe_ocp_boolean.py) — this probe is about VERIFYING
GEOMETRIC FACTS about already-built real shapes, not new API syntax.
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
from backend.geometry.te_cut import build_cove_offset_region, cut_te_surface, hinge_frame
from backend.schema.models import Config

t_start = time.perf_counter()
config = Config.model_validate(yaml.safe_load(open("tests/configs/devices/te_half.yaml").read()))
sections = build_planform_sections(config, config.airfoils.resample_points)
oml = build_oml(sections, config.planform.mirror)
print(f"[{time.perf_counter()-t_start:6.1f}s] OML built, volume={oml.Volume():.1f}mm3, watertight={is_watertight(oml)}")

res = cut_te_surface(config, oml)
wing_solid, cs_solid = res.wing, res.control_surface
print(f"[{time.perf_counter()-t_start:6.1f}s] te_cut done: wing={wing_solid.Volume():.1f}mm3 cs={cs_solid.Volume():.1f}mm3")

lofts = build_sandwich_lofts(config, sections)
fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
print(f"[{time.perf_counter()-t_start:6.1f}s] false_spar built, volume={fs.solid.Volume():.1f}mm3")

p0, p1, h, a, u, axis_len = hinge_frame(config)
gap = config.te_surface.gap_mm
print(f"axis_len={axis_len:.2f}mm gap_mm={gap} h={h} a={a} u={u}")

s_mid = axis_len / 2.0
C = p0 + h * s_mid
print(f"station s={s_mid:.2f}mm -> C={C}")

# --- Fact 1: does CS enclose the true axis point C itself? ------------------
probe_r = 0.05
tiny_box = cq.Solid.makeBox(2 * probe_r, 2 * probe_r, 2 * probe_r,
                             cq.Vector(*(C - probe_r)))
in_cs = fuzzy_common(tiny_box, cs_solid)
in_wing = fuzzy_common(tiny_box, wing_solid)
cs_vol = sum(s.Volume() for s in in_cs.Solids()) if in_cs.Solids() else 0.0
wing_vol = sum(s.Volume() for s in in_wing.Solids()) if in_wing.Solids() else 0.0
tiny_vol = (2 * probe_r) ** 3
print(f"[{time.perf_counter()-t_start:6.1f}s] tiny probe at C: cs_fraction={cs_vol/tiny_vol:.3f} wing_fraction={wing_vol/tiny_vol:.3f}")

# --- Fact 2: candidate knuckle (small cylinder on the true axis) fully in CS? ---
knuckle_od = 5.0
knuckle_len = 10.0
knuckle = cq.Solid.makeCylinder(knuckle_od / 2, knuckle_len, cq.Vector(*(C - h * (knuckle_len / 2))), cq.Vector(*h))
knuckle_in_cs = fuzzy_common(knuckle, cs_solid)
knuckle_in_cs_vol = sum(s.Volume() for s in knuckle_in_cs.Solids()) if knuckle_in_cs.Solids() else 0.0
print(f"[{time.perf_counter()-t_start:6.1f}s] knuckle(OD={knuckle_od}) volume={knuckle.Volume():.2f}mm3, "
      f"inside cs_solid={knuckle_in_cs_vol:.2f}mm3 ({100*knuckle_in_cs_vol/knuckle.Volume():.1f}%)")

# --- Fact 3: cut a lug blank against build_cove_offset_region — does it clear real CS? ---
cove_region = build_cove_offset_region(config, sections, extra_radius_mm=0.0)
print(f"[{time.perf_counter()-t_start:6.1f}s] cove_region built, volume={cove_region.Volume():.1f}mm3")


def make_oriented_box(center, dir_a, dir_u, dir_h, len_a, len_u, len_h):
    origin = center - dir_a * (len_a / 2) - dir_u * (len_u / 2) - dir_h * (len_h / 2)
    plane = cq.Plane(origin=cq.Vector(*origin), xDir=cq.Vector(*dir_a), normal=cq.Vector(*dir_u))
    return cq.Workplane(plane).box(len_a, len_u, len_h, centered=(False, False, False)).val()


reach_mm = 40.0  # oversized guess; false spar aft face known to be within ~R+5.5mm
tab_w = knuckle_od
tab = make_oriented_box(C - a * (reach_mm / 2), a, u, h, reach_mm, tab_w, knuckle_len)
lug_blank = knuckle.fuse(tab)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug_blank volume={lug_blank.Volume():.2f}mm3 (knuckle {knuckle.Volume():.2f} + tab {tab.Volume():.2f})")

lug_solid_raw = fuzzy_cut(lug_blank, cove_region)
lug_solids, lug_shards = filter_shards(lug_solid_raw, min_volume=1e-6)
print(f"[{time.perf_counter()-t_start:6.1f}s] lug after cut-vs-cove_region: {len(lug_solids)} solid(s), "
      f"vols={[round(s.Volume(),2) for s in lug_solids]}, shards={len(lug_shards)}")

if lug_solids:
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    lug_main = max(lug_solids, key=lambda s: s.Volume())
    dist_op = BRepExtrema_DistShapeShape(lug_main.wrapped, fs.solid.wrapped)
    dist_op.Perform()
    dist_to_fs = dist_op.Value() if dist_op.IsDone() else None
    dist_op2 = BRepExtrema_DistShapeShape(lug_main.wrapped, cs_solid.wrapped)
    dist_op2.Perform()
    dist_to_cs = dist_op2.Value() if dist_op2.IsDone() else None
    print(f"[{time.perf_counter()-t_start:6.1f}s] lug_main volume={lug_main.Volume():.2f}mm3 "
          f"dist_to_false_spar={dist_to_fs} dist_to_cs_solid={dist_to_cs}")
else:
    print("!!! lug produced NO solids after cutting against cove_region")

# --- Fact 4: tang extraction via fuzzy_common(knuckle, cs_solid) — real, watertight, single solid? ---
tang_raw = fuzzy_common(knuckle, cs_solid)
tang_solids, tang_shards = filter_shards(tang_raw, min_volume=1e-6)
print(f"[{time.perf_counter()-t_start:6.1f}s] tang = knuckle ∩ cs_solid: {len(tang_solids)} solid(s), "
      f"vols={[round(s.Volume(),2) for s in tang_solids]}, shards={len(tang_shards)}, "
      f"watertight={[is_watertight(s) for s in tang_solids]}")

print(f"TOTAL {time.perf_counter()-t_start:6.1f}s")
