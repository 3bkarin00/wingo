---
title: "handoff.md/state.json must describe only already-true states — verify against git log before trusting a claim"
tags: [process, handoff, incident, git]
source: "docs/decisions/ADR-005-pin-and-tube-hinges.md (incident recorded there)"
phase: p07
confidence: verified
last_updated: 2026-07-19
---

Real incident (found while investigating the P7→pin-and-tube pivot,
ADR-005): `handoff.md` claimed "every P7 commit pushed to origin," but P7's
work was actually gate-verified while still sitting as UNCOMMITTED/
untracked changes on `phase/p07` — the claim was simply false, and nobody
had checked `git log`/`git status` against the memory file's own prose
before relying on it.

Rule this implies: `handoff.md` and `artifacts/state.json` are working
memory a future session (or agent) trusts BY DEFAULT — a false claim there
doesn't just waste time, it can lead to acting on a wrong premise (e.g.
assuming work is safely on `origin` when it isn't, before a destructive
operation). Before writing a state claim into either file ("committed",
"pushed", "gate passes", "N gates in gates_passed"), verify it against the
actual source of truth (`git log`, `git status`, the real
`artifacts/gates/pXX.json` content) rather than writing what SHOULD be true
or what was true a few steps ago. `artifacts/state.json` is machine-
readable STATE (conftest.py writes it only on a real green
`pytest_sessionfinish`); `handoff.md` is human-readable INTENT — never
parse prose for state, and never let prose assert a state fact the
machine-readable file could instead confirm.
