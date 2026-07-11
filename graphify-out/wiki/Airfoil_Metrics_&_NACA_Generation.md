# Airfoil Metrics & NACA Generation

> 19 nodes · cohesion 0.15

## Key Concepts

- **test_p01_airfoils.py** (20 connections) — `tests/gates/test_p01_airfoils.py`
- **generate_naca()** (17 connections) — `backend/airfoils/naca.py`
- **QuarantinedAirfoil** (8 connections) — `backend/airfoils/types.py`
- **ingest_snapshot()** (8 connections) — `backend/airfoils/uiuc_ingest.py`
- **max_point_to_curve_deviation()** (6 connections) — `backend/airfoils/metrics.py`
- **test_naca_matches_published()** (5 connections) — `tests/gates/test_p01_airfoils.py`
- **test_resample_round_trip()** (4 connections) — `tests/gates/test_p01_airfoils.py`
- **metrics.py** (3 connections) — `backend/airfoils/metrics.py`
- **Path** (2 connections)
- **ingested()** (2 connections) — `tests/gates/test_p01_airfoils.py`
- **test_zero_silent_failures()** (2 connections) — `tests/gates/test_p01_airfoils.py`
- **ndarray** (1 connections)
- **Max over `query` points of the minimum Euclidean distance from that     point to** (1 connections) — `backend/airfoils/metrics.py`
- **Geometric comparison metrics for airfoils.  Airfoil surfaces are near-vertical a** (1 connections) — `backend/airfoils/metrics.py`
- **Generate a NACA 4- or 5-digit airfoil as a canonical Airfoil.      Raises ValueE** (1 connections) — `backend/airfoils/naca.py`
- **A source that could NOT be normalized. Carries a human-readable reason     — the** (1 connections) — `backend/airfoils/types.py`
- **Ingest every .dat in the snapshot. Returns (normalized, quarantined) —     their** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **P1 gate — plan.md §9 pass criteria:    100% of vendored UIUC files normalize OR** (1 connections) — `tests/gates/test_p01_airfoils.py`
- **test_normalized_foils_meet_te_thickness()** (1 connections) — `tests/gates/test_p01_airfoils.py`

## Relationships

- [UIUC Airfoil Ingestion](UIUC_Airfoil_Ingestion.md) (11 shared connections)
- [NACA 4/5-Digit Generators](NACA_4-5-Digit_Generators.md) (8 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (5 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (4 shared connections)
- [OCP Loft R0 Probe](OCP_Loft_R0_Probe.md) (2 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (2 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (1 shared connections)

## Source Files

- `backend/airfoils/metrics.py`
- `backend/airfoils/naca.py`
- `backend/airfoils/types.py`
- `backend/airfoils/uiuc_ingest.py`
- `tests/gates/test_p01_airfoils.py`

## Audit Trail

- EXTRACTED: 81 (95%)
- INFERRED: 4 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*