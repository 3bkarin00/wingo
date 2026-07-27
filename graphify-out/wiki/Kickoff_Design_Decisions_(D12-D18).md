# Kickoff Design Decisions (D12-D18)

> 19 nodes · cohesion 0.11

## Key Concepts

- **Input schema v0.2 (§6)** (23 connections) — `plan.md`
- **docker-compose.yml (postgres + redis dev stack)** (2 connections) — `docker-compose.yml`
- **D19 Persistence: Postgres (structured data) + Redis (queue/live state)** (2 connections) — `plan.md`
- **D2 Deployment: Coder cloud workspace, Docker Compose, port-forward viewer; standalone repo** (2 connections) — `plan.md`
- **D3 Devices: one TE hinged surface per half-span; LE droop dropped (ADR-004), slats deferred** (2 connections) — `plan.md`
- **D12 Fuselage attachment: parametric bolt bosses/hardpoints on center section** (1 connections) — `plan.md`
- **D13 Molds: full halves for ALL bodies; parting/flanges/pins; stock auto-sectioning** (1 connections) — `plan.md`
- **D14 FEA target: Ansys, both STEP-midsurface and .cdb routes** (1 connections) — `plan.md`
- **D15 Composites in Ansys: Mechanical layered shell sections, layup schedule export** (1 connections) — `plan.md`
- **D16 Ansys gate: CI proxy gates + formal manual acceptance checklist** (1 connections) — `plan.md`
- **D17 Materials: built-in library + custom entries, Postgres** (1 connections) — `plan.md`
- **D18 Airfoils: NACA 4+5 builtin + vendored UIUC snapshot + .dat upload** (1 connections) — `plan.md`
- **D21 Sequencing: R1 core -> R1.5 segmentation -> R2 Ansys -> R3 molds -> R4 reports/DXF/joint hardware detail** (1 connections) — `plan.md`
- **D22 Mold hardware: CNC defaults (flange 40mm, dowel dia 8, fit params), schema-overridable** (1 connections) — `plan.md`
- **D4 Device placement: fully contained within one wing segment** (1 connections) — `plan.md`
- **D5 Manufacturing: composite molded sandwich skin, molded internals** (1 connections) — `plan.md`
- **D6 Trailing edge: blunt TE forced, te_min_thickness_mm** (1 connections) — `plan.md`
- **D7 Wing architecture: 3-piece (center+L+R); per-segment dihedral/sweep** (1 connections) — `plan.md`
- **D9 Hinges: generated printable OR COTS placeholder pockets** (1 connections) — `plan.md`

## Relationships

- [Joint Retention Design (D8/D10/ADR-001)](Joint_Retention_Design_%28D8-D10-ADR-001%29.md) (3 shared connections)
- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (1 shared connections)
- [Agent Instructions & Conventions](Agent_Instructions_%26_Conventions.md) (1 shared connections)
- [Web UI & Segmentation Phases](Web_UI_%26_Segmentation_Phases.md) (1 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (1 shared connections)

## Source Files

- `docker-compose.yml`
- `plan.md`

## Audit Trail

- EXTRACTED: 45 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*