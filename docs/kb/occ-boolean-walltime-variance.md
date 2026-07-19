---
title: Identical OCC boolean workloads vary up to ~4.6x run-to-run on the shared Coder VM
tags: [occ, boolean, performance, sandwich, coder-workspace, incident]
source: "docs/known_issues.md (migrated); backend/geometry/iml.py timings_s instrumentation"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

Two findings from the SAME instrumented measurements
(`SandwichLofts.timings_s` / `SandwichBody.timings_s`, `te_half_twisted_
moderate.yaml`):

1. **Cost ranking inside `iml.py`**: per-station wire offsets + both ruled
   lofts are trivial (< 1s total). The three downstream booleans dominate,
   unevenly: `face_sheet_cut` 226.9s, `core_cut` 33.9s, `hollow_common`
   370.2s (~59% of the total on its own). Two thin near-parallel offset
   shells intersecting a full device-cut body is exactly the
   near-coincident-face geometry OCC booleans are slowest at.
2. **Run-to-run variance**: the SAME three booleans, same config, same code,
   same machine, fresh process both times — 136.6s in one run, 631.0s in
   another (~4.6x), no other visible load (load avg ~1, single process at
   ~100% CPU). Also independently reproduced on P6's own gate:
   `core_ring_s` measured 653s → 1209s → 1721s → 1697s → 1710s across five
   runs with IDENTICAL code+config. OCC boolean wall-time on this shared VM
   is NOT a stable quantity.

**Rule this implies**: never treat a single wall-clock measurement as a
config's true cost, and never use a wall-clock ratio between two RUNS as
evidence of a code regression — compare per-stage `timings_s` ratios WITHIN
the same run instead. A "gate suddenly got Nx slower" observation on this
workspace is noise until the per-stage breakdown disagrees qualitatively,
not just in magnitude. Practical mitigation:
`build_sandwich_body(include_hollow_interior=False)` skips the expensive
`hollow_common` boolean for callers that only need the two shells (the dev
viewer uses this); the real P6 pipeline always needs the cavity (ribs/spars
are built inside it) and pays the full cost.
