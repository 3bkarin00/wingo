---
title: UIUC airfoil .dat auto-detection — Selig vs Lednicer, the real threshold and its edge case
tags: [airfoils, parsing, uiuc, f11, p01]
source: "docs/r0_findings/p01.md (hand-analyzed 8 real UIUC files)"
phase: p01
confidence: verified
last_updated: 2026-07-19
---

No library parses UIUC `.dat` — F11 (Selig/Lednicer confusion) means
understanding the real files by hand first (P1's own R0 scope), not
guessing a heuristic.

- **Selig**: single continuous loop, TE→upper→LE→lower→TE (already this
  project's canonical order — parse as-is). First coordinate line IS the
  trailing edge, `x ≈ 1.0`.
- **Lednicer**: two blocks (upper, lower), each LE→TE, preceded by a counts
  line (`n_upper n_lower`, as floats with a trailing dot: `"17. 17."`).
  Convert to canonical: `reverse(upper)` (→ TE→LE) then append `lower[1:]`
  (drop the duplicated LE point).
- **Detection**: line 1 is always a name/header (may contain spaces/`|` —
  never parse as coordinates). Find the first line that parses as two
  floats `(a, b)`. **If `a > 1.5` → Lednicer** (`a` is a point count);
  else → Selig (`a` is the TE x-coordinate).
- **The threshold's edge case**: a naive threshold at `1.0` misreads a
  Selig file as Lednicer, because published Selig data can round the TE
  x-coordinate marginally OVER 1.0 — `naca23012.dat` begins at
  `x = 1.00003`. That misreads as Lednicer count "1" and crashes on an
  empty lower block. Confirmed on all 30 vendored files that the gap is
  wide (Selig first-x ≤ 1.00003; Lednicer counts ≥ 17) — `1.5` sits safely
  in the empty middle.
- **Real-world messiness to quarantine, not silently drop** (gate requires
  0 silent failures): CRLF line endings, leading-dot numbers (`-.0121500`
  — Python `float()` handles fine), blank lines between/around blocks,
  trailing-dot counts. Quarantine with a reason string when a line can't
  parse, block lengths don't match declared counts, point count is
  implausibly low, or the loop isn't closed/normalizable.
