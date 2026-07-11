# Graph Report - .  (2026-07-11)

## Corpus Check
- 111 files · ~56,959 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 732 nodes · 1464 edges · 60 communities (52 shown, 8 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 58 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Database Models & ORM
- Wing Config Data Models
- NACA Thickness & Cylinder Helpers
- Invalid Config Error Codes
- Agent Instructions & Conventions
- OML Loft Construction
- TE Cut Test Fixtures & Tolerances
- Airfoil Resampling Pipeline
- TE Surface Cut Construction
- Sandwich IML Boolean Construction
- Cove/Nose Arc Profile Construction
- ADR-003 Hinge Clearance Validation
- Airfoil Metrics & NACA Generation
- Spar Surfaces & Hardpoints
- Kickoff Design Decisions (D12-D18)
- NACA 4/5-Digit Generators
- Hinge Frame & Viewer Export
- Three.js Viewer App
- Changelog & Validator Constants
- Reference Geometry & Config Root
- UIUC Airfoil Ingestion
- Canonical Airfoil Data Class
- Geometry Module & ADR Map
- Phase Plan & Failure Modes (F1/F9/F10)
- Curvature & Tangency Diagnostics
- R0 Probes — OCC/Gmsh Kernel
- Failure Modes F6-F16 (Mfg/Export)
- R0 Findings — P4 TE Cut Timing
- R0 Findings — P1 Airfoil Subsystem
- Joint Retention Design (D8/D10/ADR-001)
- False Spar Closing Wall
- Config Error Code Enum
- BRep Cache R0 Probe
- Tolerance Constants (P3)
- Nose Tangency Validation Test
- Watertightness Gate Tests
- Hinge Axis Construction & R0 Probe
- R0 Findings — P2 OML Loft
- R0 Findings — P3 Reference Geometry
- Web UI & Segmentation Phases
- Nose Arc Sampling Test
- OCP Loft R0 Probe
- Ansys .cdb Oracle Writer
- Gmsh R0 Probe Script
- OCP Kernel R0 Probe Script
- OCP Boolean R0 Probe Script
- OCP Reference R0 Probe Script
- Viewer Build Script
- Coder CLI Version Noise
- WingStructGen Project Root
- Wingo Repo README

## God Nodes (most connected - your core abstractions)
1. `Config` - 54 edges
2. `Phase plan overview with executable gates (§9)` - 26 edges
3. `build_planform_sections()` - 24 edges
4. `PlacedSection` - 23 edges
5. `Input schema v0.2 (§6)` - 23 edges
6. `Geometry pipeline, construction order (§8)` - 21 edges
7. `build_oml()` - 18 edges
8. `generate_naca()` - 17 edges
9. `ConfigValidationError` - 17 edges
10. `build_nose_arc_points()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `build_nose_arc_points()` --shares_data_with--> `backend/geometry/cove_profile.py (per-station cove/nose arc profiles)`  [EXTRACTED]
  backend/geometry/cove_profile.py → docs/decisions/ADR-002-per-station-arc-cove-nose.md
- `ADR-003: Single-arc nose + derived hinge-axis height replaces two-arc/Hermite blend` --references--> `build_nose_arc_points()`  [EXTRACTED]
  docs/decisions/ADR-003-single-arc-derived-axis.md → backend/geometry/cove_profile.py
- `derive_hinge_axis()` --shares_data_with--> `backend/geometry/reference.py (spar surfaces, rib planes, hinge axes, hardpoints)`  [EXTRACTED]
  backend/geometry/reference.py → docs/r0_findings/p03.md
- `ADR-003: Single-arc nose + derived hinge-axis height replaces two-arc/Hermite blend` --references--> `derive_hinge_axis()`  [EXTRACTED]
  docs/decisions/ADR-003-single-arc-derived-axis.md → backend/geometry/reference.py
- `test_zero_silent_failures()` --indirect_call--> `QuarantinedAirfoil`  [INFERRED]
  tests/gates/test_p01_airfoils.py → backend/airfoils/types.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **P6 sandwich panel construction evolution (clean-span -> body-restricted -> 3-layer)** — docs_r0_findings_p06, changelog_md_p6_kickoff, changelog_md_p6_body_restricted_core, changelog_md_p6_3layer_correction, handoff_md [INFERRED 0.85]
- **TE cut cove/nose construction design evolution (cylinders -> per-station arcs -> single-arc derived axis)** — docs_decisions_adr_002_per_station_arc_cove_nose, docs_decisions_adr_003_single_arc_derived_axis, docs_r0_findings_p04, changelog_md_p4_refined_per_station, changelog_md_p4_single_arc_nose [INFERRED 0.85]
- **R0 probe methodology instantiated per phase** — plan_md_r0_probe_concept, docs_r0_findings_p00, docs_r0_findings_p01, docs_r0_findings_p02, docs_r0_findings_p03, docs_r0_findings_p04, docs_r0_findings_p06 [INFERRED 0.85]
- **Edge/boundary stress-test config battery (mandatory P2-P8, P11)** — tests_configs_edge_readme, tests_configs_edge_high_taper, tests_configs_edge_high_twist, tests_configs_edge_thin_airfoil, tests_configs_edge_devices_full, tests_configs_edge_devices_twisted [EXTRACTED 1.00]
- **Invalid config battery — each derived from full_example.yaml by breaking one validation rule** — tests_configs_valid_full_example, tests_configs_invalid_device_not_segment_contained, tests_configs_invalid_gap_below_tolerance, tests_configs_invalid_sandwich_stack_exceeds_thickness, tests_configs_invalid_te_hinge_too_far_forward [INFERRED 0.85]
- **Golden regression-tripwire config battery (plan.md §11, make regress)** — tests_golden_readme, tests_golden_golden_01_straight_taper, tests_golden_golden_02_twist_transition, tests_golden_golden_03_dihedral_sweep [EXTRACTED 1.00]

## Communities (60 total, 8 thin omitted)

### Community 0 - "Database Models & ORM"
Cohesion: 0.06
Nodes (59): AirfoilRow, AnsysAcceptanceRow, Base, ConfigRow, GateResultRow, JobRow, MaterialRow, UUID (+51 more)

### Community 1 - "Wing Config Data Models"
Cohesion: 0.07
Nodes (46): Airfoils, AlignmentPins, AnsysExport, Core, DeviceWindow, FaceSheet, FuselageAttachment, FuselageBolt (+38 more)

### Community 2 - "NACA Thickness & Cylinder Helpers"
Cohesion: 0.11
Nodes (25): min_thickness_mm(), Minimal analytic NACA4/5 thickness helper.  Standalone from the full P1 airfoil, Full thickness at x_frac, as a fraction of chord. None if unparseable., Minimum thickness (mm) over the sampled mid-chord region. None if the     airfoi, thickness_frac(), coaxial_cylinder_radii(), filter_shards(), fuzzy_cut() (+17 more)

### Community 3 - "Invalid Config Error Codes"
Cohesion: 0.09
Nodes (26): ADR-004: LE droop dropped from scope, backend/tolerances.py, changelog.md, device_not_segment_contained error code, gap_below_tolerance error code, sandwich_stack_exceeds_thickness error code, te_hinge_too_far_forward error code, F15: sandwich stack thickness constraint (core+face vs local airfoil thickness) (+18 more)

### Community 4 - "Agent Instructions & Conventions"
Cohesion: 0.10
Nodes (26): WingStructGen Agent Instructions (AGENTS.md, generated), WingStructGen Agent Instructions (CLAUDE.md), Hard rules (anti-pattern rejection list, distilled), Phase workflow (7-step, distilled), Session protocol (START/END), Conventions (docs/conventions.md, single source of truth), Airfoils convention: unit chord, TE->upper->LE->lower->TE, cosine resample, Frame convention: X aft, Y starboard, Z up, right-handed (+18 more)

### Community 5 - "OML Loft Construction"
Cohesion: 0.14
Nodes (24): analytic_volume_estimate(), build_oml(), build_section_wire(), _full_span_points(), _mirror_sections(), _polygon_area_3d(), ndarray, Wire (+16 more)

### Community 6 - "TE Cut Test Fixtures & Tolerances"
Cohesion: 0.12
Nodes (19): The cheap half: hinge frame + per-station feet + loft-input polygons.     Pure n, The expensive, cacheable half of the construction: raw boolean outputs     BEFOR, _station_data(), TeCutRawShapes, Every numeric tolerance in WingStructGen, in one place (plan.md §0.5).  A tolera, _build_cut_case(), cut_result(), cut_result_fresh() (+11 more)

### Community 7 - "Airfoil Resampling Pipeline"
Cohesion: 0.14
Nodes (22): close_blunt_te(), cosine_resample(), cosine_x(), interp_surface(), ndarray, Cosine resampling + blunt-TE closure — the shared final stage every airfoil pass, Split canonical points (TE→upper→LE→lower→TE) into upper and lower     surfaces,, Interpolate a surface's y at target_x. Guards np.interp's requirement     of str (+14 more)

### Community 8 - "TE Surface Cut Construction"
Cohesion: 0.15
Nodes (22): _aft_box(), build_te_cut_shapes(), _close_nose_polygon(), _close_polygon(), cut_te_surface(), finish_te_cut(), _loft_region(), ndarray (+14 more)

### Community 9 - "Sandwich IML Boolean Construction"
Cohesion: 0.14
Nodes (20): fuzzy_common(), a ∩ b (intersection) with an explicit fuzzy value., build_sandwich_body(), build_sandwich_lofts(), _camber_polyline(), face_sheet_thickness_mm(), _offset_wire(), _parting_polygon() (+12 more)

### Community 10 - "Cove/Nose Arc Profile Construction"
Cohesion: 0.18
Nodes (18): build_cove_arc_points(), build_nose_arc_points(), find_station_feet(), _forward_sweep_angles(), _overlap_extension_rad(), ndarray, Per-station cove/nose SINGLE-arc construction (§8.5, refined — docs/decisions/AD, Normal feet of C on the upper (u>0 side) and lower (u<0 side) skin     curves wi (+10 more)

### Community 11 - "ADR-003 Hinge Clearance Validation"
Cohesion: 0.16
Nodes (19): ADR-003: TE hinge clearance & nose-tangency fail-fast validation, artifacts/gates/p04.json (gate-verified metrics), artifacts/viewer_data.json, docs/r0_findings/p04.md, NOSE_TANGENCY_EXCEEDS_MAX error code, HINGE_SPAR_XC_CLEARANCE_FRAC tolerance constant, NOSE_TANGENCY_MAX_DEG = 2.0deg tolerance, P4 "must successfully build" gate battery (+11 more)

### Community 12 - "Airfoil Metrics & NACA Generation"
Cohesion: 0.15
Nodes (16): max_point_to_curve_deviation(), ndarray, Max over `query` points of the minimum Euclidean distance from that     point to, Geometric comparison metrics for airfoils.  Airfoil surfaces are near-vertical a, generate_naca(), Generate a NACA 4- or 5-digit airfoil as a canonical Airfoil.      Raises ValueE, QuarantinedAirfoil, A source that could NOT be normalized. Carries a human-readable reason     — the (+8 more)

### Community 13 - "Spar Surfaces & Hardpoints"
Cohesion: 0.15
Nodes (18): build_hardpoints(), build_spar_surfaces(), Vector, Build a ruled surface shell for each spar from root to tip., Fuselage attachment hardpoints., interp_station(), le_and_z_offset(), place_section() (+10 more)

### Community 14 - "Kickoff Design Decisions (D12-D18)"
Cohesion: 0.11
Nodes (19): docker-compose.yml (postgres + redis dev stack), D12 Fuselage attachment: parametric bolt bosses/hardpoints on center section, D13 Molds: full halves for ALL bodies; parting/flanges/pins; stock auto-sectioning, D14 FEA target: Ansys, both STEP-midsurface and .cdb routes, D15 Composites in Ansys: Mechanical layered shell sections, layup schedule export, D16 Ansys gate: CI proxy gates + formal manual acceptance checklist, D17 Materials: built-in library + custom entries, Postgres, D18 Airfoils: NACA 4+5 builtin + vendored UIUC snapshot + .dat upload (+11 more)

### Community 15 - "NACA 4/5-Digit Generators"
Cohesion: 0.16
Nodes (15): _assemble(), _camber4(), _camber5(), _thickness(), ndarray, NACA half-thickness distribution yt(x) for max thickness fraction t     (open TE, NACA 4- and 5-digit airfoil generators (closed-form).  Produces canonical-order, 4-digit camber line yc and slope dyc/dx. (+7 more)

### Community 16 - "Hinge Frame & Viewer Export"
Cohesion: 0.19
Nodes (17): hinge_frame(), (p_start, p_end, h, a, u, axis_len). h = hinge-axis unit dir; a =     chordwise-, _curvature_angle_proxy(), _curvature_check(), _export_one(), _load_gate_metrics(), main(), ndarray (+9 more)

### Community 17 - "Three.js Viewer App"
Cohesion: 0.20
Nodes (15): ADR-0003, axisRod(), buildScene(), disposeGroup(), drawCurvatureChart(), fitCameraToRoot(), hardpointMarker(), indexedMesh() (+7 more)

### Community 18 - "Changelog & Validator Constants"
Cohesion: 0.15
Nodes (17): backend/airfoils/naca_thickness.py (analytic NACA4/5 thickness helper), backend/schema/validators.py (Pydantic cross-field validation rules), SANDWICH_MARGIN_FRACTION (safe-offset margin fraction for IML offset2D), Changelog (decision journal), 2026-07-08 LE droop dropped from scope (ADR-004) entry, 2026-07-05 P0 kickoff entry, 2026-07-05 P1 (Airfoil subsystem) DONE entry, 2026-07-07(later) P4 single-arc nose + derived hinge-axis height (ADR-003) entry (+9 more)

### Community 19 - "Reference Geometry & Config Root"
Cohesion: 0.21
Nodes (14): build_reference_geometry(), build_rib_planes(), Rib planes (auto + forced at device edges and break stations)., ReferenceGeometry, Config, Root config model — the whole §6 input schema., Plane, _load() (+6 more)

### Community 20 - "UIUC Airfoil Ingestion"
Cohesion: 0.25
Nodes (13): _collect_pairs(), detect_format_and_coords(), ingest_dat_file(), _normalize_unit_chord(), _parse_pair(), _ParseError, ndarray, UIUC .dat ingest: format auto-detect (Selig/Lednicer), normalize to canonical or (+5 more)

### Community 21 - "Canonical Airfoil Data Class"
Cohesion: 0.17
Nodes (7): Airfoil, A normalized, canonical-order airfoil., Trailing-edge gap (unit chord) = vertical distance between the         upper-TE, ndarray, Return canonical (N, 2) unit-chord points for `name`.      `uiuc:<file>` → inges, resolve_airfoil(), ValueError

### Community 22 - "Geometry Module & ADR Map"
Cohesion: 0.27
Nodes (13): backend/geometry/cove_profile.py (per-station cove/nose arc profiles), backend/geometry/reference.py (spar surfaces, rib planes, hinge axes, hardpoints), backend/geometry/te_cut.py (TE surface cut construction), backend/schema/errors.py (ConfigErrorCode enum), backend/schema/models.py (Config schema models), ADR-002: Per-station axis-centered arcs replace cylinder cove/nose mechanism, ADR-003: Single-arc nose + derived hinge-axis height replaces two-arc/Hermite blend, ADR-004: Drop LE droop from scope (+5 more)

### Community 23 - "Phase Plan & Failure Modes (F1/F9/F10)"
Cohesion: 0.19
Nodes (13): F1 OCC shell/thicken fails at TE -> banned; IML by offset+loft+subtract (P6), F10 STEP loses body names -> XDE path, re-import gate (P9), F9 Sweep misses collision between samples -> fine steps + swept-volume boolean (P8), P6 — Sandwich internals + hardpoints, P7 — Hinges (generated mode), P8 — Kinematic gate (the decisive R1 gate), P9 — Export (glTF/STL/STEP), Phase plan overview with executable gates (§9) (+5 more)

### Community 24 - "Curvature & Tangency Diagnostics"
Cohesion: 0.15
Nodes (13): _discrete_curvature_angle_proxy(), _point_to_shell_distance(), ndarray, Rigid rotation of `solid` about the real hinge line (point p0, dir h)     by ang, Angle (deg) between consecutive segments at each interior point — a     smooth a, DIRECT regression test for the reported bug: a discrete curvature-     angle pro, Anti-unporting angular overlap (ADR-003 addendum A): the nose arc is     extende, Min radial gap between the CS nose surface and the wing cove surface     equals (+5 more)

### Community 25 - "R0 Probes — OCC/Gmsh Kernel"
Cohesion: 0.17
Nodes (12): backend/geometry/booleans.py (fuzzy_cut/fuzzy_common + shard filter helpers), backend/geometry/iml.py (sandwich IML construction), False spar closing wall: flat sandwich cap built on the TE device cut plane, closes hollow interior boundary, OCP/gmsh ImportError: libGL.so.1 / libXcursor.so.1 missing, R0 Findings — P0, probe_gmsh.py: gmsh 4.15.2 mesh generation confirmed, probe_ocp.py: cadquery 2.8.0 import/box/IsValid confirmed, probe_ocp_boolean.py: cut->Compound, SetFuzzyValue, tilted cylinders, shard behavior (+4 more)

### Community 26 - "Failure Modes F6-F16 (Mfg/Export)"
Cohesion: 0.24
Nodes (12): F12 .cdb writer drifts from spec -> spec-derived independent oracle parser (P13), F14 Mold undercuts at cove/blunt TE -> demold scan (P16), F16 Ansys import passes proxies, fails in practice -> manual acceptance artifact required (P14), F6 Non-developable spar webs -> distorted DXF -> developability metric, silent unroll = fail (P17), F7 T-junction mesh: looks fine, structurally disconnected -> single-connected-component check (P13), F8 .cdb unit mismatch (mm vs m) -> mm-tonne-s header asserted (P13), Geometry pipeline, construction order (§8), P13 — .cdb writer + layup schedule (+4 more)

### Community 27 - "R0 Findings — P4 TE Cut Timing"
Cohesion: 0.27
Nodes (10): GEOMETRY_TEST_TIMEOUT_S = 600 (pytest-timeout budget for geometry gate tests), 2026-07-07 P4 refined per-station construction: audit fixes + test-architecture overhaul, Where things live (repo memory file map), Known Issues — OCC/Gmsh/ezdxf workaround knowledge base, P6 sandwich-shell booleans: hollow_common dominates, ~4.6x run-to-run variance, Twisted/tilted device configs cost 2-4x more per boolean than untwisted, R0 Findings — P4 (TE surface cut), probe_brep_cache.py: exportBrep/importBrep round-trip exact, enables geometry build cache (+2 more)

### Community 28 - "R0 Findings — P1 Airfoil Subsystem"
Cohesion: 0.24
Nodes (10): UIUC airfoil snapshot README, _quarantine_me.dat: intentionally malformed quarantine fixture, R0 Findings — P1 (Airfoil subsystem), Selig/Lednicer detection heuristic: threshold revised 1.0->1.5, F11 UIUC Selig/Lednicer confusion -> auto-detect + quarantine (P1, 0 silent failures), F15 Sandwich stack > local airfoil thickness -> P0 validation rule (<=80% min local thickness), F2 OCC segfault kills worker silently -> subprocess sandbox + reaper (P0 SIGKILL test), P0 — Foundation (repo scaffold, schema validation, worker sandbox) (+2 more)

### Community 29 - "Joint Retention Design (D8/D10/ADR-001)"
Cohesion: 0.28
Nodes (9): ADR-001: Bolted spar retention replaces over-center toggle latch, D10 Joint retention: 1 vertical Z-bolt per housing, aluminum-only preload path, D20 Reports: bilingual EN/AR, lualatex RTL, D8 Segment joints: both spars carry male tongues into female boxes, insertion-axis-parallel, F17 Flat housing lip sits proud/sunk on curved OML -> lip cap rule + flushness gate (P18), F18 Bolt preload crushes hollow composite tongue -> aluminum-only preload path; continuity gate (P18), P18 — Joint retention hardware + COTS hinge mode, P19 — Bilingual report (+1 more)

### Community 30 - "False Spar Closing Wall"
Cohesion: 0.32
Nodes (7): analytic_section_points(), Exact cross-section of the ruled OML loft by the plane through C,     normal h —, build_false_spar(), FalseSpar, Solid, False spar: closing wall for the TE device cut (plan.md §8.5 step 5 / §8.7 step, Build the wing-side closing wall for the enabled te_surface device.     `section

### Community 31 - "Config Error Code Enum"
Cohesion: 0.32
Nodes (6): ConfigErrorCode, ConfigValidationError, Enum, str, Config validation error codes.  Every config rejection carries one of these code, Raised by cross-field validators with an actionable, coded message.

### Community 32 - "BRep Cache R0 Probe"
Cohesion: 0.36
Nodes (7): main(), Shape, R0 probe: BRep export/import round-trip, for the P4 geometry build cache (docs/k, Try cadquery's own Shape.exportBrep/importBrep convenience wrappers,     if this, Raw OCP BRepTools.Write_s / Read_s, the underlying OCC serialization     call ca, round_trip_via_cq_shape_methods(), round_trip_via_raw_occp()

### Community 33 - "Tolerance Constants (P3)"
Cohesion: 0.33
Nodes (7): COVE_CLEARANCE_MM = 5.0 (nose-to-cove radial clearance), KERNEL_TOLERANCE_MM (reused in place of a bare 1e-5 literal in P3 gate), NOSE_TANGENCY_MAX_DEG = 2.0 deg (mean-radius tangency error gate, calibrated from measurement), OVERLAP_MARGIN_DEG = 4.0 deg (anti-unporting angular overlap margin), PLY_THICKNESS_MM_PROVISIONAL (promoted from validators.py private dict to tolerances.py), backend/tolerances.py (every numeric tolerance in the tool), 2026-07-05 P3 (Reference geometry) DONE entry

### Community 34 - "Nose Tangency Validation Test"
Cohesion: 0.33
Nodes (6): mean_radius_tangency_err_deg(), How far the single mean-radius arc (R=(Ru+Rl)/2) deviates from the     TRUE per-, ADR-003 config-time validation: the single mean-radius nose arc     (StationFeet, _validate_nose_tangency(), The single mean-radius arc (R=(Ru+Rl)/2, ADR-003) must stay within     NOSE_TANG, test_nose_tangency()

### Community 35 - "Watertightness Gate Tests"
Cohesion: 0.33
Nodes (6): is_watertight(), Solid, Watertight = OCC-valid AND every shell is closed (r0_findings/p02.md)., Slow tier: force one real, uncached rebuild per config (bypassing the     cache, test_exactly_two_watertight_bodies(), test_fresh_build_matches_gate_criteria()

### Community 36 - "Hinge Axis Construction & R0 Probe"
Cohesion: 0.47
Nodes (5): build_hinge_axes(), TE hinge axis (straight, containment-sampled, DERIVED height — see     derive_hi, Edge, _append(), main()

### Community 37 - "R0 Findings — P2 OML Loft"
Cohesion: 0.40
Nodes (6): 2026-07-05 P2 (Sections + OML loft) DONE entry, Unmatched shell glob reaches pytest as a literal path, R0 Findings — P2 (Sections + OML loft), IsValid() necessary-but-not-sufficient trap: misaligned start point distorts loft volume 5x while still reporting valid, Spline+ruled=False bulges ~3.1%/unstable -> switched to polygon wires + ruled=True, scripts/run_regress.py (regression runner across all prior gates)

### Community 38 - "R0 Findings — P3 Reference Geometry"
Cohesion: 0.33
Nodes (6): Gate Changes (audit log), p03 gate change 2026-07-08: dropped config.le_droop branch from test_forced_rib_planes_at_device_edges, R0 Findings — P3 (Reference geometry), BRepExtrema_DistShapeShape(vertex,SOLID) is always 0 for interior points; must use distance-to-Shell for a real margin, F5 Twist pushes hinge axis out of OML mid-span -> sampled containment (P3), P3 — Reference geometry (spars, ribs, hinge axes, hardpoints)

### Community 39 - "Web UI & Segmentation Phases"
Cohesion: 0.33
Nodes (6): Frontend README (React + three.js viewer placeholder), D1 Interaction: Web UI, three.js viewer, body toggles + deflection slider (v1), F19 Non-parallel tongues make panel un-insertable -> parallel-by-construction + insertion-sweep gate (P11), P10 — Web UI E2E (Playwright), P11 — 3-piece wing (segmentation), P12 — Midsurface STEP

### Community 40 - "Nose Arc Sampling Test"
Cohesion: 0.40
Nodes (5): Shape, Sample the cross-section of `shape` by the plane through C, normal h,     into a, section_points(), Sealed-region (nose arc) points on the ACTUAL built CS solid — sampled     via a, test_nose_is_single_arc()

### Community 41 - "OCP Loft R0 Probe"
Cohesion: 0.60
Nodes (4): _append(), _closed_wire(), main(), Build a closed wire at height z from canonical airfoil points using a     spline

### Community 42 - "Ansys .cdb Oracle Writer"
Cohesion: 0.50
Nodes (4): APDL blocked-format spec, .cdb writer (planned P13), F12: writer and verifier must not share a bug, tests/oracle/README.md

## Knowledge Gaps
- **63 isolated node(s):** `wingstructgen`, `ADR-0003`, `Where things live (repo memory file map)`, `wingo (repo README)`, `Units convention: mm/deg, suffixed schema fields` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Reference Geometry & Config Root` to `Database Models & ORM`, `Wing Config Data Models`, `Hinge Axis Construction & R0 Probe`, `OML Loft Construction`, `TE Cut Test Fixtures & Tolerances`, `Airfoil Resampling Pipeline`, `TE Surface Cut Construction`, `Sandwich IML Boolean Construction`, `Cove/Nose Arc Profile Construction`, `Spar Surfaces & Hardpoints`, `Hinge Frame & Viewer Export`, `False Spar Closing Wall`?**
  _High betweenness centrality (0.185) - this node is a cross-community bridge._
- **Why does `P3 — Reference geometry (spars, ribs, hinge axes, hardpoints)` connect `R0 Findings — P3 Reference Geometry` to `Reference Geometry & Config Root`, `R0 Findings — P1 Airfoil Subsystem`, `Geometry Module & ADR Map`, `Phase Plan & Failure Modes (F1/F9/F10)`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `ADR-004: Drop LE droop from scope` connect `Geometry Module & ADR Map` to `Agent Instructions & Conventions`, `R0 Findings — P3 Reference Geometry`, `Kickoff Design Decisions (D12-D18)`, `Changelog & Validator Constants`, `Reference Geometry & Config Root`, `Phase Plan & Failure Modes (F1/F9/F10)`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `Config` (e.g. with `FalseSpar` and `SandwichBody`) actually correct?**
  _`Config` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `PlacedSection` (e.g. with `StationFeet` and `FalseSpar`) actually correct?**
  _`PlacedSection` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Geometric comparison metrics for airfoils.  Airfoil surfaces are near-vertical a`, `Max over `query` points of the minimum Euclidean distance from that     point to`, `NACA 4- and 5-digit airfoil generators (closed-form).  Produces canonical-order` to the rest of the system?**
  _216 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Database Models & ORM` be split into smaller, more focused modules?**
  _Cohesion score 0.057971014492753624 - nodes in this community are weakly interconnected._