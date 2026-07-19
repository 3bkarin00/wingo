---
title: "F3 — every boolean output must be shard-filtered by volume before use"
tags: [occ, boolean, hard-rule, f3]
source: "plan.md §10 F3, §0.2 hard rules; backend/geometry/booleans.py filter_shards"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

A `BRepAlgoAPI` boolean (cut/common/fuse) can return a compound containing
one real body plus several micro-fragment "shards" — degenerate slivers
from near-coincident faces, not real geometry. Undetected, these poison
every downstream step (volume sums, watertightness checks, further
booleans against a shard instead of the real body).

Mandatory mitigation (CLAUDE.md hard rule: "never skip the shard filter
after a boolean"): `backend.geometry.booleans.filter_shards(shape,
min_volume=None)` splits a boolean result's solids into `(kept, shards)` by
a volume threshold — default `SHARD_MIN_VOLUME_MM3 = 1.0`, chosen because a
real wing part is at least ~10^4 mm³ and a boolean shard is typically
< 1 mm³, so 1.0 sits far below any legitimate body and far above kernel
noise with wide margin either way. Gates assert `len(shards) == 0`
explicitly (never silently discard a shard count without checking it's
zero) — a nonzero shard count on a real build is a real construction
defect to investigate, not routine noise to filter past.
