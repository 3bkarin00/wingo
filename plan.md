# WingStructGen — Architecture & Development Plan

**Version:** 0.4 (agent-executable; joint redesign — bolted spar retention replaces toggle latches)
**Status:** Approved for P0 kickoff
**Classification:** Private / internal tool
**Executor:** Claude Code (inside Antigravity). This document is the master spec; the agent must treat it as normative.
**Methodology:** Phase-gated, release-train delivery. Every phase = **R0 probe → implement → executable gate**. A phase is DONE if and only if its gate command exits 0 and writes a gate artifact. No exceptions.

---

## 0. AGENT EXECUTION PROTOCOL (read first, every session)

### 0.1 Phase workflow — mandatory sequence
```
1. Read this plan.md section for the current phase.
2. Run/write the R0 probe script for every third-party boundary the phase touches
   (scripts/r0_probes/probe_<lib>.py). Probes call the REAL installed library and
   print actual entry points, signatures, and a minimal working example.
   If the probe contradicts this plan, STOP and update docs/r0_findings/<phase>.md
   before writing any implementation code.
3. Implement.
4. Run the phase gate:  make gate PHASE=p04   (wraps pytest tests/gates/test_p04_*.py -v)
5. Gate exit 0 → gate writes artifacts/gates/p04.json (metrics + pass) → commit
   with message "P04 DONE: <summary> [gate:pass]" → proceed.
   Gate exit != 0 → fix and re-run. NEVER edit a gate to make it pass without
   documenting why in docs/gate_changes.md.
6. Run the regression suite (make regress = all previous gates on golden configs)
   before declaring the phase complete. Later phases must not break earlier gates.
7. Close the session per the §0.5 session protocol: rewrite handoff.md, verify
   state.json, append changelog.md if a decision changed.
```

### 0.2 Hard rules (anti-pattern rejection list)
- **NEVER mock the third-party boundary a gate verifies.** Gates run the real
  CadQuery/OCP kernel, real Gmsh, real ezdxf, real lualatex, on real files.
  (Project history: the NeuralFoil Phase-2 adapter was written against a fictional
  API and its tests mocked the boundary they were meant to verify. Never again.)
