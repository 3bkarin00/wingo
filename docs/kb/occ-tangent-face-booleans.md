---
title: "F4 — never exact tangency between bodies in a boolean; always a deliberate clearance/fuzzy value"
tags: [occ, boolean, tangency, hard-rule, f4]
source: "plan.md §10 F4, §0.2 hard rules; docs/r0_findings/p04.md; docs/decisions/ADR-002, ADR-003"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

Two coaxial/coincident faces in a boolean operand (e.g. a cove arc and a
nose arc at the exact same radius+center) is an unstable-boolean hazard —
OCC can produce inconsistent or degenerate results at an exact tangency.
Hard rule (CLAUDE.md): never construct exact tangency between two bodies a
boolean will operate on; always leave a deliberate, explicit clearance, OR
hand the boolean an explicit fuzzy value.

Two independent mechanisms in this codebase, used for different reasons:
1. **Deliberate clearance angle/radius**: the wing cove arc and CS nose arc
   share the same axis-centered point `C` but use DIFFERENT radii
   (`R_cove = max(Ru,Rl) + COVE_CLEARANCE_MM`) — distinct radii ⇒ never
   tangent, by construction, at every deflection angle (ADR-002/ADR-003).
   `FACE_TANGENCY_TOLERANCE_MM` (0.1mm) is the gate-side check: two
   cylindrical faces whose radii differ by less than this are treated as
   effectively tangent and fail the check.
2. **Explicit fuzzy value**: `BRepAlgoAPI_Cut(...).SetFuzzyValue(1e-3)` —
   `BOOLEAN_FUZZY_VALUE_MM = 1.0e-3` gives the kernel a larger merge
   tolerance than its own default (`Precision::Confusion` = 1e-4mm) to
   resolve near-coincident edges robustly at the cove without visibly
   moving geometry. `backend.geometry.booleans.fuzzy_cut`/`fuzzy_common`
   are the only sanctioned entry points for this — always route boolean
   ops through them rather than calling `BRepAlgoAPI_*` directly.
