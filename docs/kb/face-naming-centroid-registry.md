---
title: Booleans destroy face identity — recover named bond faces via a centroid-match registry, hard-fail on a miss
tags: [occ, naming, face-registry, fea, bonding]
source: "backend/geometry/face_registry.py; plan.md §8 step 8 'Face naming for FEA'"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

A boolean (cut/common/fuse) does not preserve a face's identity across the
operation — you can't hold a reference to "the bond face" through a
subsequent cut and expect it to still resolve. Recovery mechanism, shared
by every bonded interface in the project (hinge carriers, π-joint bonds,
D25 tab/slot bonds):

1. At CREATION time (before any further boolean touches the face), record
   `(name, centroid, unit normal, area)` into a `FaceRegistry`
   (`record`/`record_face`).
2. After ALL booleans on that body are done, `registry.match(body)` scans
   the body's FINAL faces and matches each registry entry by:
   centroid within `FACE_REGISTRY_CENTROID_TOL_MM` (0.5mm — absorbs kernel-
   fuzz-scale re-tessellation/splitting; rejects any other face on the same
   part, since bond faces are never closer than a leg thickness apart),
   `|dot(normal)| ≥ FACE_REGISTRY_NORMAL_DOT_MIN` (0.98, a ~11.5° cone),
   area within `FACE_REGISTRY_AREA_TOL_FRAC` (10%).
3. An UNMATCHED entry is a HARD `RuntimeError` listing every missing name —
   never skipped silently. "A boolean ate a bond face" is a real
   construction bug (a later cut removed material the registry expected
   to survive), and silently dropping the name would hide it.

Verified to survive both unrelated AND piercing booleans on the real
kernel; verified to survive a full STEP XDE round-trip (see
step-xde-naming.md). Naming convention observed everywhere this is used:
`<PART><LOCATOR>_<ROLE>_BOND[_SIDE]`, e.g.
`HINGE<n>_WING_CARRIER_BOND`, `RIB<y>_PI_<side><k>_LEG_BOND_{IN,OUT}`,
`SPAR<name>_RIB<y>_SLOT<k>_BOND_{IN,OUT}`.
