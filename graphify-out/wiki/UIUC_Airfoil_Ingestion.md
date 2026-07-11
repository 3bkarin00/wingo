# UIUC Airfoil Ingestion

> 14 nodes · cohesion 0.25

## Key Concepts

- **uiuc_ingest.py** (18 connections) — `backend/airfoils/uiuc_ingest.py`
- **ingest_dat_file()** (12 connections) — `backend/airfoils/uiuc_ingest.py`
- **detect_format_and_coords()** (10 connections) — `backend/airfoils/uiuc_ingest.py`
- **_ParseError** (10 connections) — `backend/airfoils/uiuc_ingest.py`
- **_normalize_unit_chord()** (7 connections) — `backend/airfoils/uiuc_ingest.py`
- **_parse_pair()** (5 connections) — `backend/airfoils/uiuc_ingest.py`
- **_collect_pairs()** (3 connections) — `backend/airfoils/uiuc_ingest.py`
- **ndarray** (2 connections)
- **UIUC .dat ingest: format auto-detect (Selig/Lednicer), normalize to canonical or** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **Internal: signals a quarantine with a reason (not a crash).** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **Parse a line as an (x, y) float pair. Returns None for blank lines;     raises _** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **Return (format, canonical-order raw points). Line 0 is always the     name/heade** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **Translate LE to x=0 and scale to unit chord, preserving aspect ratio.** (1 connections) — `backend/airfoils/uiuc_ingest.py`
- **Exception** (1 connections)

## Relationships

- [Airfoil Metrics & NACA Generation](Airfoil_Metrics_%26_NACA_Generation.md) (11 shared connections)
- [NACA 4/5-Digit Generators](NACA_4-5-Digit_Generators.md) (6 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (5 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (4 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (1 shared connections)

## Source Files

- `backend/airfoils/uiuc_ingest.py`

## Audit Trail

- EXTRACTED: 70 (96%)
- INFERRED: 3 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*