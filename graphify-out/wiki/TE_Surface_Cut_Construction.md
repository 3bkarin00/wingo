# TE Surface Cut Construction

> 23 nodes · cohesion 0.15

## Key Concepts

- **te_cut.py** (38 connections) — `backend/geometry/te_cut.py`
- **build_te_cut_shapes()** (14 connections) — `backend/geometry/te_cut.py`
- **cut_te_surface()** (9 connections) — `backend/geometry/te_cut.py`
- **finish_te_cut()** (8 connections) — `backend/geometry/te_cut.py`
- **_aft_box()** (7 connections) — `backend/geometry/te_cut.py`
- **_loft_region()** (7 connections) — `backend/geometry/te_cut.py`
- **ndarray** (6 connections)
- **TeCutResult** (6 connections) — `backend/geometry/te_cut.py`
- **_close_nose_polygon()** (4 connections) — `backend/geometry/te_cut.py`
- **_close_polygon()** (4 connections) — `backend/geometry/te_cut.py`
- **Solid** (4 connections)
- **_station_point()** (4 connections) — `backend/geometry/te_cut.py`
- **_vec()** (4 connections) — `backend/geometry/te_cut.py`
- **Vector** (3 connections)
- **Trailing-edge control-surface cut (plan.md §8.5, refined per-station arc constru** (1 connections) — `backend/geometry/te_cut.py`
- **Point on the hinge axis at arc-length s from p0.** (1 connections) — `backend/geometry/te_cut.py`
- **Close an open forward-arc polyline (from Pl-side to Pu-side) into a     simple p** (1 connections) — `backend/geometry/te_cut.py`
- **Close the nose forward-arc, extending aft by `aft_reach` beyond the     hinge so** (1 connections) — `backend/geometry/te_cut.py`
- **Hard precondition (ADR-003 point 5, not just a gate test): every     station pro** (1 connections) — `backend/geometry/te_cut.py`
- **Box on the +a side of the hinge-axis plane. Local frame x=a (aft),     z=u (up),** (1 connections) — `backend/geometry/te_cut.py`
- **The expensive, cacheable half: nose/cove lofts, aft boxes, and the two     boole** (1 connections) — `backend/geometry/te_cut.py`
- **The cheap half: F3 shard-filter + sort + gap-volume arithmetic. ALWAYS     run f** (1 connections) — `backend/geometry/te_cut.py`
- **Direct, uncached build+finish — for callers that always want a fresh     result** (1 connections) — `backend/geometry/te_cut.py`

## Relationships

- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (12 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (8 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (5 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (5 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (4 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (3 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (2 shared connections)
- [Nose Tangency Validation Test](Nose_Tangency_Validation_Test.md) (2 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (2 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (1 shared connections)
- [Hinge Axis Construction & R0 Probe](Hinge_Axis_Construction_%26_R0_Probe.md) (1 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (1 shared connections)

## Source Files

- `backend/geometry/te_cut.py`

## Audit Trail

- EXTRACTED: 123 (97%)
- INFERRED: 4 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*