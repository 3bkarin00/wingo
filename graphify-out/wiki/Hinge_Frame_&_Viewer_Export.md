# Hinge Frame & Viewer Export

> 18 nodes · cohesion 0.19

## Key Concepts

- **export_viewer_data.py** (26 connections) — `scripts/export_viewer_data.py`
- **hinge_frame()** (16 connections) — `backend/geometry/te_cut.py`
- **_export_one()** (15 connections) — `scripts/export_viewer_data.py`
- **_sandwich_export()** (11 connections) — `scripts/export_viewer_data.py`
- **_curvature_check()** (6 connections) — `scripts/export_viewer_data.py`
- **_curvature_angle_proxy()** (4 connections) — `scripts/export_viewer_data.py`
- **_load_gate_metrics()** (3 connections) — `scripts/export_viewer_data.py`
- **main()** (3 connections) — `scripts/export_viewer_data.py`
- **_rib_rectangle()** (3 connections) — `scripts/export_viewer_data.py`
- **_tessellate()** (3 connections) — `scripts/export_viewer_data.py`
- **ndarray** (2 connections)
- **Path** (2 connections)
- **(p_start, p_end, h, a, u, axis_len). h = hinge-axis unit dir; a =     chordwise-** (1 connections) — `backend/geometry/te_cut.py`
- **P6 WIP (backend/geometry/iml.py): clean-span-only sandwich shells for     the wi** (1 connections) — `scripts/export_viewer_data.py`
- **A generous rectangle in the rib plane (X-Z at fixed Y), sized to the     local c** (1 connections) — `scripts/export_viewer_data.py`
- **Angle (deg) between consecutive segments at each interior point — the     exact** (1 connections) — `scripts/export_viewer_data.py`
- **Curvature-angle proxy at 5 representative nose stations (root/25%/     50%/75%/t** (1 connections) — `scripts/export_viewer_data.py`
- **Pull this config's ALREADY-VERIFIED numbers straight from the real     gate arti** (1 connections) — `scripts/export_viewer_data.py`

## Relationships

- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (6 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (5 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (4 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (4 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (3 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (3 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (3 shared connections)
- [Curvature & Tangency Diagnostics](Curvature_%26_Tangency_Diagnostics.md) (3 shared connections)
- [Watertightness Gate Tests](Watertightness_Gate_Tests.md) (3 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (2 shared connections)
- [Hinge Axis Construction & R0 Probe](Hinge_Axis_Construction_%26_R0_Probe.md) (1 shared connections)
- [Nose Arc Sampling Test](Nose_Arc_Sampling_Test.md) (1 shared connections)

## Source Files

- `backend/geometry/te_cut.py`
- `scripts/export_viewer_data.py`

## Audit Trail

- EXTRACTED: 100 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*