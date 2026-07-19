---
title: The nose arc extends past its tangent points by max_deflection + a margin, or it "unports" at full deflection
tags: [hinges, cove-nose, design-rule, adr-003]
source: "backend/tolerances.py OVERLAP_MARGIN_DEG; docs/decisions/ADR-003"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

If the CS nose arc's angular extent stopped exactly at the tangent points
`Pu`/`Pl`, it would rotate clear of the fixed wing's cove lips before
reaching `max_deflection_deg` — the nose edge "unports" (exposes itself to
airflow, loses the sealed cove contact) well before full deflection, which
a naive geometric construction would not catch (both bodies still valid
solids, nothing fails a boolean check — this is a KINEMATIC defect, not a
construction-validity one).

Fix: extend the nose arc beyond each tangent point by
`max_deflection_deg + OVERLAP_MARGIN_DEG` (4.0°, a fixed design-practice
margin — NOT config-derived like most of this project's tolerances; the
comment in `tolerances.py` is explicit that it's a fixed margin, not fit to
observed geometry, choosing the middle of the standard 3-5° practice
range) so the curved nose still overlaps the wing cove lips at full
deflection in both directions. Schema override:
`te_surface.overlap_margin_deg` (None → use the tolerances.py default).
Between multiple hinge stations along one device window, this overlap is
what keeps the swept nose envelope continuous rather than gapping.
