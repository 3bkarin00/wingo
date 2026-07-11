# R0 Findings — P1 Airfoil Subsystem

> 10 nodes · cohesion 0.24

## Key Concepts

- **P1 — Airfoil subsystem (NACA generators, UIUC ingest, resample)** (5 connections) — `plan.md`
- **F11 UIUC Selig/Lednicer confusion -> auto-detect + quarantine (P1, 0 silent failures)** (4 connections) — `plan.md`
- **P0 — Foundation (repo scaffold, schema validation, worker sandbox)** (4 connections) — `plan.md`
- **P2 — Sections + OML loft** (4 connections) — `plan.md`
- **UIUC airfoil snapshot README** (3 connections) — `data/uiuc_snapshot/README.md`
- **Selig/Lednicer detection heuristic: threshold revised 1.0->1.5** (3 connections) — `docs/r0_findings/p01.md`
- **F15 Sandwich stack > local airfoil thickness -> P0 validation rule (<=80% min local thickness)** (3 connections) — `plan.md`
- **_quarantine_me.dat: intentionally malformed quarantine fixture** (2 connections) — `data/uiuc_snapshot/README.md`
- **F2 OCC segfault kills worker silently -> subprocess sandbox + reaper (P0 SIGKILL test)** (2 connections) — `plan.md`
- **R0 Findings — P1 (Airfoil subsystem)** (1 connections) — `docs/r0_findings/p01.md`

## Relationships

- [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md) (3 shared connections)
- [Phase Plan & Failure Modes (F1/F9/F10)](Phase_Plan_%26_Failure_Modes_%28F1-F9-F10%29.md) (3 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (1 shared connections)
- [R0 Findings — P2 OML Loft](R0_Findings_%E2%80%94_P2_OML_Loft.md) (1 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (1 shared connections)

## Source Files

- `data/uiuc_snapshot/README.md`
- `docs/r0_findings/p01.md`
- `plan.md`

## Audit Trail

- EXTRACTED: 31 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*