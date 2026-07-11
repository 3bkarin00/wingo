# Nose Tangency Validation Test

> 6 nodes · cohesion 0.33

## Key Concepts

- **mean_radius_tangency_err_deg()** (7 connections) — `backend/geometry/cove_profile.py`
- **_validate_nose_tangency()** (5 connections) — `backend/geometry/te_cut.py`
- **test_nose_tangency()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **How far the single mean-radius arc (R=(Ru+Rl)/2) deviates from the     TRUE per-** (1 connections) — `backend/geometry/cove_profile.py`
- **ADR-003 config-time validation: the single mean-radius nose arc     (StationFeet** (1 connections) — `backend/geometry/te_cut.py`
- **The single mean-radius arc (R=(Ru+Rl)/2, ADR-003) must stay within     NOSE_TANG** (1 connections) — `tests/gates/test_p04_te_cut.py`

## Relationships

- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (3 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (2 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (2 shared connections)
- [Config Error Code Enum](Config_Error_Code_Enum.md) (1 shared connections)

## Source Files

- `backend/geometry/cove_profile.py`
- `backend/geometry/te_cut.py`
- `tests/gates/test_p04_te_cut.py`

## Audit Trail

- EXTRACTED: 18 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*