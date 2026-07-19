---
title: "Type IML/cove-fidelity fields as cq.Shape, not cq.Solid — a fuzzy_cut against a curved cove can return a Compound"
tags: [occ, typing, iml, cove-nose]
source: "handoff.md do-not-touch note (2026-07-13); backend/geometry/iml.py SandwichLofts, backend/geometry/false_spar.py"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

`SandwichLofts`'s three IML fields (`face_iml_solid`, `core_iml_solid`,
`hollow_iml_solid`) and `false_spar.build_false_spar`'s
`hollow_iml_solid` parameter are typed `cq.Shape`, deliberately NOT the
narrower `cq.Solid` — inside a device window, the cove-fidelity cut
(following the true cove-cut boundary instead of the plain uncut airfoil)
can legitimately return a `Compound` rather than a single `Solid`, and
narrowing the type back to `cq.Solid` would either be a lie (still
runtime-Compound, type-checker wrong) or force an unwarranted single-solid
assumption into call sites that don't actually need one.

General lesson: when a fuzzy boolean's OUTPUT SHAPE depends on config
(clean-span vs. device-window-affected, in this case), don't over-narrow
its type just because the common/tested case happens to be a single solid
— type it for what the operation can ACTUALLY return, and let
`filter_shards`/explicit `.Solids()` calls at the point of use handle the
Compound case rather than assuming it away upstream.
