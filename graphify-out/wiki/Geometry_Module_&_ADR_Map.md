# Geometry Module & ADR Map

> 13 nodes · cohesion 0.27

## Key Concepts

- **ADR-003: Single-arc nose + derived hinge-axis height replaces two-arc/Hermite blend** (13 connections) — `docs/decisions/ADR-003-single-arc-derived-axis.md`
- **ADR-004: Drop LE droop from scope** (12 connections) — `docs/decisions/ADR-004-drop-le-droop.md`
- **ADR-002: Per-station axis-centered arcs replace cylinder cove/nose mechanism** (9 connections) — `docs/decisions/ADR-002-per-station-arc-cove-nose.md`
- **P4 — TE surface cut** (7 connections) — `plan.md`
- **backend/geometry/reference.py (spar surfaces, rib planes, hinge axes, hardpoints)** (4 connections) — `docs/r0_findings/p03.md`
- **F4 Tangent-face booleans at cove -> deliberate clearance angle (P4 tangency check)** (4 connections) — `plan.md`
- **P5 — retired (ADR-004, LE droop dropped from scope)** (4 connections) — `plan.md`
- **backend/geometry/cove_profile.py (per-station cove/nose arc profiles)** (3 connections) — `docs/decisions/ADR-002-per-station-arc-cove-nose.md`
- **backend/geometry/te_cut.py (TE surface cut construction)** (3 connections) — `docs/r0_findings/p04.md`
- **TE cut construction plan: nested cylinders + aft half-space box, exact volume conservation by set algebra** (3 connections) — `docs/r0_findings/p04.md`
- **F3 Boolean micro-shards poison downstream -> mandatory shard filter (P4+ gates)** (3 connections) — `plan.md`
- **backend/schema/errors.py (ConfigErrorCode enum)** (1 connections) — `docs/decisions/ADR-004-drop-le-droop.md`
- **backend/schema/models.py (Config schema models)** (1 connections) — `docs/decisions/ADR-004-drop-le-droop.md`

## Relationships

- [R0 Findings — P4 TE Cut Timing](R0_Findings_%E2%80%94_P4_TE_Cut_Timing.md) (4 shared connections)
- [Phase Plan & Failure Modes (F1/F9/F10)](Phase_Plan_%26_Failure_Modes_%28F1-F9-F10%29.md) (4 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (3 shared connections)
- [Tolerance Constants (P3)](Tolerance_Constants_%28P3%29.md) (3 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (2 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (2 shared connections)
- [Agent Instructions & Conventions](Agent_Instructions_%26_Conventions.md) (2 shared connections)
- [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md) (2 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (1 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (1 shared connections)
- [Kickoff Design Decisions (D12-D18)](Kickoff_Design_Decisions_%28D12-D18%29.md) (1 shared connections)

## Source Files

- `docs/decisions/ADR-002-per-station-arc-cove-nose.md`
- `docs/decisions/ADR-003-single-arc-derived-axis.md`
- `docs/decisions/ADR-004-drop-le-droop.md`
- `docs/r0_findings/p03.md`
- `docs/r0_findings/p04.md`
- `plan.md`

## Audit Trail

- EXTRACTED: 67 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*