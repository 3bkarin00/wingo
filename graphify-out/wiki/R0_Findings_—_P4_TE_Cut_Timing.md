# R0 Findings — P4 TE Cut Timing

> 10 nodes · cohesion 0.27

## Key Concepts

- **R0 Findings — P4 (TE surface cut)** (7 connections) — `docs/r0_findings/p04.md`
- **2026-07-07 P4 refined per-station construction: audit fixes + test-architecture overhaul** (6 connections) — `changelog.md`
- **Known Issues — OCC/Gmsh/ezdxf workaround knowledge base** (4 connections) — `docs/known_issues.md`
- **P6 sandwich-shell booleans: hollow_common dominates, ~4.6x run-to-run variance** (4 connections) — `docs/known_issues.md`
- **Twisted/tilted device configs cost 2-4x more per boolean than untwisted** (4 connections) — `docs/known_issues.md`
- **tests/gates/geometry_cache.py (disk cache for OCC boolean construction output)** (4 connections) — `changelog.md`
- **GEOMETRY_TEST_TIMEOUT_S = 600 (pytest-timeout budget for geometry gate tests)** (2 connections) — `changelog.md`
- **probe_brep_cache.py: exportBrep/importBrep round-trip exact, enables geometry build cache** (2 connections) — `docs/r0_findings/p04.md`
- **probe_ocp_section_loft.py: per-station normal-foot arcs tangent to skin by construction** (2 connections) — `docs/r0_findings/p04.md`
- **Where things live (repo memory file map)** (1 connections) — `CLAUDE.md`

## Relationships

- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (4 shared connections)
- [R0 Probes — OCC/Gmsh Kernel](R0_Probes_%E2%80%94_OCC-Gmsh_Kernel.md) (4 shared connections)
- [Changelog & Validator Constants](Changelog_%26_Validator_Constants.md) (2 shared connections)
- [Tolerance Constants (P3)](Tolerance_Constants_%28P3%29.md) (1 shared connections)
- [R0 Findings — P2 OML Loft](R0_Findings_%E2%80%94_P2_OML_Loft.md) (1 shared connections)

## Source Files

- `CLAUDE.md`
- `changelog.md`
- `docs/known_issues.md`
- `docs/r0_findings/p04.md`

## Audit Trail

- EXTRACTED: 34 (94%)
- INFERRED: 2 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*