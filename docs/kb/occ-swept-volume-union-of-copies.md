---
title: Swept clearance volumes are built as union-of-rotated-copies, never a single revolve
tags: [occ, sweep, hinges, kinematics, d26]
source: "plan.md D26/§8.8; backend/geometry/hinges_pin_tube.py; backend/geometry/kinematics.py; docs/r0_findings/p07.md"
phase: p07
confidence: verified
last_updated: 2026-07-19
---

Any swept clearance envelope in this project (hinge pockets, P8's kinematic
swept-volume check) is built as a UNION OF DISCRETE ROTATED COPIES about the
true axis, never `BRepPrimAPI_MakeRevol`/a single revolve of a solid:

```python
copy = body.rotate(axis_p0_vec, axis_p0_vec + axis_dir_vec, angle_deg)
union = copy if union is None else union.fuse(copy)
```

Why: `cq.Shape.rotate` (rigid rotation about an arbitrary axis) is
R0-verified accurate to 1.5e-14mm against an independent Rodrigues'-formula
reference (docs/r0_findings/p07.md) and composes trivially into a union —
a genuinely swept SOLID's revolve API has edge cases with non-convex/
compound moving bodies this project has never needed to probe. Angular
step is `HINGE_POCKET_SWEEP_STEP_DEG`/`KINEMATIC_SWEPT_ENVELOPE_STEP_DEG`
(2°) — chosen so the chordal sag `r·(1−cos θ)` stays a small fraction of a
mm for any realistic reach, absorbed by an explicit clearance grown into
the MOVING bodies BEFORE rotating (`HINGE_POCKET_SWEPT_CLEARANCE_MM`), not
by a post-hoc 3D offset of the finished union. That's a deliberate
deviation from a "3D-offset the swept union" design note: growing convex
primitives before rotate-union is the same Minkowski growth for those
shapes, and it avoids `BRepOffsetAPI_MakeOffsetShape` on a many-copy union
(the fragile case) — an API this project has never probed.

Two independent consumers of the SAME technique: `hinges_pin_tube.py`'s
swept pockets (construction-time, cuts real clearance into carriers) and
`kinematics.py`'s `swept_envelope`/`envelope_clear_of_wing` (verification-
time, F9's "swept-volume boolean at both extremes intersect fixed wing = ∅").
