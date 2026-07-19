---
title: "P0 config validation rejects with actionable error codes at submit time — never a silent downstream degrade"
tags: [validation, schema, design-rule, p0]
source: "plan.md §6 P0 validation rules; backend/schema/validators.py, errors.py"
phase: p00
confidence: verified
last_updated: 2026-07-19
---

Every cross-field geometric/manufacturing constraint this project knows
about in advance is checked at CONFIG-SUBMIT time, with a specific
`ConfigErrorCode` and an actionable message — not discovered later as a
confusing construction failure or, worse, a silently-wrong body. Examples
already built: device window must be segment-contained (D4); TE hinge must
clear the rear spar; sandwich stack ≤ 80% of local min airfoil thickness
(F15); `gap_mm` ≥ 2x tessellation tolerance AND ≥ 10x kernel tolerance;
`NOSE_TANGENCY_MAX_DEG` twist rejection (see hinge-axis-twist-radius-
asymmetry.md); interlock tab/slot batteries that don't fit a spar's usable
web height (D25).

Pattern to follow for any NEW geometric precondition discovered during
construction: if it's a genuine config-level constraint (not just an
implementation detail), add it as a P0 validator with its own error code,
don't just let the construction code raise a generic exception deep in a
boolean chain. `backend/schema/validators.py`'s own separation from
`models.py` field constraints exists exactly so this rule set (which grows
phase by phase) doesn't bloat the field definitions — see `models.py`'s own
module docstring. A rejected config with an actionable message is a
FEATURE (the P0 gate explicitly tests that every `tests/configs/invalid/*`
config is rejected with the RIGHT code), not a UX rough edge to soften.