- **NEVER mark a phase done without a gate artifact** in artifacts/gates/.
- **NEVER hardcode geometry results** (volumes, counts, coordinates) into gates
  as magic constants without a derivation comment; golden-config expected values
  live in tests/golden/expected/*.json with provenance notes.
- **NEVER use OCC shell/thicken for the IML** (F1). NEVER exact tangency in
  booleans (F4). NEVER skip the shard filter after a boolean (F3).
- **NEVER invent an API.** If unsure of a signature, run the R0 probe.
- All units mm/deg; all frames per docs/conventions.md. No implicit conventions.
- Ask the human only when the plan is ambiguous or a gate must change; otherwise
  proceed autonomously through the phase sequence.

### 0.3 Self-verification answer (why the tool "knows" each phase is correct)
Every phase gate is an executable pytest suite that checks the phase's output at
the real boundary with machine-checkable criteria (watertightness, volume
conservation, interference = 0, coaxiality tolerance, collision count = 0, file
re-import fidelity...). The agent cannot proceed on vibes: `make gate` either
exits 0 or the phase is not done. Three layers stack:
  (a) per-phase gates (correctness of the new capability),
  (b) `make regress` — all prior gates re-run on golden configs (no regressions),
  (c) edge-config battery (tests/configs/edge/*.yaml) on geometry phases.
The ONE thing that cannot self-verify locally is Ansys import (licensed, external):
P14 is a formal MANUAL gate with a signed checklist committed to the repo (§9, D16).

### 0.4 Repository layout (create in P0)
```
wingstructgen/
├── CLAUDE.md                    # distilled rules from §0 (read by Claude Code)
├── AGENTS.md                    # same content, Antigravity convention (keep in sync — §0.5)
├── plan.md                      # this file (normative)
├── handoff.md                   # next-step memory, rewritten every session (§0.5)
├── changelog.md                 # decision journal (§0.5)
├── docker-compose.yml
├── Makefile                     # gate, regress, probes, up, seed targets
├── docs/
│   ├── conventions.md           # §5, single source of truth
│   ├── known_issues.md          # OCC workarounds knowledge base (§0.5)
│   ├── decisions/               # ADR-NNN files for post-kickoff pivots (§0.5)
│   ├── r0_findings/             # per-phase probe results
│   └── gate_changes.md          # audited gate modifications
├── scripts/r0_probes/           # probe_ocp.py, probe_gmsh.py, probe_ezdxf.py, ...
├── backend/
│   ├── tolerances.py            # EVERY numeric tolerance in the tool, one file (§0.5)
│   ├── api/                     # FastAPI app
│   ├── worker/                  # queue consumer, subprocess sandbox, reaper
│   ├── geometry/                # pipeline stages, one module per §8 step
│   ├── exporters/               # step_xde.py, cdb_writer.py, dxf_flat.py, gltf.py
│   ├── airfoils/                # naca.py, uiuc_ingest.py, resample.py
│   └── schema/                  # Pydantic v2 models + validators
├── frontend/                    # React + three.js
├── report/                      # lualatex service, Jinja2 templates EN/AR
├── data/uiuc_snapshot/          # vendored .dat files (P1 ingests → Postgres)
├── tests/
│   ├── gates/                   # test_p00_*.py ... test_p19_*.py  (THE gates)
│   ├── golden/                  # 3 reference configs + expected/*.json
│   ├── configs/edge/            # high-taper, high-twist, thin-airfoil, min-gap...
│   └── oracle/                  # independent .cdb spec parser (F12)
└── artifacts/                   # gitignored job outputs; gates/ + state.json committed
```

### 0.5 Repo memory files (agent working memory across sessions)

Two problems these solve: **session amnesia** (a fresh agent session knows
nothing) and **decision amnesia** (why is it built this way?). The agent MUST
maintain these; a session that ends without updating handoff.md + state.json is
an incomplete session.

**CLAUDE.md / AGENTS.md** — the agent instruction file. CLAUDE.md is read by
Claude Code; AGENTS.md is the Antigravity convention. Identical content
(generate one from the other in the Makefile — never hand-edit both). Contents:
distilled §0 rules, the anti-pattern list, pointers to conventions.md,
tolerances.py, handoff.md, and the session protocol below.

**handoff.md** — next-step memory. HARD CAP ~20 lines. REWRITTEN (never
appended) at the end of every session. Template:
```markdown
# Handoff — <date>
## State
- Release/Phase: R1 / P4 (in progress)
- Last green gate: p03 (artifacts/gates/p03.json)
## Next single action
- <ONE concrete step, e.g. "implement cove revolution surface; R0 probe
  for BRepPrimAPI_MakeRevol is in docs/r0_findings/p04.md">
## Blockers / open questions
- <only real ones; empty is a valid answer>
## Do not touch
- <anything mid-refactor or awaiting human input>
```

**artifacts/state.json** — machine-readable twin of handoff.md. The agent reads
STATE from JSON and INTENT from handoff.md; never parse prose for state.
Updated automatically by `make gate` on every pass:
```json
{
  "schema_version": "0.4",
  "current_release": "R1",
  "current_phase": "p04",
  "gates_passed": ["p00", "p01", "p02", "p03"],
  "last_golden_run": {"date": "...", "config": "golden_01", "all_green": true},
  "plan_md_version": "0.4"
}
```

**changelog.md** — decision journal, not a diff log (git has the diffs). One
entry per meaningful change: what changed, WHY, and what it retired/added.
Example: `v0.4 — toggle latch → bolted spar retention (mechanism-generation
risk); retired latch risk, added F17–F19, rewrote D8/D10/P18.`

**backend/tolerances.py** — every numeric tolerance in the entire tool: kernel
fuzz values, coaxiality (0.05 mm), lip flushness, gate thresholds, clearance
bands. Each constant carries a comment with its origin/derivation. Gates and
geometry code import from here — a tolerance literal anywhere else in the
codebase is a review-blocking offense.

**docs/known_issues.md** — OCC workarounds knowledge base. Every resolved
kernel fight gets an entry: symptom → root cause → workaround → phase where
found. Compounds in value toward P15–P16 (molds, the hardest OCC work).

**docs/decisions/ADR-NNN-*.md** — one short Architecture Decision Record per
post-kickoff pivot (ADR-001 = the v0.4 joint redesign). The §2 D-table stays
the baseline; ADRs capture deltas so plan.md isn't rewritten per pivot.

**Session protocol (append to CLAUDE.md/AGENTS.md):**
```
START: read state.json → handoff.md → current phase section in plan.md →
       docs/known_issues.md (skim for the libs this phase touches).
END:   rewrite handoff.md; verify state.json matches reality; append
       changelog.md if any decision changed; log any new OCC workaround.
```

---

## 1. Mission

A standalone, locally deployed web application that generates a complete,
manufacturable, analysis-ready parametric composite wing: outer mold line,
sandwich skin, ribs, spars, trailing-edge control surface, leading-edge droop
nose, hinges, segment joints, skin latches, fuselage attachment hardpoints, and
CNC mold tooling — from a single declarative input configuration.

The tool performs **no FEA itself**. Its analysis deliverable is an Ansys-ready
package whose quality is guaranteed by automated gates plus a formal manual
Ansys acceptance procedure.

## 2. Locked Decisions

| # | Area | Decision |
|---|---|---|
| D1 | Interaction | Web UI, three.js viewer: body toggles + deflection slider (v1) |
| D2 | Deployment | Coder cloud workspace, Docker Compose, viewer via port-forward; standalone repo |
| D3 | Devices | One TE hinged surface + one LE hinged droop per half-span; slats deferred |
| D4 | Device placement | Devices fully contained within one wing segment (else validation error) |
| D5 | Manufacturing | Composite molded: sandwich skin (foam core + face sheets), molded internals |
| D6 | Trailing edge | Blunt TE forced, `te_min_thickness_mm` |
| D7 | Wing architecture | 3-piece (center + L + R outer); per-segment dihedral/sweep |
| D8 | Segment joints | Both spars (main + rear) carry male tongues (rect hollow OR circular tube, configurable) from the outer panels into female boxes in the center section; tongues parallel to a horizontal insertion axis BY CONSTRUCTION regardless of spar sweep (OML kinks at break plane); equal engagement both tongues; each box sits in a separate bonded aluminum housing |
| D9 | Hinges | Generated printable OR COTS placeholder pockets (pin Ø param), configurable |
| D10 | Joint retention | 1 vertical Z-bolt per housing (2 per break): countersunk head seats on an aluminum lip penetrating the upper skin → housing top → side walls → integral threaded bottom boss. Preload path is aluminum-only, never crossing composite; tongue holes are clearance fits — bolt acts purely as a shear pin against spanwise withdrawal |
| D11 | Core | Ramped drop-offs at edges/hinge lands/joint housing zones (incl. lip penetrations) — unified hardpoint mechanism |
| D12 | Fuselage attachment | Parametric bolt bosses/hardpoints on center section |
| D13 | Molds | Full halves for ALL bodies; parting plane, flanges, alignment pins; CNC tooling board; stock auto-sectioning |
| D14 | FEA target | Ansys. Both routes: STEP midsurfaces → SpaceClaim/Mechanical AND pre-meshed .cdb |
| D15 | Composites in Ansys | Mechanical layered shell sections; layup schedule exported CSV+JSON |
| D16 | Ansys gate | CI proxy gates + formal manual acceptance checklist committed as artifact |
| D17 | Materials | Built-in library (CFRP/GFRP/foams/tooling board) + custom entries, Postgres |
| D18 | Airfoils | NACA 4+5 builtin + vendored UIUC snapshot + .dat upload |
| D19 | Persistence | Postgres (jobs/configs/materials/airfoils/gates); Redis (queue/live state) |
| D20 | Reports | Bilingual EN/AR, lualatex RTL |
| D21 | Sequencing | R1 core → R1.5 segmentation → R2 Ansys → R3 molds → R4 reports/DXF/joint hardware detail |
| D22 | Mold hardware | CNC defaults (flange 40 mm, dowel Ø8, fit params), schema-overridable |

**Assumption A1 (open):** R1 builds a one-piece wing; segmentation ships as R1.5.
Joint hardware detail (housings/bolts) in R4/P18; joint housing hardpoint zones
reserved in R1.5. If overridden, P11 merges into R1 after P6.

## 3. Release Train

| Release | Content | Definition of done |
|---|---|---|
| **R1** | One-piece wing: OML, devices, sandwich internals, hinges, hardpoints, viewer, STEP/STL/glTF | P0–P10 gates green + regress green |
| **R1.5** | Segmentation: breaks, dual spar tongue/box (insertion-axis-parallel), per-segment dihedral/sweep, joint housing hardpoints | P11 gates green + regress green |
| **R2** | Ansys package: midsurface STEP, .cdb writer, layup schedule, named selections | P12–P13 CI gates green + P14 signed manual acceptance |
| **R3** | Molds: all bodies, parting, flanges, pins, stock sectioning | P15–P16 gates green |
| **R4** | Bilingual report, DXF, joint retention hardware (housings/bolts), COTS hinge mode | P17–P19 gates green |

## 4. System Architecture

```
Coder workspace (Docker Compose, ports forwarded)
┌─────────────┐  REST/WS   ┌───────────────┐  Redis queue  ┌────────────────────┐
│  Frontend   │──────────▶ │  API service  │─────────────▶ │  Geometry worker   │
│  React +    │◀────────── │  FastAPI      │◀───────────── │  CadQuery/OCP,     │
│  three.js   │ glTF/state │  Pydantic v2  │  heartbeats   │  Gmsh, ezdxf       │
└─────────────┘            └──────┬────────┘               └─────────┬──────────┘
                                  │                                  │
                           ┌──────▼────────┐              ┌──────────▼─────────┐
                           │   Postgres    │              │  Report service    │
                           │ jobs/configs/ │              │  lualatex (EN/AR)  │
                           │ materials/    │              └────────────────────┘
                           │ airfoils/gates│
                           └───────────────┘
```

- **API (FastAPI):** schema validation, job lifecycle, artifact serving, WebSocket
  progress, material/airfoil/config CRUD.
- **Geometry worker:** runs each job in a **subprocess sandbox** — OCC failures are
  often segfaults, not exceptions; parent detects child death, marks job failed at
  last checkpoint, stays alive. Heartbeats to Redis; reaper fails orphaned jobs.
- **Report service:** lualatex container, Jinja2 → .tex, Amiri/Noto Naskh for AR.
- **Storage:** artifacts on shared volume keyed by job ID; Postgres structured
  data; Redis transient only.
- **Frontend:** GLTFLoader; per-body toggles; deflection sliders animate about the
  true hinge axes client-side (visual only — authoritative check is server-side P8).

## 5. Conventions (docs/conventions.md, authored in P0, referenced everywhere)

- **Units:** mm, deg. Schema fields suffixed (`_mm`,`_deg`,`_frac`,`_xc`). `.cdb`
  decks declare **mm–tonne–s** in header block and report.
- **Frame:** X aft, Y starboard, Z up, right-handed. Origin: center-section root LE.
- **Twist axis:** user-declared `twist_axis_xc`, stored on every section — never implicit.
- **Hinge/latch axes:** perfectly straight 3D lines derived FIRST; mechanisms
  defined relative to their axis, never the reverse.
- **Signs:** TE surface trailing-edge-down positive; droop leading-edge-down positive.
- **Airfoils:** unit chord, TE→upper→LE→lower→TE, blunt TE enforced, identical
  cosine resampling (`resample_points`, odd) before any placement.
- **Naming contract:** `SEG-{C|L|R}/BODY-{name}/ROLE-{skin|rib|spar|...}` across
  STEP, .cdb, glTF, DXF, report.

## 6. Input Schema (v0.2, abridged — normative = Pydantic models in backend/schema/)

```yaml
planform:
  span_mm: 2400
  segments:                          # 3-piece from R1.5; R1 accepts single segment
    - {name: center, y_end_frac: 0.20, dihedral_deg: 0.0, sweep_le_deg: 0.0}
    - {name: outer,  y_end_frac: 1.00, dihedral_deg: 5.0, sweep_le_deg: 5.0}
  stations:
    - {y_frac: 0.0, chord_mm: 320, twist_deg:  0.0, airfoil: naca23012}
    - {y_frac: 1.0, chord_mm: 180, twist_deg: -2.0, airfoil: uiuc:sd7037}
  twist_axis_xc: 0.25
  mirror: true

airfoils:
  sources: [naca4, naca5, uiuc, dat_upload]
  resample_points: 199
  te_min_thickness_mm: 0.8

skin:
  face_sheet: {material: cfrp_200gsm_twill, plies: 2}
  core:       {material: rohacell_31, thickness_mm: 3.0}
  ramp_ratio: 3.0                    # drop-off length = ratio × core thickness

spars:                               # BOTH spars carry tongues (D8); equal engagement
  - {name: main, xc_root: 0.25, xc_tip: 0.25, web: {material: cfrp_200gsm_twill, plies: 4},
     tongue: {cross_section: rect_hollow,   # rect_hollow | circular_tube
              engagement_mm: 120, clearance_mm: 0.2, wall_mm: 2.0}}
  - {name: rear, xc_root: 0.70, xc_tip: 0.70, web: {material: cfrp_200gsm_twill, plies: 3},
     tongue: {cross_section: rect_hollow, engagement_mm: 120, clearance_mm: 0.2, wall_mm: 2.0}}

ribs:
  count: 9
  construction: {material: cfrp_200gsm_twill, plies: 3}
  lightening_holes: {enabled: true, margin_mm: 8}

te_surface:  {enabled: true, span_start_frac: 0.55, span_end_frac: 0.95,
              hinge_xc_start: 0.75, hinge_xc_end: 0.75, gap_mm: 1.5,
              max_deflection_deg: 25, hinges: {mode: generated|cots, count: 3, cots_pin_dia_mm: 3.0}}

le_droop:    {enabled: true, span_start_frac: 0.10, span_end_frac: 0.55,
              hinge_xc_start: 0.15, hinge_xc_end: 0.15, gap_mm: 1.5,
              max_deflection_deg: 20, hinges: {mode: generated, count: 2}}

hardpoints:
  auto: [hinge_lands, joint_housing_zones, fuselage_bosses]
  fuselage_attachment:
    bolts: [{y_mm: 0, x_c: 0.25, dia_mm: 6}, {y_mm: 0, x_c: 0.70, dia_mm: 6}]

joint_retention:                     # bolted spar retention (replaced toggle latches, v0.4)
  insertion_axis: horizontal_y       # tongues forced parallel to this by construction
  bolts_per_housing: 1               # 2 per break (main + rear housings)
  bolt: {dia_mm: 5, axis: global_z, head: countersunk_flush}
  housing:                           # separate aluminum block per spar
    material: al_7075
    side_wall_mm: 4.0                # structural: carries full bolt preload
    boss_thread: M5_placeholder      # placeholder bore + callout, never real thread geometry
    lip: {mode: flat_capped, flush_tol_mm: 0.1}   # flat lip; Ø auto-capped by local OML
                                                  # curvature; curvature-matched mode optional

molds:
  bodies: all
  flange_width_mm: 40
  alignment_pins: {dia_mm: 8, count_min: 4, fit: sliding}
  stock: {slab_lwh_mm: [1500, 500, 100], auto_section: true}
  parting: auto_max_width

ansys_export:
  routes: [step_midsurface, cdb]
  target_element_size_mm: 8
  named_selections: true

output:
  formats: [step, stl, gltf, cdb, dxf, pdf, layup_csv, layup_json]
```

**P0 validation rules (reject with actionable messages):** device windows
non-overlapping and segment-contained (D4); TE hinge aft of rear spar +
clearance, LE hinge forward of main spar + clearance; hinge axes contained in
OML with margin ≥ face+core stack, **sampled along the axis**; core + 2×face ≤
80 % of min local airfoil thickness; `gap_mm` ≥ 2× tessellation tolerance and
≥ 10× kernel tolerance; break stations outside device windows; lightening holes
degrade gracefully (shrink → omit, warn) on small tip ribs.
**Joint rules (v0.4):** angle between bolt axis (global Z) and local upper-skin
normal at every bolt station ≤ 3° (countersink seats flush only near-normal —
holds because the center section is flat, must be VALIDATED not assumed); flat
housing lip Ø capped so max deviation from local OML curvature ≤ flush_tol_mm;
tongue axes parallel to insertion axis (enforced by construction, asserted
anyway); bolt edge distance ≥ 2×Ø from tongue and housing edges; housings +
boss fully inside IML with bond-gap clearance; tongue cross-section fits inside
housing box with configured clearance.

## 7. Data Model (Postgres)

- `configs` — versioned JSONB + schema version, parent-config lineage.
- `jobs` — status, checkpoints, timing, worker id, artifact manifest.
- `gate_results` — one row per gate per job: name, phase, pass/fail, metrics
  JSONB. **The report renders from this table** — gates and reporting cannot diverge.
- `materials` — E1/E2/G12/ν12, density, ply thickness, allowables (schedule only).
- `airfoils` — normalized UIUC snapshot + NACA + uploads: raw & normalized points,
  detected format (Selig/Lednicer), validation flags.
- `ansys_acceptance` — checklist version, Ansys version, tester, date, per-item
  results, linked job.

## 8. Geometry Pipeline (construction order is normative; one module per step)

1. **Airfoil ingest & normalization** — Selig/Lednicer auto-detect (UIUC mixes
   both), canonical reorder, blunt TE to `te_min_thickness_mm`, cosine resample.
2. **Sections & per-segment placement** — scale, twist about declared axis,
   per-segment dihedral/sweep; C1 continuity of the unbroken OML at segment joins.
3. **Master OML loft** (half-span, watertight), mirror for full span.
4. **Reference geometry before any cut** — spar ruled surfaces; rib planes (auto +
   forced at device edges and break stations); TE/LE hinge axes (straight,
   containment-sampled); break planes; hardpoint footprints; latch & boss locations.
5. **Device cuts** — TE: spanwise gap cuts + chordwise cut, nose rebuilt as
   revolution about hinge axis, concave cove + false spar on wing side, small
   deliberate clearance angle (never exact tangency, F4). LE droop: mirrored
   approach; droop keeps original airfoil LE (why droop beat slats).
6. **Segmentation (R1.5)** — break-plane cuts; BOTH spars get male tongues on
   the outer panels (rect hollow or circular tube), built **parallel to the
   horizontal insertion axis by construction** — NOT along the swept spar
   directions — transitioning into their spars inside the outer panel; female
   boxes in the center section; OML kinks exactly at the break plane, panel
   slides on horizontally; closing ribs at break faces; joint housing hardpoint
   zones (core ramp-out + upper-skin lip penetration reserves) at each housing.
7. **Sandwich internals per body** — IML by **2D per-station offset + second loft
   + subtract, NEVER OCC shell/thicken** (F1). Core volume between face-sheet
   IMLs with **ramped drop-offs** (`ramp_ratio`) at edges, hinge lands, joints,
   every hardpoint (core ramps out to solid laminate). Ribs: plane ∩ inner
   volume, cutouts + holes as 2D face ops before thickening. Spars trimmed to
   IML; false spars close device cut faces. **Midsurface faces constructed here,
   alongside the solids** — not extracted later.
8. **Hardware** — hinges (generated or COTS pockets) with holes exactly on axis;
   fuselage bosses; joint retention (R4/P18): per-spar aluminum housings (sleeve
   with structural side walls, integral threaded bottom boss, countersink lip
   penetrating the upper skin), Z-bolts, tongue clearance holes, skin lip
   cutouts. Bore chain per bolt: lip countersink → housing top → tongue hole →
   bottom boss, all coaxial. Galvanic-isolation (glass ply) note at every
   aluminum–CFRP bond line flows into the P19 report.
9. **Molds (R3)** — per body: parting curve at max half-breadth per station →
   parting surface → upper/lower cavity blocks; flanges, pin bores, stock
   auto-sectioning with inter-block alignment; demold clearance vs pull direction
   (cove and blunt-TE regions are the risk zones).
10. **Derived outputs** — per-body tessellation → glTF (LOD-cached) + STL; **STEP
    via OCP XDE assembly path** (plain export drops names, F10); named midsurface
    STEP; `.cdb` via custom NBLOCK/EBLOCK/SECTYPE writer (no OSS tool writes
    .cdb); DXF with developability check; layup schedule CSV/JSON; gate data →
    bilingual PDF.

## 9. Phase Plan — with executable gates

Format per phase: **Scope → R0 probes → Gate command → Pass criteria (machine-checkable)**.
Gate artifacts: `artifacts/gates/pXX.json`. All gates also stream metrics to `gate_results`.

### R1 — Core geometry + viewer

**P0 — Foundation**
- Scope: repo scaffold (§0.4), Compose stack, Postgres migrations, Pydantic
  schema + all §6 validation rules, conventions.md, worker sandbox/heartbeat/reaper,
  Makefile targets (gate/regress/probes/up/seed).
- R0: probe_ocp.py, probe_gmsh.py (import, version, one trivial op each).
- Gate: `make gate PHASE=p00`
- Pass: every invalid config in tests/configs/invalid/ rejected with the expected
  error code; valid configs round-trip schema→JSON→schema losslessly; a gate test
  SIGKILLs a worker subprocess mid-job and asserts the job lands in FAILED with a
  checkpoint, not RUNNING.

**P1 — Airfoil subsystem**
- Scope: NACA 4/5 generators; UIUC snapshot ingest with Selig/Lednicer
  auto-detection, quarantine, normalization; blunt-TE closure; cosine resampler.
- R0: parse 5 known-Selig and 5 known-Lednicer files by hand first; document
  detection heuristic in r0_findings/p01.md.
- Gate: `make gate PHASE=p01`
- Pass: 100 % of vendored UIUC files normalize OR quarantine with a reason string
  (0 silent failures); NACA generators match published ordinate tables within
  tolerance for 3 reference sections; resample round-trip max deviation < 1e-3
  chord; every normalized foil has TE thickness ≥ te_min_thickness_mm.

**P2 — Sections + OML loft**
- Scope: §8.2–8.3.
- R0: probe OCP loft API (real signature, wire ordering requirement) on 3 sections.
- Gate: `make gate PHASE=p02`
- Pass: solid watertight (OCC closed-shell + validity); volume within ±3 % of
  analytic planform × mean-thickness estimate on all golden configs; no
  self-intersection on every edge config (high taper, high twist, thin foil);
  twist verified: rotated section points match hand-computed rotation about the
  declared axis to 1e-6 mm.

**P3 — Reference geometry**
- Scope: spar surfaces, rib planes (+forced planes), both hinge axes, hardpoint
  footprints.
- Gate: `make gate PHASE=p03`
- Pass: axis straightness exact by construction (assert 2-point line object);
  containment sampled at ≥ 50 stations along each axis with margin ≥ sandwich
  stack — passes on golden AND edge configs (F5); forced rib planes exist at
  every device edge.

**P4 — TE surface cut**
- Scope: §8.5 TE path.
- R0: probe boolean cut + revolution surface on a toy solid; record fuzzy-value
  behavior.
- Gate: `make gate PHASE=p04`
- Pass: exactly 2 watertight bodies; vol(wing)+vol(CS)+vol(gap) = vol(P2) within
  0.5 %; shard filter reports 0 bodies below min-volume threshold (F3); cove
  clearance angle present (no tangent face pairs, F4).

**P5 — LE droop cut**
- Gate: `make gate PHASE=p05`
- Pass: 3 watertight bodies; same conservation, shard, tangency criteria.

**P6 — Sandwich internals + hardpoints**
- Scope: §8.7 (includes midsurface construction alongside solids).
- Gate: `make gate PHASE=p06`
- Pass: pairwise boolean interference = 0 across ALL bodies; every auto hardpoint
  has core ramp-out (core body distance-to-hardpoint ≥ ramp length); IML audit:
  min wall ≥ face-sheet stack everywhere (sampled); every rib watertight after
  holes/cutouts; midsurface face count matches structural body count.

**P7 — Hinges (generated mode)**
- Gate: `make gate PHASE=p07`
- Pass: all hinge holes coaxial with their axis within 0.05 mm, measured on the
  generated geometry; lug/tang clearance to moving body ≥ configured fit gap.

**P8 — Kinematic gate (the decisive R1 gate)**
- Gate: `make gate PHASE=p08`
- Pass: sweep TE and droop through ±max_deflection: coarse 1° steps + fine 0.1°
  steps in the outer 20 % of travel; collision count = 0 at every step; minimum
  clearance ≥ gap_mm − tolerance and monotonic-trend check; swept-volume boolean
  at both extremes intersect fixed wing = ∅ (F9).

**P9 — Export (glTF/STL/STEP)**
- R0: probe OCP XDE document API — verify names survive a write/read cycle on a
  2-body toy assembly BEFORE implementing (F10 — fictional-API-shaped trap).
- Gate: `make gate PHASE=p09`
- Pass: exported STEP re-imported into OCC: body count identical, all names per
  §5 naming contract intact; STL manifold per body; glTF loads in headless
  three.js smoke test and node count matches body count.

**P10 — Web UI E2E**
- Gate: `make gate PHASE=p10` (Playwright)
- Pass: scripted run: submit golden config → progress events received → model
  renders → each body toggles → deflection slider animates about correct axis
  (compare a tracked vertex against server-computed position).

### R1.5 — Segmentation

**P11 — 3-piece wing**
- Scope: §8.6 + per-segment dihedral/sweep activation.
- Gate: `make gate PHASE=p11`
- Pass: segments re-assembled in OCC: tongue/box clearance within
  [clearance_mm ± 0.05] along 100 % of engagement length for BOTH tongues; both
  tongue axes parallel to insertion axis within 0.05° (asserted, though enforced
  by construction); **insertion sweep**: translate the outer panel along the
  insertion axis through full engagement — zero collisions at every step (the
  joint's equivalent of P8); OML surface deviation across breaks < 0.1 mm;
  closing ribs watertight; joint housing hardpoint zones present at each
  housing; device-in-segment validation rejects a crossing config; **regress:
  P2–P10 gates still green in segmented mode**.

### R2 — Ansys export package

**P12 — Midsurface STEP**
- Gate: `make gate PHASE=p12`
- Pass: sliver/micro-edge scan: 0 edges < target_element_size_mm/10; shared-edge
  conformality where ribs meet skin/spars (coincident edges within kernel
  tolerance); names survive OCC re-import; midsurface-to-solid max normal
  deviation < 10 % of local thickness.

**P13 — .cdb writer + layup schedule**
- Scope: custom NBLOCK/EBLOCK/ET/SECTYPE/SECDATA/CMBLOCK writer; Gmsh meshes the
  constructed midsurfaces; layup CSV+JSON.
- R0: obtain and cite the APDL blocked-format spec sections in r0_findings/p13.md;
  write tests/oracle/cdb_parser.py FROM THE SPEC before the writer exists (F12 —
  writer and verifier must not share a bug).
- Gate: `make gate PHASE=p13`
- Pass: oracle parser accepts the deck: node/element counts match Gmsh source;
  every element belongs to exactly one SECTYPE with correct layer stack from the
  materials DB; mesh is a **single connected component** across all structural
  bodies (F7 — T-junction detector); named components (CMBLOCK) match §5 naming;
  mm–tonne–s header present (F8).

**P14 — Manual Ansys acceptance (formal gate, human-executed)**
- Procedure: docs/ansys_acceptance_checklist.md v1 — on licensed Ansys: import
  STEP midsurfaces (SpaceClaim shared topology ON), mesh at target size, assign
  layered sections from layup_csv, verify named selections resolved, import .cdb
  into Mechanical APDL, /CHECK clean.
- Pass: signed checklist committed to repo + row in `ansys_acceptance`. CI blocks
  R2 completion tag until the artifact exists. Re-run whenever P12/P13 code changes.

### R3 — Molds

**P15 — Mold generation**
- Gate: `make gate PHASE=p15`
- Pass: per body: (upper ∪ lower mold ∪ part) boolean is void-free (cavity
  closure); flange width ≥ configured; pin bores coaxial across halves within
  0.05 mm; pin count ≥ count_min.

**P16 — Demold + stock sectioning**
- Gate: `make gate PHASE=p16`
- Pass: undercut scan vs pull direction = 0 faces (cove and blunt-TE regions
  explicitly sampled, F14); every sectioned block fits declared slab dims;
  inter-block alignment features present on every section interface.

### R4 — Documentation & detail

**P17 — DXF flat patterns**
- Gate: `make gate PHASE=p17`
- Pass: rib patterns: re-parsed DXF area = source face area within 0.1 %; spar
  webs: developability metric computed; non-developable webs carry a WARNING
  entity + distortion metric in the DXF and gate JSON — silent unroll = fail (F6).

**P18 — Joint retention hardware + COTS hinge mode**
- Scope: aluminum housings (per-spar sleeve, structural side walls, integral
  threaded bottom boss, skin-penetrating countersink lip), Z-bolts, tongue
  clearance holes, upper-skin lip cutouts, COTS hinge pocket mode.
- Gate: `make gate PHASE=p18`
- Pass: bore chain (lip countersink → housing top → tongue clearance hole →
  bottom boss) coaxial within 0.05 mm per bolt; **preload-path continuity**:
  swept bolt-load column from head seat to boss intersects aluminum bodies only,
  never composite (the design's core promise, asserted on geometry); lip
  flushness: flat lip max deviation from local OML ≤ flush_tol_mm; tongue holes
  are clearance fit (Ø_hole − Ø_bolt within configured band — no interference);
  bolt edge distance ≥ 2×Ø from tongue and housing edges; housings fully inside
  IML with bond-gap clearance; COTS hinge pocket dims match cots_pin_dia_mm +
  fit params.

**P19 — Bilingual report**
- R0: probe lualatex container with an AR+EN sample (RTL, Amiri) before templating.
- Gate: `make gate PHASE=p19`
- Pass: report compiles from a real job's gate_results rows with zero lualatex
  errors; every gate in the job appears in the PDF (count match); AR pages render
  RTL (marker-position check on rasterized page); PDF served via API endpoint.

## 10. Failure-Mode Register (each F maps to the gate that catches it)

| # | Failure mode | Mitigation / catching gate |
|---|---|---|
| F1 | OCC shell/thicken fails at TE | Banned (§0.2); IML by offset+loft+subtract — P6 |
| F2 | OCC segfault kills worker silently | Subprocess sandbox + reaper — P0 gate SIGKILL test |
| F3 | Boolean micro-shards poison downstream | Mandatory shard filter — P4+ gates |
| F4 | Tangent-face booleans at cove | Deliberate clearance angle — P4 tangency check |
| F5 | Twist pushes hinge axis out of OML mid-span | Sampled containment — P3 |
| F6 | Non-developable spar webs → distorted DXF | Developability metric, silent unroll = fail — P17 |
| F7 | T-junction mesh: looks fine, structurally disconnected | Single-connected-component check — P13 |
| F8 | .cdb unit mismatch (mm vs m = 10⁹ error) | mm–tonne–s header asserted — P13 |
| F9 | Sweep misses collision between samples | Fine steps + swept-volume boolean — P8 |
| F10 | STEP loses body names | XDE path, probed in P9 R0, re-import gate — P9 |
| F11 | UIUC Selig/Lednicer confusion | Auto-detect + quarantine — P1 (0 silent failures) |
| F12 | .cdb writer drifts from spec (no OSS reference) | Spec-derived independent oracle parser — P13 |
| F13 | Fictional third-party APIs (NeuralFoil-class) | Mandatory R0 probes; boundary mocking banned — §0 |
| F14 | Mold undercuts at cove / blunt TE | Demold scan — P16 |
| F15 | Sandwich stack > local airfoil thickness | P0 validation rule (≤ 80 % min local thickness) |
| F16 | Ansys import passes proxies, fails in practice | Manual acceptance artifact required — P14 |
| F17 | Flat housing lip sits proud/sunk on curved OML | Lip Ø capped by curvature rule (P0) + flushness gate — P18 |
| F18 | Bolt preload crushes hollow composite tongue | Design: aluminum-only preload path; continuity gate — P18 |
| F19 | Non-parallel tongues make panel un-insertable | Parallel-by-construction + insertion-sweep gate — P11 |

*(v0.4: over-center latch mechanism risk retired entirely — replaced by bolted retention, D8/D10.)*

## 11. Testing Strategy

- **Gates ARE the test suite** — pytest, real kernel/mesher/compiler, real files;
  metrics to artifacts/gates/*.json and Postgres gate_results.
- **Golden configs** (3 reference wings, committed expected metrics with
  provenance) — regression tripwire; `make regress` runs all completed gates on
  them and must stay green through every later phase.
- **Edge battery** (tests/configs/edge/) — high taper, high twist, thin airfoil,
  max device spans, min gaps — mandatory on P2–P8, P11.
- **CI:** full golden pipeline per merge; Playwright nightly; oracle parser per
  merge; P14 re-triggered by any P12/P13 diff.

## 12. Out of Scope (this version)

Structural solve of any kind; aero load mapping; slats; multiple TE surfaces per
half-span; actuator geometry; fastener detail beyond tongues/retention bolts/bosses (no real thread geometry ever);
ply-drop optimization; mold thermal/cure modeling.

---

*Open item: Assumption A1 (R1 one-piece → R1.5 segmentation). Override merges
P11 into R1 after P6.*
