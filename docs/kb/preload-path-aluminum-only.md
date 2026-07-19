---
title: Joint-retention bolt preload path is aluminum-only, never crosses composite
tags: [joint-retention, d10, adr-001, design-rule, f17, f18]
source: "plan.md D10; docs/decisions/ADR-001-bolted-spar-retention.md"
phase: p18
confidence: probable
last_updated: 2026-07-19
---

ADR-001 replaced an over-center toggle-latch segment-joint mechanism with
bolted spar retention specifically to get this property: 1 vertical Z-bolt
per housing (2 per break) — countersunk head seats on an ALUMINUM lip that
penetrates the upper skin → aluminum housing top → aluminum side walls →
integral threaded aluminum bottom boss. The preload path never touches
composite. Tongue holes (in the composite spar tongue itself) are
CLEARANCE fits, not preload-bearing — the bolt acts purely as a shear pin
against spanwise withdrawal, not as the joint-closing mechanism.

Why this matters as a standalone rule (not just "how D10 happens to work"):
composite has poor through-thickness bearing/crush strength compared to
its in-plane strength — running bolt preload through a hollow composite
tongue risks crushing it (F18, explicitly registered). Any FUTURE joint-
hardware design in this project must preserve "preload path is aluminum-
only" as an invariant, not just replicate the current bolt count/housing
shape. Gated by the not-yet-built P18 preload-path-continuity gate +
P11's insertion-sweep gate (parallel-tongues-by-construction, F19) —
`confidence: probable` here because the DESIGN rule is locked (ADR-001,
D10) but the P18 gate that verifies it in real geometry hasn't been built
yet (R4 scope, after R1/R1.5/R2/R3).
