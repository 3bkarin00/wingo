# ADR-004 — Drop LE droop from scope

**Status**: Accepted (post-P4, pre-P5 kickoff).

## Context

D3 originally locked "one TE hinged surface + one LE hinged droop per
half-span; slats deferred" (plan.md §2). P0–P4 built the schema field
(`le_droop`, sharing `DeviceWindow` with `te_surface`), the P0 cross-field
validation rules (window non-overlap vs. `te_surface`, segment containment,
hinge-vs-main-spar clearance), and P3's hinge-axis derivation/containment
gate already covered `le_droop` generically (`ref.hinge_axes` is a dict
keyed by device name, iterated without a TE/LE special case). P5 ("LE droop
cut") was about to apply P4's derived-axis/single-arc construction
(ADR-002, ADR-003) to the LE hinge — ADR-003 explicitly anticipated this
("P5 reuses this identical construction... `DeviceWindow` already covers
`le_droop` too").

Before starting P5, the product decision was made to drop the LE droop
device entirely — the vehicle ships with a TE control surface only, no LE
device. This is a scope reduction, not a technical finding (no construction
problem was hit; the mirrored-`a`-direction approach sketched for P5 would
have worked).

## Decision

Remove `le_droop` from the schema and every code path that branched on it,
rather than leaving a disabled/dead field:

- `backend/schema/models.py`: `Config.le_droop` field removed.
- `backend/schema/validators.py`: `_enabled_devices` now only ever returns
  `te_surface`. `validate_device_windows`'s TE-vs-LE span overlap check is
  removed (vacuous with one device type) — segment-containment stays (it
  still applies to `te_surface`). `validate_hinge_vs_spar`'s LE branch
  removed.
- `backend/schema/errors.py`: `LE_HINGE_TOO_FAR_AFT` and
  `DEVICE_WINDOW_OVERLAP` removed (both now unreachable — the latter had no
  other trigger since devices were never a list).
- `backend/geometry/reference.py`: `build_hinge_axes`'s LE branch and
  `build_rib_planes`'s LE forced-rib-plane addition removed. `ref.hinge_axes`
  stays a dict (now only ever containing `"te"`) rather than collapsing to a
  single value, so P3's gate test needed no structural change beyond
  dropping the LE expected-rib-plane check.
- Test fixtures: `tests/configs/invalid/le_hinge_too_far_aft.yaml` and
  `device_window_overlap.yaml` deleted (the rules they exercised no longer
  exist). `device_not_segment_contained.yaml` rewritten to straddle a
  segment break with `te_surface` instead of `le_droop` — the segment-
  containment rule itself is unchanged and still needs coverage.
  `tests/configs/valid/full_example.yaml` and the two `tests/configs/edge/
  devices_*.yaml` files had their `le_droop` blocks removed, keeping
  `te_surface`.
- `tests/gates/test_p03_reference.py` (frozen P3 gate): the
  `config.le_droop` branch in `test_forced_rib_planes_at_device_edges`
  removed — logged in `docs/gate_changes.md` per the "never edit a gate
  silently" rule, even though the gate's pass criteria (forced rib planes
  at every *enabled* device's edges) are unchanged in substance.

## Consequences

- Phase sequence: P5 ("LE droop cut") is retired — no phase does this work.
  P0–P4 keep their numbers and frozen gate artifacts unchanged. P6 onward
  keep their original numbers (no renumbering) per explicit decision: the
  gap at P5 costs nothing (gate filenames/artifacts are per-phase, not
  sequential-index-dependent) and renumbering would touch every P6+
  cross-reference in plan.md for zero functional benefit.
- P8 ("Kinematic gate") pass criteria updated to sweep TE only (the "and
  droop" language removed).
- `docs/conventions.md` §Signs drops the LE droop sign-convention line
  (TE's "trailing-edge-down positive" stays).
- Historical documents are NOT rewritten: ADR-002, ADR-003, and
  `docs/r0_findings/p04.md` still mention LE droop / P5 in their original
  context (what was true and anticipated at the time). This ADR is the
  authoritative pointer for "why LE droop no longer exists" going forward.
- `DeviceWindow` (the schema model) is unchanged and still used by
  `te_surface` alone — not deleted, since it's not TE-specific in itself.
