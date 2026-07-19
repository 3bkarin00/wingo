---
title: Twisted/tilted device configs cost 2-4x more per boolean than untwisted ones
tags: [occ, boolean, performance, te-cut, incident]
source: "docs/known_issues.md (migrated); artifacts/gates/p04_timings.json, docs/r0_findings/p04.md"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

Measured directly (cold cache): `te_half` (untwisted) vs `te_half_twisted`
(-8° tip twist) — `wing_cut_s` 28.6s → 60.2s (2.1x), `cs_common_s` 20.0s →
83.7s (4.2x). Lofting and per-station analytic sectioning are IDENTICAL
between the two configs (0.53s / 0.02s each) — the cost lives entirely in
`BRepAlgoAPI_Cut`/`Common` themselves. Twist tilts the station cutting
planes relative to the OML's own ruled facets, so the boolean's face-face
intersection curves are more numerous and less axis-aligned — a standard
OCC cost driver, not a construction defect.

No construction-strategy change was applied — no single boolean exceeded
~120s (well inside `GEOMETRY_TEST_TIMEOUT_S`=600s), and the actual pain
(every gate re-run repaying this cost) is what `tests/gates/
geometry_cache.py` solves instead (unchanged config+code re-run costs
< 1s). Do NOT tune fidelity down (fewer stations, coarser sections, looser
fuzzy value) to shave a one-time cold-build cost that no longer sits in the
iteration loop — that trades real geometric precision for an already-solved
problem. Revisit only if a future config's cold build actually approaches
the timeout budget.
