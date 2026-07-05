# ADR-001 — Bolted spar retention replaces over-center toggle latch

**Status**: Accepted (folded into plan.md v0.4, baseline for P0 kickoff).

## Context

The original segment-joint design (pre-v0.4) retained the outer wing panels
with an over-center toggle latch mechanism. Toggle latches are a moving,
spring-loaded mechanism generated as part of the wing geometry — a
significant mechanism-generation risk (kinematic clearances, wear,
manufacturability of the toggle itself) on top of the already-hard segment
joint problem (D8).

## Decision

Replace the toggle latch with bolted spar retention (D8, D10): both spars
carry male tongues (rect hollow or circular tube) into female boxes housed
in separate bonded aluminum blocks per spar. Retention is 1 vertical Z-bolt
per housing (2 per break), countersunk, seating on an aluminum lip. The
preload path is aluminum-only and never crosses composite; tongue holes are
clearance fits, so the bolt acts purely as a shear pin against spanwise
withdrawal, not as the primary joint-closing mechanism.

## Consequences

- Retired: the entire toggle-latch failure-mode surface (kinematic mechanism
  geometry, spring/wear behavior, latch-specific gate).
- Added: F17–F19 (flat lip curvature mismatch, bolt preload crushing a
  hollow composite tongue, non-parallel tongues blocking insertion) and the
  P11 insertion-sweep gate / P18 preload-path-continuity gate that catch
  them.
- D8/D10 in plan.md §2 and the P11/P18 gate definitions in §9 are the
  authoritative spec for this decision; this ADR exists so the *why* survives
  independent of plan.md being rewritten in a future pivot.
