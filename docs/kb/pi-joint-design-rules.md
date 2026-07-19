---
title: π-joint rib/skin bonding — proportions, separate-body-for-FEA, explicit bond gaps
tags: [pi-joint, ribs, d24, bonding, wp2b]
source: "backend/geometry/pi_joints.py; backend/tolerances.py PI_* constants; docs/r0_findings/p06_ext.md"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

D24 applies to EVERY rib (no schema opt-in/out — locked decision), so the
π-section dimensions live as `tolerances.py` constants
(`PI_BASE_THICKNESS_MM`/`PI_LEG_THICKNESS_MM` = 0.6mm each, a 3-ply
provisional-CFRP preform laminate; `PI_LEG_HEIGHT_MM` = 8.0mm, ~10-15x the
bond-line thickness, matching the aerospace lap-joint guideline of ≥10x
adherend thickness for bond area) rather than a schema block, since §6
deliberately adds none — promotable to schema later without a construction
change.

Design rules, all real constraints found during construction:
- π preforms are SEPARATE bodies from the rib, not fused into it — a real
  FEA/manufacturing requirement (bonded joint, not integral material) that
  also gives the centroid registry (see face-naming-centroid-registry.md) a
  clean body to attach named bond faces to.
- Rib skin-contact segments are offset INWARD by `(base thickness + bond
  gap)` BEFORE the rib solid is built — the offset is not a post-hoc
  shrink of the finished rib, it changes the actual outline the rib slab is
  built from.
- π legs land at EXACTLY `rib_y ± (rib_thickness/2 + PI_BOND_GAP_MM)` BY
  CONSTRUCTION (not verified after the fact by re-measuring 3D geometry —
  see geometry-shape-vs-solid-typing.md's sibling lesson about not
  re-deriving analytically-guaranteed facts from finished geometry).
  `PI_BOND_GAP_MM` = 0.2mm is the SAME value as `HINGE_CARRIER_BOND_GAP_MM`
  — one shared "structural adhesive film thickness" constant reused across
  every bonded (non-locating) interface in the project, not redefined per
  module.
- Preform paths are trimmed clear of spar crossings
  (`PI_SPAR_CLEARANCE_MM` = one `SPAR_RIB_CUTOUT_CLEARANCE_MM` + 2mm
  handling slack) — the preform must never touch a spar body.
- DELIBERATE DEVIATION from an earlier "three swept boxes and union" recipe
  note: the π section is lofted as ONE simply-connected 12-corner polygon
  instead — identical resulting geometry, zero fuse booleans, no F4 risk at
  the base↔leg junctions.
