# Input schema v0.2 (§6)

> God node · 23 connections · `plan.md`

**Community:** [Kickoff Design Decisions (D12-D18)](Kickoff_Design_Decisions_%28D12-D18%29.md)

## Connections by Relation

### references
- WingStructGen — Architecture & Development Plan (plan.md) `EXTRACTED`
- D11 Core: ramped drop-offs at edges/hinge lands/joint housing zones `EXTRACTED`
- D1 Interaction: Web UI, three.js viewer, body toggles + deflection slider (v1) `EXTRACTED`
- D10 Joint retention: 1 vertical Z-bolt per housing, aluminum-only preload path `EXTRACTED`
- D19 Persistence: Postgres (structured data) + Redis (queue/live state) `EXTRACTED`
- D2 Deployment: Coder cloud workspace, Docker Compose, port-forward viewer; standalone repo `EXTRACTED`
- D20 Reports: bilingual EN/AR, lualatex RTL `EXTRACTED`
- D3 Devices: one TE hinged surface per half-span; LE droop dropped (ADR-004), slats deferred `EXTRACTED`
- D8 Segment joints: both spars carry male tongues into female boxes, insertion-axis-parallel `EXTRACTED`
- D12 Fuselage attachment: parametric bolt bosses/hardpoints on center section `EXTRACTED`
- D13 Molds: full halves for ALL bodies; parting/flanges/pins; stock auto-sectioning `EXTRACTED`
- D14 FEA target: Ansys, both STEP-midsurface and .cdb routes `EXTRACTED`
- D15 Composites in Ansys: Mechanical layered shell sections, layup schedule export `EXTRACTED`
- D16 Ansys gate: CI proxy gates + formal manual acceptance checklist `EXTRACTED`
- D17 Materials: built-in library + custom entries, Postgres `EXTRACTED`
- D18 Airfoils: NACA 4+5 builtin + vendored UIUC snapshot + .dat upload `EXTRACTED`
- D21 Sequencing: R1 core -> R1.5 segmentation -> R2 Ansys -> R3 molds -> R4 reports/DXF/joint hardware detail `EXTRACTED`
- D22 Mold hardware: CNC defaults (flange 40mm, dowel dia 8, fit params), schema-overridable `EXTRACTED`
- D4 Device placement: fully contained within one wing segment `EXTRACTED`
- D5 Manufacturing: composite molded sandwich skin, molded internals `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*