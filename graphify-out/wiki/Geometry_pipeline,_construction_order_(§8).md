# Geometry pipeline, construction order (§8)

> God node · 21 connections · `plan.md`

**Community:** [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md)

## Connections by Relation

### references
- WingStructGen — Architecture & Development Plan (plan.md) `EXTRACTED`
- F11 UIUC Selig/Lednicer confusion -> auto-detect + quarantine (P1, 0 silent failures) `EXTRACTED`
- F4 Tangent-face booleans at cove -> deliberate clearance angle (P4 tangency check) `EXTRACTED`
- False spar closing wall: flat sandwich cap built on the TE device cut plane, closes hollow interior boundary `EXTRACTED`
- F1 OCC shell/thicken fails at TE -> banned; IML by offset+loft+subtract (P6) `EXTRACTED`
- F15 Sandwich stack > local airfoil thickness -> P0 validation rule (<=80% min local thickness) `EXTRACTED`
- F17 Flat housing lip sits proud/sunk on curved OML -> lip cap rule + flushness gate (P18) `EXTRACTED`
- F18 Bolt preload crushes hollow composite tongue -> aluminum-only preload path; continuity gate (P18) `EXTRACTED`
- F19 Non-parallel tongues make panel un-insertable -> parallel-by-construction + insertion-sweep gate (P11) `EXTRACTED`
- F3 Boolean micro-shards poison downstream -> mandatory shard filter (P4+ gates) `EXTRACTED`
- F5 Twist pushes hinge axis out of OML mid-span -> sampled containment (P3) `EXTRACTED`
- F10 STEP loses body names -> XDE path, re-import gate (P9) `EXTRACTED`
- F12 .cdb writer drifts from spec -> spec-derived independent oracle parser (P13) `EXTRACTED`
- F13 Fictional third-party APIs (NeuralFoil-class) -> mandatory R0 probes; boundary mocking banned (§0) `EXTRACTED`
- F14 Mold undercuts at cove/blunt TE -> demold scan (P16) `EXTRACTED`
- F16 Ansys import passes proxies, fails in practice -> manual acceptance artifact required (P14) `EXTRACTED`
- F2 OCC segfault kills worker silently -> subprocess sandbox + reaper (P0 SIGKILL test) `EXTRACTED`
- F6 Non-developable spar webs -> distorted DXF -> developability metric, silent unroll = fail (P17) `EXTRACTED`
- F7 T-junction mesh: looks fine, structurally disconnected -> single-connected-component check (P13) `EXTRACTED`
- F8 .cdb unit mismatch (mm vs m) -> mm-tonne-s header asserted (P13) `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*