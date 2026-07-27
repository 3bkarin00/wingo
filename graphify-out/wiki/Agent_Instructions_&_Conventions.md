# Agent Instructions & Conventions

> 26 nodes · cohesion 0.10

## Key Concepts

- **WingStructGen — Architecture & Development Plan (plan.md)** (9 connections) — `plan.md`
- **Conventions (docs/conventions.md, single source of truth)** (8 connections) — `docs/conventions.md`
- **Agent execution protocol (§0)** (6 connections) — `plan.md`
- **WingStructGen Agent Instructions (CLAUDE.md)** (5 connections) — `CLAUDE.md`
- **WingStructGen Agent Instructions (AGENTS.md, generated)** (4 connections) — `AGENTS.md`
- **Hard rules / anti-pattern rejection list (§0.2)** (4 connections) — `plan.md`
- **Phase workflow — mandatory sequence (§0.1)** (4 connections) — `plan.md`
- **Hard rules (anti-pattern rejection list, distilled)** (3 connections) — `CLAUDE.md`
- **Session protocol (START/END)** (3 connections) — `CLAUDE.md`
- **Phase workflow (7-step, distilled)** (2 connections) — `CLAUDE.md`
- **Hinge/latch axes convention: derived first as straight 3D lines** (2 connections) — `docs/conventions.md`
- **Signs convention: TE trailing-edge-down positive deflection** (2 connections) — `docs/conventions.md`
- **F13 Fictional third-party APIs (NeuralFoil-class) -> mandatory R0 probes; boundary mocking banned (§0)** (2 connections) — `plan.md`
- **Repo memory files: handoff.md/state.json/changelog.md/tolerances.py/known_issues.md/ADRs (§0.5)** (2 connections) — `plan.md`
- **Airfoils convention: unit chord, TE->upper->LE->lower->TE, cosine resample** (1 connections) — `docs/conventions.md`
- **Frame convention: X aft, Y starboard, Z up, right-handed** (1 connections) — `docs/conventions.md`
- **Naming contract: SEG-{C|L|R}/BODY-{name}/ROLE-{...}** (1 connections) — `docs/conventions.md`
- **Twist axis convention: user-declared twist_axis_xc** (1 connections) — `docs/conventions.md`
- **Units convention: mm/deg, suffixed schema fields** (1 connections) — `docs/conventions.md`
- **Postgres data model (§7)** (1 connections) — `plan.md`
- **Mission: parametric composite wing generator, no in-house FEA** (1 connections) — `plan.md`
- **Phase gate concept (executable pytest, pass/fail artifact)** (1 connections) — `plan.md`
- **R0 probe methodology (probe real 3rd-party boundary before implementing)** (1 connections) — `plan.md`
- **Repository layout (§0.4)** (1 connections) — `plan.md`
- **Self-verification answer: gates as the proof mechanism (§0.3)** (1 connections) — `plan.md`
- *... and 1 more nodes in this community*

## Relationships

- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (2 shared connections)
- [Failure Modes F6-F16 (Mfg/Export)](Failure_Modes_F6-F16_%28Mfg-Export%29.md) (2 shared connections)
- [Kickoff Design Decisions (D12-D18)](Kickoff_Design_Decisions_%28D12-D18%29.md) (1 shared connections)
- [Phase Plan & Failure Modes (F1/F9/F10)](Phase_Plan_%26_Failure_Modes_%28F1-F9-F10%29.md) (1 shared connections)

## Source Files

- `AGENTS.md`
- `CLAUDE.md`
- `docs/conventions.md`
- `plan.md`

## Audit Trail

- EXTRACTED: 68 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*