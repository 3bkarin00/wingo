# Gate Changes

Audit log of any modification to an existing gate's test or pass criteria
after it was first written. A gate is a contract; changing one after the
fact needs a paper trail. Format:

```
## pXX — <date>
- What changed: ...
- Why: ...
- Re-verified against: golden configs / regress
```

## p03 — 2026-07-08
- What changed: `test_forced_rib_planes_at_device_edges`
  (tests/gates/test_p03_reference.py) had its `config.le_droop` branch
  removed — it would otherwise `AttributeError` once `le_droop` left the
  schema.
- Why: LE droop dropped from scope entirely (ADR-004), a product decision
  made before P5 started, not a construction/gate problem. The test's pass
  criteria are unchanged in substance (forced rib planes at every *enabled*
  device's window edges); there is just one fewer device type that can be
  enabled. `tests/configs/edge/devices_full.yaml` and `devices_twisted.yaml`
  (both parametrize this test) had their `le_droop` blocks removed too, so
  every case this test runs against still has a real `te_surface` device to
  check.
- Re-verified against: `make gate PHASE=p03` on wingo.coder (golden + edge
  configs, all green) and `make regress` (p00-p04) after the schema/
  validator/reference.py changes.

