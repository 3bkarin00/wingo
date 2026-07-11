# ADR-003 Hinge Clearance Validation

> 19 nodes · cohesion 0.16

## Key Concepts

- **tools/viewer/README.md** (9 connections) — `tools/viewer/README.md`
- **tests/configs/devices/te_half_twisted.yaml (ADR-003 negative test)** (7 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **tools/viewer/index_template.html** (7 connections) — `tools/viewer/index_template.html`
- **tests/configs/devices/te_half_twisted_moderate.yaml (passing twisted-hinge stress case)** (5 connections) — `tests/configs/devices/te_half_twisted_moderate.yaml`
- **ADR-003: TE hinge clearance & nose-tangency fail-fast validation** (3 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **docs/r0_findings/p04.md** (3 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **tests/configs/devices/te_half.yaml** (3 connections) — `tests/configs/devices/te_half.yaml`
- **artifacts/gates/p04.json (gate-verified metrics)** (2 connections) — `tools/viewer/index_template.html`
- **artifacts/viewer_data.json** (2 connections) — `tools/viewer/README.md`
- **P4 "must successfully build" gate battery** (2 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **P10: real product UI (React + three.js against live API)** (2 connections) — `tools/viewer/README.md`
- **three.js (vendored, fetched once from jsdelivr)** (2 connections) — `tools/viewer/README.md`
- **tools/viewer/app.js** (2 connections) — `tools/viewer/README.md`
- **NOSE_TANGENCY_EXCEEDS_MAX error code** (1 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **HINGE_SPAR_XC_CLEARANCE_FRAC tolerance constant** (1 connections) — `tests/configs/devices/te_half_twisted.yaml`
- **NOSE_TANGENCY_MAX_DEG = 2.0deg tolerance** (1 connections) — `tests/configs/devices/te_half_twisted_moderate.yaml`
- **scripts/export_viewer_data.py** (1 connections) — `tools/viewer/README.md`
- **tools/viewer/build.py** (1 connections) — `tools/viewer/README.md`
- **tools/viewer/dist/viewer.html (generated, gitignored)** (1 connections) — `tools/viewer/README.md`

## Relationships

- [Invalid Config Error Codes](Invalid_Config_Error_Codes.md) (1 shared connections)

## Source Files

- `tests/configs/devices/te_half.yaml`
- `tests/configs/devices/te_half_twisted.yaml`
- `tests/configs/devices/te_half_twisted_moderate.yaml`
- `tools/viewer/README.md`
- `tools/viewer/index_template.html`

## Audit Trail

- EXTRACTED: 49 (89%)
- INFERRED: 6 (11%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*