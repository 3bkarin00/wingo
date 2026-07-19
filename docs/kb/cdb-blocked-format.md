---
title: ".cdb has no OSS writer/reader — hand-write NBLOCK/EBLOCK/CMBLOCK/SECTYPE, verify with a spec-derived independent oracle"
tags: [ansys, cdb, export, f8, f12, not-yet-built]
source: "plan.md §8 pipeline step 10, §2 D14/D15, §10 F8/F12"
phase: p13
confidence: hypothesis
last_updated: 2026-07-19
---

`confidence: hypothesis` — this is a stated design intent for a phase (P13)
not yet reached in this repo; no construction or gate exists yet to verify
it against. Recorded now so the intent doesn't have to be re-derived from
plan.md when P13 starts.

No open-source tool writes Ansys `.cdb` — plan.md's own note: "`.cdb` via
custom NBLOCK/EBLOCK/SECTYPE writer (no OSS tool writes .cdb)". Two
registered failure modes specifically about this:
- **F8**: unit mismatch (mm vs m) in a `.cdb` deck is a 10^9 error in
  practice (wrong units compound through every downstream FEA quantity) —
  mitigation is asserting the `mm–tonne–s` header block is actually present
  and correct, not assuming the writer got it right.
- **F12**: since there's no reference implementation to diff against, a
  hand-rolled `.cdb` writer can silently drift from the Ansys block-format
  spec over time with nothing to catch it. Mitigation: a SPEC-DERIVED
  INDEPENDENT ORACLE PARSER (P13's own gate) — written from the Ansys
  format spec directly, not from reading this project's own writer code,
  so the two can't share a misunderstanding. Composites route through
  Mechanical layered shell sections (D15) with the layup schedule exported
  as separate CSV+JSON, not embedded in the `.cdb` itself.

When P13 starts: R0-probe the actual NBLOCK/EBLOCK/CMBLOCK/SECTYPE syntax
against the real spec before writing the writer, same discipline as every
other third-party boundary in this project.
