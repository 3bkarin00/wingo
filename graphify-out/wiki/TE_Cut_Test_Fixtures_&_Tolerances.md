# TE Cut Test Fixtures & Tolerances

> 25 nodes · cohesion 0.12

## Key Concepts

- **test_p04_te_cut.py** (52 connections) — `tests/gates/test_p04_te_cut.py`
- **_build_cut_case()** (13 connections) — `tests/gates/test_p04_te_cut.py`
- **tolerances.py** (12 connections) — `backend/tolerances.py`
- **_station_data()** (11 connections) — `backend/geometry/te_cut.py`
- **TeCutRawShapes** (10 connections) — `backend/geometry/te_cut.py`
- **CutCase** (8 connections) — `tests/gates/test_p04_te_cut.py`
- **test_extreme_twist_config_rejected()** (7 connections) — `tests/gates/test_p04_te_cut.py`
- **_load()** (5 connections) — `tests/gates/test_p04_te_cut.py`
- **cut_result()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **cut_result_fresh()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **test_axis_equidistant_residual()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **test_loft_topology_uniform()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **The cheap half: hinge frame + per-station feet + loft-input polygons.     Pure n** (1 connections) — `backend/geometry/te_cut.py`
- **The expensive, cacheable half of the construction: raw boolean outputs     BEFOR** (1 connections) — `backend/geometry/te_cut.py`
- **Every numeric tolerance in WingStructGen, in one place (plan.md §0.5).  A tolera** (1 connections) — `backend/tolerances.py`
- **Path** (1 connections)
- **pytest_generate_tests()** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **P4 gate — plan.md §9 pass criteria + the refined per-station cove/nose construct** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **Shared by both the `cut_result` (cache-backed, fast) and     `cut_result_fresh`** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **The derived hinge-axis's least-squares fit residual (backend/geometry/     refer** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **Every station profile fed to the nose/cove loft must have identical     point co** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **ADR-003: te_half_twisted.yaml's -8deg tip twist at hinge_xc=0.72 is     delibera** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **test_no_shards()** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **test_volume_conservation()** (1 connections) — `tests/gates/test_p04_te_cut.py`
- **_write_timings()** (1 connections) — `tests/gates/test_p04_te_cut.py`

## Relationships

- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (12 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (8 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (8 shared connections)
- [Curvature & Tangency Diagnostics](Curvature_%26_Tangency_Diagnostics.md) (7 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (6 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (4 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (4 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (4 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (3 shared connections)
- [Watertightness Gate Tests](Watertightness_Gate_Tests.md) (3 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (3 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (2 shared connections)

## Source Files

- `backend/geometry/te_cut.py`
- `backend/tolerances.py`
- `tests/gates/test_p04_te_cut.py`

## Audit Trail

- EXTRACTED: 132 (92%)
- INFERRED: 11 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*