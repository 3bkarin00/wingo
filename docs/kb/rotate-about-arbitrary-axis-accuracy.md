---
title: "cq.Shape.rotate about an arbitrary axis is R0-verified accurate to 1.5e-14mm"
tags: [occ, rotation, kinematics, api-verified]
source: "docs/r0_findings/p07.md; backend/geometry/kinematics.py rotate_point"
phase: p07
confidence: verified
last_updated: 2026-07-19
---

`cq.Shape.rotate(axis_start_vec, axis_end_vec, angle_deg)` (rigid rotation
about the LINE through two points, not about the origin) was R0-verified
before being trusted for hinge/kinematic construction: rotating a test
point set and comparing against an independently-implemented Rodrigues'-
rotation-formula reference gave agreement to 1.5e-14mm — effectively exact,
floating-point-noise-level. This is the technique behind every
rotation/sweep-envelope operation in the project (WP1's hinge pockets, P8's
kinematic sweep, P10's server-side vertex check).

Because the agreement is this tight, `backend.geometry.kinematics.
rotate_point` reimplements the SAME rotation as a pure-numpy Rodrigues'
formula (no `cq.Shape` construction at all) specifically so a check can
compare "the real OCC rotation" against "a cheap, independent, exact
mathematical rotation" without needing to build any geometry for the check
itself — e.g. P10's `/kinematics/sample` API endpoint, and the client-side
three.js rotation it's checked against (a THIRD independent implementation
of the same rigid transform, in a different language). Three independent
implementations of the same axis-angle rotation agreeing is a much
stronger correctness claim than one implementation checked against itself.
