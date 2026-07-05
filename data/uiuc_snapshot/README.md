# UIUC airfoil snapshot

Vendored `.dat` files from the UIUC Airfoil Coordinate Database
(`https://m-selig.ae.illinois.edu/ads/coord/<name>.dat`), ingested to
Postgres by the P1 airfoil subsystem (plan.md §8.1, §9 P1).

**Snapshot scope (P1):** a curated ~29-airfoil set, deliberately spanning
both coordinate formats and a range of point counts / TE bluntness — not the
full ~1600-file database (which would bloat the repo). Expand later if a
phase needs broader coverage. Format mix as classified by the ingest
detector (see docs/r0_findings/p01.md): 17 Selig, 12 Lednicer.

`_quarantine_me.dat` is an intentionally malformed fixture (a non-numeric
line mid-coordinates) that MUST land in quarantine with a reason string —
it proves the "0 silent failures" property the P1 gate requires, so the
quarantine path is exercised on every gate run. Do not delete it.
