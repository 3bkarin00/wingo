---
title: CS nose/wing cove are ONE axis-centered arc per station, hinge-axis height is DERIVED not assumed
tags: [hinges, cove-nose, adr-002, adr-003, conventions]
source: "docs/decisions/ADR-002, ADR-003; docs/conventions.md; docs/r0_findings/p04.md"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

Locked construction (docs/conventions.md: "Hinge/latch axes: derived FIRST
as perfectly straight 3D lines; every hinge mechanism is then defined
relative to its axis, never the reverse"):

- At each station (a plane ⟂ the hinge axis), `C` = the hinge-axis point in
  that plane. `Pu`/`Pl` = the NEAREST-POINT ("normal foot") projections of
  `C` onto the upper/lower OML skin. The nearest-point vector `C→P` is
  ALWAYS ⟂ the skin's local tangent — a property of nearest-point
  projection itself, not a solved/iterated constraint — so a circular arc
  centered on `C` through `P` is tangent to the skin at `P` BY
  CONSTRUCTION. R0-measured: `C→Pu` deviates 0.40° from perpendicular
  (≈0, confirms tangency).
- CS nose = ONE arc at `R=(Ru+Rl)/2` (ADR-003 deleted the earlier two-arc/
  Hermite-blend branch — see hinge-axis-twist-radius-asymmetry.md for why).
- Wing cove = a SEPARATE concentric arc at the SAME `C`, radius
  `R + COVE_CLEARANCE_MM` (5.0mm) — never tangent to the nose (F4), and
  because both are centered on the same axis point at every station, this
  radial offset is invariant under rotation about the axis at ANY
  deflection angle, not just at rest.
- The hinge-axis HEIGHT itself is DERIVED (least-squares fit to the true
  equidistant-from-skin point along the span), never assumed/hardcoded —
  this is what "axis derived first" means concretely for this construction.

Per-station profiles are lofted (`ruled=True`, matching the OML's own P2
loft convention) into nose/cove REGION solids that then play the exact role
a cruder cylinder-pair construction (P4-v1, retired by ADR-002) used to
play in the wing/CS boolean split.
