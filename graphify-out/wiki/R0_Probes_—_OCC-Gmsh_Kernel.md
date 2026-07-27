# R0 Probes — OCC/Gmsh Kernel

> 12 nodes · cohesion 0.17

## Key Concepts

- **IML construction plan: per-station offset + ruled loft + fuzzy_cut, never OCC shell/thicken** (5 connections) — `docs/r0_findings/p06.md`
- **Handoff — 2026-07-09** (5 connections) — `handoff.md`
- **False spar closing wall: flat sandwich cap built on the TE device cut plane, closes hollow interior boundary** (3 connections) — `docs/r0_findings/p06.md`
- **OCP/gmsh ImportError: libGL.so.1 / libXcursor.so.1 missing** (3 connections) — `docs/known_issues.md`
- **R0 Findings — P0** (3 connections) — `docs/r0_findings/p00.md`
- **backend/geometry/booleans.py (fuzzy_cut/fuzzy_common + shard filter helpers)** (2 connections) — `docs/r0_findings/p04.md`
- **backend/geometry/iml.py (sandwich IML construction)** (2 connections) — `docs/r0_findings/p06.md`
- **probe_ocp_boolean.py: cut->Compound, SetFuzzyValue, tilted cylinders, shard behavior** (2 connections) — `docs/r0_findings/p04.md`
- **Next single action: false-spar closing wall + device-region sandwich fidelity** (2 connections) — `handoff.md`
- **probe_gmsh.py: gmsh 4.15.2 mesh generation confirmed** (1 connections) — `docs/r0_findings/p00.md`
- **probe_ocp.py: cadquery 2.8.0 import/box/IsValid confirmed** (1 connections) — `docs/r0_findings/p00.md`
- **Do-not-touch: iml.py triple-offset chain, ADR-003 arc/axis construction, geometry cache usage** (1 connections) — `handoff.md`

## Relationships

- [R0 Findings — P4 TE Cut Timing](R0_Findings_%E2%80%94_P4_TE_Cut_Timing.md) (4 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (2 shared connections)
- [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md) (1 shared connections)
- [Phase Plan & Failure Modes (F1/F9/F10)](Phase_Plan_%26_Failure_Modes_%28F1-F9-F10%29.md) (1 shared connections)

## Source Files

- `docs/known_issues.md`
- `docs/r0_findings/p00.md`
- `docs/r0_findings/p04.md`
- `docs/r0_findings/p06.md`
- `handoff.md`

## Audit Trail

- EXTRACTED: 30 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*