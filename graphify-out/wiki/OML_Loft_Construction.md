# OML Loft Construction

> 26 nodes · cohesion 0.14

## Key Concepts

- **build_planform_sections()** (24 connections) — `backend/geometry/sections.py`
- **PlacedSection** (23 connections) — `backend/geometry/sections.py`
- **build_oml()** (18 connections) — `backend/geometry/loft.py`
- **test_p02_oml.py** (16 connections) — `tests/gates/test_p02_oml.py`
- **loft.py** (15 connections) — `backend/geometry/loft.py`
- **analytic_volume_estimate()** (7 connections) — `backend/geometry/loft.py`
- **build_section_wire()** (7 connections) — `backend/geometry/loft.py`
- **_full_span_points()** (6 connections) — `backend/geometry/loft.py`
- **test_golden_watertight_and_volume()** (6 connections) — `tests/gates/test_p02_oml.py`
- **_mirror_sections()** (5 connections) — `backend/geometry/loft.py`
- **_load()** (5 connections) — `tests/gates/test_p02_oml.py`
- **test_edge_no_self_intersection()** (5 connections) — `tests/gates/test_p02_oml.py`
- **_polygon_area_3d()** (4 connections) — `backend/geometry/loft.py`
- **ndarray** (4 connections)
- **test_twist_matches_hand_computed_rotation()** (4 connections) — `tests/gates/test_p02_oml.py`
- **Wire** (1 connections)
- **Master OML loft (plan.md §8.3).  Builds closed polygon section wires, lofts them** (1 connections) — `backend/geometry/loft.py`
- **Closed polygon wire through ordered (N,3) section points. `close=True`     adds** (1 connections) — `backend/geometry/loft.py`
- **Full-span ordered list of (N,3) point arrays: the y<0 side is the y>0     side r** (1 connections) — `backend/geometry/loft.py`
- **Loft the placed sections into a watertight OML solid (ruled, polygon     wires),** (1 connections) — `backend/geometry/loft.py`
- **Planar area of a (near-planar) closed 3D polygon = |vector area|.** (1 connections) — `backend/geometry/loft.py`
- **∫ cross-section-area along the true swept/dihedral span path — the     independe** (1 connections) — `backend/geometry/loft.py`
- **Build placed half-span sections at every station and segment boundary     (bound** (1 connections) — `backend/geometry/sections.py`
- **Path** (1 connections)
- **P2 gate — plan.md §9 pass criteria:    solid watertight (OCC closed-shell + vali** (1 connections) — `tests/gates/test_p02_oml.py`
- *... and 1 more nodes in this community*

## Relationships

- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (12 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (12 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (8 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (8 shared connections)
- [Watertightness Gate Tests](Watertightness_Gate_Tests.md) (5 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (5 shared connections)
- [Hinge Axis Construction & R0 Probe](Hinge_Axis_Construction_%26_R0_Probe.md) (4 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (4 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (2 shared connections)
- [Airfoil Metrics & NACA Generation](Airfoil_Metrics_%26_NACA_Generation.md) (2 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (1 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (1 shared connections)

## Source Files

- `backend/geometry/loft.py`
- `backend/geometry/sections.py`
- `tests/gates/test_p02_oml.py`

## Audit Trail

- EXTRACTED: 154 (96%)
- INFERRED: 6 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*