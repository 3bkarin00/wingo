# Config

> God node · 54 connections · `backend/schema/models.py`

**Community:** [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md)

## Connections by Relation

### contains
- models.py `EXTRACTED`

### imports
- test_p04_te_cut.py `EXTRACTED`
- te_cut.py `EXTRACTED`
- export_viewer_data.py `EXTRACTED`
- reference.py `EXTRACTED`
- sections.py `EXTRACTED`
- iml.py `EXTRACTED`
- false_spar.py `EXTRACTED`
- test_p03_reference.py `EXTRACTED`
- test_p02_oml.py `EXTRACTED`
- validators.py `EXTRACTED`
- test_p00_foundation.py `EXTRACTED`
- geometry_cache.py `EXTRACTED`
- probe_ocp_section_loft.py `EXTRACTED`

### inherits
- BaseModel `EXTRACTED`

### method
- ._p0_cross_field_rules() `EXTRACTED`

### rationale_for
- Root config model — the whole §6 input schema. `EXTRACTED`

### references
- [build_planform_sections()](build_planform_sections%28%29.md) `EXTRACTED`
- hinge_frame() `EXTRACTED`
- _export_one() `EXTRACTED`
- build_false_spar() `EXTRACTED`
- derive_hinge_axis() `EXTRACTED`
- build_te_cut_shapes() `EXTRACTED`
- build_reference_geometry() `EXTRACTED`
- build_station_profiles() `EXTRACTED`
- build_sandwich_lofts() `EXTRACTED`
- build_spar_surfaces() `EXTRACTED`
- _station_data() `EXTRACTED`
- _sandwich_export() `EXTRACTED`
- build_hinge_axes() `EXTRACTED`
- build_hardpoints() `EXTRACTED`
- le_and_z_offset() `EXTRACTED`
- interp_station() `EXTRACTED`
- cut_te_surface() `EXTRACTED`
- get_or_build_shapes() `EXTRACTED`
- face_sheet_thickness_mm() `EXTRACTED`
- build_rib_planes() `EXTRACTED`

### uses
- [PlacedSection](PlacedSection.md) `INFERRED`
- TeCutRawShapes `INFERRED`
- CutCase `INFERRED`
- TeCutResult `INFERRED`
- SandwichLofts `INFERRED`
- SandwichBody `INFERRED`
- FalseSpar `INFERRED`
- ReferenceGeometry `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*