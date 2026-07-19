# Knowledge Base (Stage 1: file-based)

One concept per file, kebab-case filename, frontmatter + short body:

```
---
title: <one line>
tags: [occ, boolean, ...]
source: <where this was learned: phase, R0 probe, incident, external doc>
phase: <phase where learned, e.g. p04>
confidence: verified | probable | hypothesis
last_updated: YYYY-MM-DD
---
<body: the rule/lesson/spec itself. SHORT — a card, not an essay.>
```

`confidence` meanings:
- **verified** — confirmed against the real kernel/tool on a real file, or
  passed a real gate.
- **probable** — established by construction/design and partially checked
  (e.g. an R0 probe, not yet a full phase gate), or a design rule the team
  has committed to but hasn't stress-tested widely.
- **hypothesis** — a stated intent (plan.md, an ADR) for a phase not yet
  built; no real-kernel evidence exists yet.

## Index

`make kb-index` regenerates `INDEX.md` (filename/title/tags/confidence, one
line per entry) from the frontmatter of every file here. `INDEX.md` is
generated — don't hand-edit it.

## Search

`make kb-search Q="term"` — greps title/tags/body across every entry
(case-insensitive) and prints the matching files with the matching lines.
Stage 1 only: no embeddings, no ranking, just grep. If the KB grows past
what grep-and-skim can handle, Stage 2 is a pgvector-backed semantic search
over entry bodies (embed on write, cosine-search on read) — **not built
yet**, tracked here as the acknowledged next step, not attempted in this
scaffold.

## Workflow (see CLAUDE.md §0.1 for the authoritative version)

- **Before** touching an unfamiliar area or fighting a library: `make
  kb-search Q="<topic>"` first.
- **At resolution** of anything non-obvious (failed approach, API surprise,
  design rule decided): write or update the entry **in the same commit** as
  the fix. A fight resolved without a KB entry is an incomplete fix.
- R0 probes: the probe script stays as raw evidence
  (`scripts/r0_probes/probe_*.py`, `docs/r0_findings/pXX.md`); the KB entry
  is the DISTILLED lesson a future session should read instead of re-running
  the probe.

## Provenance

Seeded 2026-07-19 by migrating `docs/known_issues.md` (now a pointer file,
tag `incident`) and mining `docs/r0_findings/`, `docs/decisions/`,
`docs/gate_changes.md`, and commit history for durable lessons not
otherwise captured anywhere a future session would think to look.
