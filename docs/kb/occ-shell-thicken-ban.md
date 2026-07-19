---
title: "F1 — never OCC shell/thicken for the IML; use 2D offset + loft + subtract"
tags: [occ, iml, sandwich, hard-rule, f1]
source: "plan.md §10 Failure-Mode Register F1, §0.2 hard rules; backend/geometry/iml.py; docs/r0_findings/p06.md"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

OCC's shell/thicken operation fails at the trailing edge (thin, near-zero
local thickness — exactly where a wing section is hardest for a generic
offset-shell algorithm). Banned outright (CLAUDE.md hard rule, F1 in the
failure-mode register) — never attempt it for the IML, don't rediscover
this by trying it again.

The working replacement, R0-probed before any construction code
(`probe_ocp_offset.py`, `probe_ocp_offset_3layer.py`): 2D per-station
`cq.Wire.offset2D(-distance, kind="intersection")`, THEN loft the offset
wires into a second solid, THEN subtract from the outer solid. A single
whole-loop offset by `d` shrinks local (upper-to-lower) thickness by `2d`
(both walls move inward together) — the sandwich panel is 3 layers PER
WALL (outer face / core / inner face), so the real chain is full-value, not
a total-thickness-budget offset:

```
face_IML   = OML_wire.offset2D(-face_mm)
core_IML   = face_IML.offset2D(-core_mm)
hollow_IML = core_IML.offset2D(-face_mm)
```

Where a section is locally thinner than `2*stack_mm`, the innermost offsets
SELF-CLIP (`kind="intersection"`) — the hollow vanishes and the walls merge
into solid laminate. This is a verified, accepted consequence of the offset
chain (still one valid closed wire per station, valid lofts, shard-free,
exact volume conservation), NOT a defect to "fix" by tuning offsets down —
a first implementation tried that and silently deleted the inner face
sheet (caught by product review, see `iml.py`'s own module docstring).
