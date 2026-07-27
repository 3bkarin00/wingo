# Failure Modes F6-F16 (Mfg/Export)

> 12 nodes · cohesion 0.24

## Key Concepts

- **Geometry pipeline, construction order (§8)** (21 connections) — `plan.md`
- **P13 — .cdb writer + layup schedule** (6 connections) — `plan.md`
- **P14 — Manual Ansys acceptance (formal gate, human-executed)** (4 connections) — `plan.md`
- **P16 — Demold + stock sectioning** (4 connections) — `plan.md`
- **P17 — DXF flat patterns** (4 connections) — `plan.md`
- **P15 — Mold generation** (3 connections) — `plan.md`
- **F12 .cdb writer drifts from spec -> spec-derived independent oracle parser (P13)** (2 connections) — `plan.md`
- **F14 Mold undercuts at cove/blunt TE -> demold scan (P16)** (2 connections) — `plan.md`
- **F16 Ansys import passes proxies, fails in practice -> manual acceptance artifact required (P14)** (2 connections) — `plan.md`
- **F6 Non-developable spar webs -> distorted DXF -> developability metric, silent unroll = fail (P17)** (2 connections) — `plan.md`
- **F7 T-junction mesh: looks fine, structurally disconnected -> single-connected-component check (P13)** (2 connections) — `plan.md`
- **F8 .cdb unit mismatch (mm vs m) -> mm-tonne-s header asserted (P13)** (2 connections) — `plan.md`

## Relationships

- [Phase Plan & Failure Modes (F1/F9/F10)](Phase_Plan_%26_Failure_Modes_%28F1-F9-F10%29.md) (8 shared connections)
- [R0 Findings — P1 Airfoil Subsystem](R0_Findings_%E2%80%94_P1_Airfoil_Subsystem.md) (3 shared connections)
- [Joint Retention Design (D8/D10/ADR-001)](Joint_Retention_Design_%28D8-D10-ADR-001%29.md) (3 shared connections)
- [Agent Instructions & Conventions](Agent_Instructions_%26_Conventions.md) (2 shared connections)
- [Web UI & Segmentation Phases](Web_UI_%26_Segmentation_Phases.md) (2 shared connections)
- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (2 shared connections)
- [R0 Probes — OCC/Gmsh Kernel](R0_Probes_%E2%80%94_OCC-Gmsh_Kernel.md) (1 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (1 shared connections)

## Source Files

- `plan.md`

## Audit Trail

- EXTRACTED: 54 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*