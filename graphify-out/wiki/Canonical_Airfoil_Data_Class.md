# Canonical Airfoil Data Class

> 13 nodes · cohesion 0.17

## Key Concepts

- **Airfoil** (15 connections) — `backend/airfoils/types.py`
- **resolve_airfoil()** (14 connections) — `backend/geometry/airfoil_resolver.py`
- **ValueError** (11 connections)
- **.__post_init__()** (2 connections) — `backend/airfoils/types.py`
- **.te_thickness()** (2 connections) — `backend/airfoils/types.py`
- **._odd_resample_points()** (2 connections) — `backend/schema/models.py`
- **._span_ordered()** (2 connections) — `backend/schema/models.py`
- **.n_points()** (1 connections) — `backend/airfoils/types.py`
- **.to_list()** (1 connections) — `backend/airfoils/types.py`
- **A normalized, canonical-order airfoil.** (1 connections) — `backend/airfoils/types.py`
- **Trailing-edge gap (unit chord) = vertical distance between the         upper-TE** (1 connections) — `backend/airfoils/types.py`
- **ndarray** (1 connections)
- **Return canonical (N, 2) unit-chord points for `name`.      `uiuc:<file>` → inges** (1 connections) — `backend/geometry/airfoil_resolver.py`

## Relationships

- [Airfoil Metrics & NACA Generation](Airfoil_Metrics_%26_NACA_Generation.md) (5 shared connections)
- [NACA 4/5-Digit Generators](NACA_4-5-Digit_Generators.md) (4 shared connections)
- [UIUC Airfoil Ingestion](UIUC_Airfoil_Ingestion.md) (4 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (4 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (2 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (2 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (2 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (1 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (1 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (1 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (1 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (1 shared connections)

## Source Files

- `backend/airfoils/types.py`
- `backend/geometry/airfoil_resolver.py`
- `backend/schema/models.py`

## Audit Trail

- EXTRACTED: 37 (69%)
- INFERRED: 17 (31%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*