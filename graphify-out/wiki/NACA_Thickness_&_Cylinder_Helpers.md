# NACA Thickness & Cylinder Helpers

> 29 nodes · cohesion 0.11

## Key Concepts

- **filter_shards()** (15 connections) — `backend/geometry/booleans.py`
- **booleans.py** (11 connections) — `backend/geometry/booleans.py`
- **fuzzy_cut()** (11 connections) — `backend/geometry/booleans.py`
- **min_thickness_mm()** (9 connections) — `backend/airfoils/naca_thickness.py`
- **probe_ocp_offset.py** (7 connections) — `scripts/r0_probes/probe_ocp_offset.py`
- **probe_ocp_offset_3layer.py** (7 connections) — `scripts/r0_probes/probe_ocp_offset_3layer.py`
- **main()** (7 connections) — `scripts/r0_probes/probe_ocp_offset.py`
- **main()** (6 connections) — `scripts/r0_probes/probe_ocp_offset_3layer.py`
- **Shape** (5 connections)
- **coaxial_cylinder_radii()** (4 connections) — `backend/geometry/booleans.py`
- **_solids()** (4 connections) — `backend/geometry/booleans.py`
- **validate_sandwich_stack()** (4 connections) — `backend/schema/validators.py`
- **test_no_interbody_tangency()** (4 connections) — `tests/gates/test_p04_te_cut.py`
- **naca_thickness.py** (3 connections) — `backend/airfoils/naca_thickness.py`
- **thickness_frac()** (3 connections) — `backend/airfoils/naca_thickness.py`
- **Solid** (2 connections)
- **_append()** (2 connections) — `scripts/r0_probes/probe_ocp_offset_3layer.py`
- **_append()** (2 connections) — `scripts/r0_probes/probe_ocp_offset.py`
- **_station_solid_from_points()** (2 connections) — `scripts/r0_probes/probe_ocp_offset.py`
- **Minimal analytic NACA4/5 thickness helper.  Standalone from the full P1 airfoil** (1 connections) — `backend/airfoils/naca_thickness.py`
- **Full thickness at x_frac, as a fraction of chord. None if unparseable.** (1 connections) — `backend/airfoils/naca_thickness.py`
- **Minimum thickness (mm) over the sampled mid-chord region. None if the     airfoi** (1 connections) — `backend/airfoils/naca_thickness.py`
- **ndarray** (1 connections)
- **Shared boolean helpers for the device-cut phases (P4+).  Centralizes the two thi** (1 connections) — `backend/geometry/booleans.py`
- **base − tool with an explicit fuzzy value (default from tolerances).** (1 connections) — `backend/geometry/booleans.py`
- *... and 4 more nodes in this community*

## Relationships

- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (7 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (5 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (4 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (4 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (2 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (2 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (1 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (1 shared connections)

## Source Files

- `backend/airfoils/naca_thickness.py`
- `backend/geometry/booleans.py`
- `backend/schema/validators.py`
- `scripts/r0_probes/probe_ocp_offset.py`
- `scripts/r0_probes/probe_ocp_offset_3layer.py`
- `tests/gates/test_p04_te_cut.py`

## Audit Trail

- EXTRACTED: 118 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*