# Tolerance Constants (P3)

> 7 nodes · cohesion 0.33

## Key Concepts

- **backend/tolerances.py (every numeric tolerance in the tool)** (7 connections) — `CLAUDE.md`
- **2026-07-05 P3 (Reference geometry) DONE entry** (5 connections) — `changelog.md`
- **COVE_CLEARANCE_MM = 5.0 (nose-to-cove radial clearance)** (2 connections) — `docs/decisions/ADR-002-per-station-arc-cove-nose.md`
- **KERNEL_TOLERANCE_MM (reused in place of a bare 1e-5 literal in P3 gate)** (2 connections) — `changelog.md`
- **NOSE_TANGENCY_MAX_DEG = 2.0 deg (mean-radius tangency error gate, calibrated from measurement)** (2 connections) — `docs/decisions/ADR-003-single-arc-derived-axis.md`
- **OVERLAP_MARGIN_DEG = 4.0 deg (anti-unporting angular overlap margin)** (2 connections) — `docs/decisions/ADR-003-single-arc-derived-axis.md`
- **PLY_THICKNESS_MM_PROVISIONAL (promoted from validators.py private dict to tolerances.py)** (2 connections) — `changelog.md`

## Relationships

- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (3 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (3 shared connections)
- [R0 Findings — P4 TE Cut Timing](R0_Findings_%E2%80%94_P4_TE_Cut_Timing.md) (1 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (1 shared connections)

## Source Files

- `CLAUDE.md`
- `changelog.md`
- `docs/decisions/ADR-002-per-station-arc-cove-nose.md`
- `docs/decisions/ADR-003-single-arc-derived-axis.md`

## Audit Trail

- EXTRACTED: 22 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*