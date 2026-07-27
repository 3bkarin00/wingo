# Phase Plan & Failure Modes (F1/F9/F10)

> 13 nodes · cohesion 0.19

## Key Concepts

- **Phase plan overview with executable gates (§9)** (26 connections) — `plan.md`
- **P8 — Kinematic gate (the decisive R1 gate)** (5 connections) — `plan.md`
- **P6 — Sandwich internals + hardpoints** (4 connections) — `plan.md`
- **P9 — Export (glTF/STL/STEP)** (4 connections) — `plan.md`
- **F1 OCC shell/thicken fails at TE -> banned; IML by offset+loft+subtract (P6)** (3 connections) — `plan.md`
- **P7 — Hinges (generated mode)** (3 connections) — `plan.md`
- **F10 STEP loses body names -> XDE path, re-import gate (P9)** (2 connections) — `plan.md`
- **F9 Sweep misses collision between samples -> fine steps + swept-volume boolean (P8)** (2 connections) — `plan.md`
- **R1: one-piece wing core (P0-P10 gates green + regress)** (1 connections) — `plan.md`
- **R1.5: segmentation (P11 gates green + regress)** (1 connections) — `plan.md`
- **R2: Ansys package (P12-P13 CI gates + P14 signed manual acceptance)** (1 connections) — `plan.md`
- **R3: molds (P15-P16 gates green)** (1 connections) — `plan.md`
- **R4: bilingual report, DXF, joint retention hardware, COTS hinge mode (P17-P19 gates green)** (1 connections) — `plan.md`

## Relationships

- [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md) (8 shared connections)
- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (4 shared connections)
- [Web UI & Segmentation Phases](Web_UI_%26_Segmentation_Phases.md) (4 shared connections)
- [R0 Findings — P1 Airfoil Subsystem](R0_Findings_%E2%80%94_P1_Airfoil_Subsystem.md) (3 shared connections)
- [Joint Retention Design (D8/D10/ADR-001)](Joint_Retention_Design_%28D8-D10-ADR-001%29.md) (2 shared connections)
- [R0 Probes — OCC/Gmsh Kernel](R0_Probes_%E2%80%94_OCC-Gmsh_Kernel.md) (1 shared connections)
- [Agent Instructions & Conventions](Agent_Instructions_%26_Conventions.md) (1 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (1 shared connections)

## Source Files

- `plan.md`

## Audit Trail

- EXTRACTED: 54 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*