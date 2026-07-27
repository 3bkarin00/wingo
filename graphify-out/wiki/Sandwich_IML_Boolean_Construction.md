# Sandwich IML Boolean Construction

> 21 nodes · cohesion 0.14

## Key Concepts

- **iml.py** (20 connections) — `backend/geometry/iml.py`
- **fuzzy_common()** (12 connections) — `backend/geometry/booleans.py`
- **build_sandwich_lofts()** (11 connections) — `backend/geometry/iml.py`
- **build_sandwich_body()** (9 connections) — `backend/geometry/iml.py`
- **face_sheet_thickness_mm()** (6 connections) — `backend/geometry/iml.py`
- **_parting_polygon()** (6 connections) — `backend/geometry/iml.py`
- **SandwichBody** (5 connections) — `backend/geometry/iml.py`
- **SandwichLofts** (5 connections) — `backend/geometry/iml.py`
- **_camber_polyline()** (4 connections) — `backend/geometry/iml.py`
- **_offset_wire()** (3 connections) — `backend/geometry/iml.py`
- **ndarray** (2 connections)
- **a ∩ b (intersection) with an explicit fuzzy value.** (1 connections) — `backend/geometry/booleans.py`
- **Shape** (1 connections)
- **Wire** (1 connections)
- **Sandwich-skin IML construction (plan.md §8.7), CLEAN-SPAN ONLY.  IML by **2D per** (1 connections) — `backend/geometry/iml.py`
- **Face-sheet stack thickness (mm) — same provisional ply-thickness     lookup alre** (1 connections) — `backend/geometry/iml.py`
- **Exact camber polyline (TE→LE, world coords) of one placed section.     Canonical** (1 connections) — `backend/geometry/iml.py`
- **Closed planar polygon (constant-Y station plane) bounding the region     BELOW t** (1 connections) — `backend/geometry/iml.py`
- **Per-station chained full-value offset (face_mm, core_mm, face_mm — see     modul** (1 connections) — `backend/geometry/iml.py`
- **Cuts the per-station lofts (built over the FULL original span) against     the A** (1 connections) — `backend/geometry/iml.py`
- **Per-body sandwich layers, three per wall (outer face / core / inner     face). T** (1 connections) — `backend/geometry/iml.py`

## Relationships

- [OML Loft Construction](OML_Loft_Construction.md) (8 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (7 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (5 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (5 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (4 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (2 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (2 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (1 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (1 shared connections)

## Source Files

- `backend/geometry/booleans.py`
- `backend/geometry/iml.py`

## Audit Trail

- EXTRACTED: 89 (96%)
- INFERRED: 4 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*