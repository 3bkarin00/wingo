# Wing Config Data Models

> 49 nodes · cohesion 0.07

## Key Concepts

- **models.py** (41 connections) — `backend/schema/models.py`
- **BaseModel** (28 connections)
- **validators.py** (15 connections) — `backend/schema/validators.py`
- **geometry_cache.py** (7 connections) — `tests/gates/geometry_cache.py`
- **get_or_build_shapes()** (7 connections) — `tests/gates/geometry_cache.py`
- **validate_device_windows()** (5 connections) — `backend/schema/validators.py`
- **cache_key()** (5 connections) — `tests/gates/geometry_cache.py`
- **DeviceWindow** (4 connections) — `backend/schema/models.py`
- **validate_gaps()** (4 connections) — `backend/schema/validators.py`
- **Airfoils** (3 connections) — `backend/schema/models.py`
- **_enabled_devices()** (3 connections) — `backend/schema/validators.py`
- **validate_hinge_vs_spar()** (3 connections) — `backend/schema/validators.py`
- **AlignmentPins** (2 connections) — `backend/schema/models.py`
- **AnsysExport** (2 connections) — `backend/schema/models.py`
- **Core** (2 connections) — `backend/schema/models.py`
- **FaceSheet** (2 connections) — `backend/schema/models.py`
- **FuselageAttachment** (2 connections) — `backend/schema/models.py`
- **FuselageBolt** (2 connections) — `backend/schema/models.py`
- **Hardpoints** (2 connections) — `backend/schema/models.py`
- **Hinges** (2 connections) — `backend/schema/models.py`
- **Housing** (2 connections) — `backend/schema/models.py`
- **HousingLip** (2 connections) — `backend/schema/models.py`
- **JointBolt** (2 connections) — `backend/schema/models.py`
- **JointRetention** (2 connections) — `backend/schema/models.py`
- **LighteningHoles** (2 connections) — `backend/schema/models.py`
- *... and 24 more nodes in this community*

## Relationships

- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (7 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (6 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (4 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (2 shared connections)
- [NACA Thickness & Cylinder Helpers](NACA_Thickness_%26_Cylinder_Helpers.md) (2 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (1 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (1 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (1 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (1 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (1 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (1 shared connections)
- [Database Models & ORM](Database_Models_%26_ORM.md) (1 shared connections)

## Source Files

- `backend/schema/models.py`
- `backend/schema/validators.py`
- `tests/gates/geometry_cache.py`

## Audit Trail

- EXTRACTED: 188 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*