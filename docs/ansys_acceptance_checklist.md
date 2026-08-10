# Ansys Acceptance Checklist v1.0

**Purpose:** Formal manual acceptance procedure for WingStructGen Ansys export package.
**Reference:** plan.md §9 P14 — "CI proxy gates + formal manual acceptance checklist committed as artifact"
**Trigger:** Re-run whenever P12 (midsurface STEP) or P13 (.cdb writer) code changes.

---

## Pre-requisites

- [ ] Ansys Mechanical APDL (or Ansys Workbench Mechanical) installed and licensed
- [ ] WingStructGen-generated STEP midsurface files available (from P12 export)
- [ ] WingStructGen-generated .cdb file available (from P13 writer)
- [ ] WingStructGen-generated layup schedule CSV/JSON available (from P13 writer)
- [ ] Target element size noted (from `ansys_export.target_element_size_mm` in config)

---

## Part A: STEP Midsurface Import (SpaceClaim / DesignModeler)

### A1. Shared Topology

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| A1.1 | Import STEP midsurface file into SpaceClaim | ☐ | |
| A1.2 | Enable **Shared Topology** (Geometry → Data Preprocessing → Shared Topology) | ☐ | Must be ON for layered shell assignment |
| A1.3 | Verify all midsurface faces are imported (count matches P12 export) | ☐ | Compare face count with `MidsurfaceResult.faces` |
| A1.4 | Verify body names are preserved (per §5 naming contract) | ☐ | SEG-{C|L|R}/BODY-{name} format |
| A1.5 | No gaps or overlaps between adjacent midsurfaces | ☐ | Check at rib-skin and rib-spar interfaces |

### A2. Named Selections

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| A2.1 | Named selections from `ansys_export.named_selections` are present | ☐ | |
| A2.2 | Each named selection contains correct entities (faces/edges) | ☐ | |
| A2.3 | Named selection names match §5 naming contract | ☐ | |

---

## Part B: Mesh at Target Element Size

### B1. Global Mesh Settings

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| B1.1 | Element size set to `target_element_size_mm` (from config) | ☐ | |
| B1.2 | Element type: SHELL281 (28-node layered shell) | ☐ | |
| B1.3 | Mesh quality check: min skew angle < 0.85 | ☐ | |
| B1.4 | No zero-volume elements | ☐ | |

### B2. Mesh Connectivity (F7)

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| B2.1 | All midsurface bodies share nodes at interfaces | ☐ | T-junction check |
| B2.2 | Mesh forms single connected component | ☐ | Compare with P13 oracle parser result |
| B2.3 | No floating nodes (nodes not connected to any element) | ☐ | |

---

## Part C: Layered Shell Section Assignment

### C1. Material and Layup

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| C1.1 | Create material definitions from materials DB (D17) | ☐ | E1, E2, G12, ν12, density, ply thickness |
| C1.2 | Create layered shell sections matching layup schedule CSV | ☐ | |
| C1.3 | Number of layers matches `skin.face_sheet.plies` + core | ☐ | |
| C1.4 | Ply angles match layup schedule (0° default) | ☐ | |
| C1.5 | Ply thicknesses match `ply_thickness × plies + core_thickness` | ☐ | |
| C1.6 | Assign sections to correct bodies via named selections | ☐ | |

### C2. Layup Verification

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| C2.1 | Total laminate thickness = face_sheet_plies × ply_thickness + core_thickness | ☐ | |
| C2.2 | Symmetric layup (if configured) | ☐ | |
| C2.3 | All layers have valid material assignment | ☐ | |

---

## Part D: .cdb Import (Mechanical APDL)

### D1. Command Block Database

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| D1.1 | Import .cdb file via `/INPUT,file,cdb` | ☐ | |
| D1.2 | Node count matches P13 writer output | ☐ | |
| D1.3 | Element count matches P13 writer output | ☐ | |
| D1.4 | Element types are SHELL281 | ☐ | |
| D1.5 | Section numbers match SECTYPE definitions | ☐ | |
| D1.6 | Component names (CMBLOCK) are preserved | ☐ | |

### D2. Units Verification (F8)

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| D2.1 | `/UNITS,1` present in .cdb header (mm–tonne–s) | ☐ | |
| D2.2 | Imported geometry dimensions match expected (mm) | ☐ | Spot-check: span = `planform.span_mm` |
| D2.3 | No unit conversion warnings from APDL | ☐ | |

### D3. /CHECK Clean

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| D3.1 | Run `/CHECK` command — no errors | ☐ | |
| D3.2 | Run `/CHECK` command — no warnings (or warnings documented) | ☐ | |
| D3.3 | `*STATUS,NODE` shows correct node count | ☐ | |
| D3.4 | `*STATUS,ELEM` shows correct element count | ☐ | |

---

## Part E: Static Structural Verification (Optional but Recommended)

### E1. Boundary Conditions

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| E1.1 | Apply fixed support at fuselage attachment hardpoints | ☐ | |
| E1.2 | Apply pressure load (uniform or aerodynamic) | ☐ | |
| E1.3 | Verify reaction forces at supports | ☐ | Sum should equal applied load |

### E2. Solution

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| E2.1 | Solution completes without errors | ☐ | |
| E2.2 | Maximum displacement is within acceptable range | ☐ | < span/500 as rough guideline |
| E2.3 | Maximum stress is below material allowable | ☐ | |
| E2.4 | No element failure warnings | ☐ | |

---

## Sign-off

| Field | Value |
|-------|-------|
| **Tester Name** | |
| **Ansys Version** | (e.g., 2024 R2) |
| **Date** | YYYY-MM-DD |
| **Config Used** | (benchmark config filename) |
| **Overall Result** | ☐ PASS / ☐ FAIL |
| **Comments** | |

---

## Commit Procedure

After successful completion:

1. Fill in all check boxes and sign-off fields
2. Save this document as `docs/ansys_acceptance_checklist.md`
3. Commit to repository: `git add docs/ansys_acceptance_checklist.md && git commit -m "P14: Ansys acceptance checklist v1.0 signed by <name>"`
4. Store a copy of the signed checklist in the `ansys_acceptance` Postgres table (when available)
5. Update `artifacts/state.json` to record the acceptance date and tester

---

## Re-run Triggers

Re-run this checklist when:
- P12 (midsurface STEP) code changes
- P13 (.cdb writer) code changes
- Schema models change (affects naming, layer stack)
- Tolerances change (affects element sizing)
- Ansys version upgrade
