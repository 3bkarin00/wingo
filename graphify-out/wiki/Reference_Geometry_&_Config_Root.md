# Reference Geometry & Config Root

> 16 nodes · cohesion 0.21

## Key Concepts

- **Config** (54 connections) — `backend/schema/models.py`
- **test_p03_reference.py** (17 connections) — `tests/gates/test_p03_reference.py`
- **build_reference_geometry()** (13 connections) — `backend/geometry/reference.py`
- **build_rib_planes()** (6 connections) — `backend/geometry/reference.py`
- **test_hinge_axis_straightness_and_containment()** (6 connections) — `tests/gates/test_p03_reference.py`
- **_load()** (5 connections) — `tests/gates/test_p03_reference.py`
- **ReferenceGeometry** (4 connections) — `backend/geometry/reference.py`
- **_sandwich_stack_mm()** (4 connections) — `tests/gates/test_p03_reference.py`
- **test_forced_rib_planes_at_device_edges()** (4 connections) — `tests/gates/test_p03_reference.py`
- **Rib planes (auto + forced at device edges and break stations).** (1 connections) — `backend/geometry/reference.py`
- **._p0_cross_field_rules()** (1 connections) — `backend/schema/models.py`
- **Root config model — the whole §6 input schema.** (1 connections) — `backend/schema/models.py`
- **Plane** (1 connections)
- **Path** (1 connections)
- **P3 gate — plan.md §9 pass criteria:    axis straightness exact by construction (** (1 connections) — `tests/gates/test_p03_reference.py`
- **core + 2x face-sheet, reusing the same provisional ply-thickness table     as th** (1 connections) — `tests/gates/test_p03_reference.py`

## Relationships

- [OML Loft Construction](OML_Loft_Construction.md) (12 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (9 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (7 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (6 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (6 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (6 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (5 shared connections)
- [Hinge Axis Construction & R0 Probe](Hinge_Axis_Construction_%26_R0_Probe.md) (4 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (4 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (3 shared connections)
- [Database Models & ORM](Database_Models_%26_ORM.md) (3 shared connections)
- [R0 Findings — P3 Reference Geometry](R0_Findings_%E2%80%94_P3_Reference_Geometry.md) (2 shared connections)

## Source Files

- `backend/geometry/reference.py`
- `backend/schema/models.py`
- `tests/gates/test_p03_reference.py`

## Audit Trail

- EXTRACTED: 109 (91%)
- INFERRED: 11 (9%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*