---
title: Wing twist grows the upper/lower normal-foot radius mismatch (Ru≠Rl) roughly linearly
tags: [hinges, twist, tolerances, cove-nose, adr-003]
source: "backend/tolerances.py NOSE_TANGENCY_MAX_DEG derivation; docs/r0_findings/p04.md; ADR-003"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

The single-arc nose/cove construction (ADR-003) uses one radius
`R = (Ru+Rl)/2` per station, where `Ru`/`Rl` are the normal-foot distances
from the hinge-axis point `C` to the upper/lower OML skin. On a symmetric,
untwisted section `Ru≈Rl` and the mean-radius approximation is nearly
exact. Twist breaks that symmetry: measured directly, tangency error scales
roughly LINEARLY with twist at ~1.7° of residual tangency error per degree
of tip twist, at a realistic aft hinge_xc (0.70-0.75, the only region a rear
spar leaves valid).

This is WHY `NOSE_TANGENCY_MAX_DEG = 2.0°` exists as a config-time
REJECTION (not a warning, not a silently-degraded construction) in
`backend/geometry/te_cut.py` — 2.0° accommodates a real 1° tip-twist config
(1.70° residual, ~15% margin) while still rejecting the project's own
extreme-twist edge case (`te_half_twisted.yaml`, -8° tip, ~16.75°
residual). Do NOT add a conditional construction branch keyed on twist
magnitude (e.g. "use two arcs when twist is large") — the two-arc/Hermite-
blend branch that used to exist for exactly this case was DELETED in
ADR-003 after its curvature discontinuity produced a visibly lumpy nose on
any twisted config; the fix was fail-fast validation, not a smarter
construction branch.
