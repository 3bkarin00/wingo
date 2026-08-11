# Handoff — 2026-08-11
## State
- Release/Phase: R2 COMPLETE — P00-P21 DONE (main branch)
- Gates passed: p00-p21 (22/22)
- Regression: 352 passed, 1 skipped (full suite, 8:20) — ALL GATES CLEAN
- Fixed: p13 regression (missing __init__.py in tests/ and tests/oracle/) — all 16 p13 tests now pass

## Completed phases
- P00-P03: Foundation, airfoils, OML loft, reference geometry (original gates)
- P04: Fast/full/incremental build pipeline (backend/geometry/pipeline.py)
- P05: Incremental station rebuild via WingDependencyGraph (backend/core/wing_graph.py)
- P06: Dependency graph core (backend/core/dependency.py) — DAG, BFS invalidation, Kahn's topo order
- P07 (hinges): Hinge geometry (backend/geometry/hinges.py) — coaxial hinge holes, lug/tang features
- P07 (multires): Multi-resolution geometry (backend/geometry/multires.py) — 51/127/199-pt presets
- P08 (kinematic): Kinematic sweep (backend/geometry/kinematic.py) — ±max_deflection sweep, collision detection
- P08 (memory): Memory profiling module (backend/geometry/memory.py)
- P09: FastAPI app (backend/api/app.py) — job CRUD, WebSocket progress, artifact serving
- P10: Mesh simplification/LOD (backend/geometry/mesh.py) — tessellation stats, LOD levels
- P11 (segmentation): 3-piece wing (backend/geometry/segmentation.py) — tongue/box joints, insertion sweep
- P12 (midsurface STEP): Midsurface construction (backend/geometry/midsurface.py) — face extraction, sliver scan, STEP export/import
- P13 (.cdb writer + layup): backend/exporters/cdb_writer.py + layup.py — APDL NBLOCK/EBLOCK/ET/SECTYPE/SECDATA/CMBLOCK writer, independent oracle parser (tests/oracle/cdb_parser.py), CSV+JSON layup schedule
- P14: Manual Ansys acceptance checklist (docs/ansys_acceptance_checklist.md)
- P15 (molds): backend/geometry/molds.py — parting curves, mold halves, assembly, cavity closure, pin coaxiality
- P16 (demold): backend/geometry/demold.py — undercut scan, stock sectioning, alignment features
- P17 (dxf): backend/exporters/dxf_flat.py — rib/spar flat patterns, area validation, developability check
- P18 (joint retention): backend/geometry/joint_retention.py — aluminum housings, Z-bolts, countersink lips, tongue clearance holes, preload-path continuity, COTS hinge pockets, bore chain coaxiality, lip flushness
- P19 (bilingual report): backend/report/bilingual.py — lualatex Docker container (EN/AR, Amiri font), report from gate_results, API endpoint /api/reports/{job_id}
- P20 (shape validation): backend/geometry/validate.py — bounding box, face area, symmetry, chord, volume checks (35 tests)
- P21 (web UI): backend/api/tessellation.py + frontend/ — React + three.js 3D viewer, LOD tessellation API, 9 tests

## R2 Complete
All 22 phases (P00-P21) of Release 2 are complete. 22/22 gates passed.

## P21 Web UI — Known Issues & Fixes
- **FIXED**: Vite dev server dependency pre-bundling issue with @react-three/fiber and @react-three/drei
- **Fix**: Added `optimizeDeps.exclude: ['@react-three/fiber', '@react-three/drei']` to vite.config.js
- **Current setup**: Production build served via `frontend/server.py` (port 3000) with CORS headers
- API proxy: FastAPI runs on port 8000 (`uvicorn backend.api.app:app --reload --port 8000`)
- ConfigPanel sends `output` field inside `config` dict (required by Pydantic model)
- `tessellation.py` has duplicate `_get_db()` definition — only one needed
- Production build split into 3 chunks: react (141KB), app (155KB), three (667KB)

## Do not touch
- P00-P03 gates are frozen contracts
- OML construction is POLYGON wires + ruled=True
