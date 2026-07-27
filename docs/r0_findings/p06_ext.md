## probe_sweep_spine.py
- **PROBE FAILED**: AttributeError: type object 'Wire' has no attribute 'makeSpline'
```
Traceback (most recent call last):
  File "/home/coder/wingo/scripts/r0_probes/probe_sweep_spine.py", line 57, in main
    spine_wire = cq.Wire.makeSpline(spine_vecs)
                 ^^^^^^^^^^^^^^^^^^
AttributeError: type object 'Wire' has no attribute 'makeSpline'. Did you mean: 'makeEllipse'?
```

## probe_sweep_spine.py
- spine: 12-point spline, Length()=312.91mm (chord-to-chord straight distance=300.17mm)
- Technique A `Workplane(profile).sweep(pathWorkplane)`: SUCCEEDED, valid=True, volume=7507.43mm^3 (analytic profile_area*spine_len=7509.89mm^3)
- Technique B `makeLoft([30 sampled-frame rects], ruled=True)`: SUCCEEDED, valid=True, volume=7505.35mm^3 (analytic profile_area*spine_len=7509.89mm^3)
- Technique B end-cap face areas found near profile_area=24.0: [33.72, 33.52, 33.7, 33.1, 33.48, 32.49, 33.13, 31.77, 32.74, 31.05, 32.4, 30.44, 32.18, 30.06, 32.13, 29.98, 32.27, 30.22, 32.56, 30.72, 32.93, 31.4, 33.31, 32.14, 33.61, 32.81, 33.74, 33.34, 33.65, 33.65, 33.34, 33.74, 32.81, 33.61, 32.14, 33.31, 31.4, 32.93, 30.72, 32.56, 30.22, 32.27, 29.98, 32.13, 30.06, 32.18, 30.44, 32.4, 31.05, 32.74, 31.77, 33.13, 32.49, 33.48, 33.1, 33.7, 33.52, 33.72, 24.0, 24.0]
- CONCLUSION: Technique A (direct sweep) also works — re-verify on the REAL P3 ruled-surface cap-path curve before picking it over B, since this probe's spine is a synthetic spline, not the true intersection curve

## probe_offset_curve_surface.py
- toy surface: cylindrical patch, radius=150.0mm, length=400mm
- skin-contact curve: 15-point spline ON the cylinder surface (by construction, at exactly radius=150.0mm), Length()=435.69mm
- `OCP.BRepOffsetAPI.BRepOffsetAPI_MakeOffsetOnSurf` NOT AVAILABLE: AttributeError: module 'OCP.BRepOffsetAPI' has no attribute 'BRepOffsetAPI_MakeOffsetOnSurf'
- `OCP.BRepOffsetAPI.BRepOffsetAPI_NormalProjection` EXISTS in the installed OCP (class importable; signature/usage not yet exercised here)
- Technique B (manual normal-offset + refit spline): offset_wire valid=True, closed=False, Length()=436.59mm
- Technique B ACCURACY: offset points' radial distance from cylinder axis, expected=148.000mm, max deviation across 15 points=4.00000mm (FAIL — investigate before using this technique)
- CONCLUSION: Native on-surface offset API available (BRepOffsetAPI_NormalProjection) — probe its exact signature next.

## probe_offset_curve_surface.py
- toy surface: cylindrical patch, radius=150.0mm, length=400mm
- skin-contact curve: 15-point spline ON the cylinder surface (by construction, at exactly radius=150.0mm), Length()=435.69mm
- `OCP.BRepOffsetAPI.BRepOffsetAPI_MakeOffsetOnSurf` NOT AVAILABLE: AttributeError: module 'OCP.BRepOffsetAPI' has no attribute 'BRepOffsetAPI_MakeOffsetOnSurf'
- `OCP.BRepOffsetAPI.BRepOffsetAPI_NormalProjection` EXISTS in the installed OCP (class importable; signature/usage not yet exercised here)
- Technique B (manual normal-offset + refit spline): offset_wire valid=True, closed=False, Length()=434.80mm
- Technique B ACCURACY: offset points' radial distance from cylinder axis, expected=148.000mm, max deviation across 15 points=0.00000mm (PASS — sub-micron, offset correctly followed local curvature)
- CONCLUSION: Native on-surface offset API available (BRepOffsetAPI_NormalProjection) — probe its exact signature next.

## probe_xde_face_naming.py
- toy body: 10x10x10 box, naming face[0] as 'TEST_TAB_BOND_FACE' via AddSubShape
- `AddSubShape(top_label, face)` -> label created
- `STEPCAFControl_Writer().Write(path)` status=IFSelect_ReturnStatus.IFSelect_RetVoid
- CONCLUSION: STEP write failed outright — cannot test round-trip; investigate the writer signature interactively before relying on this path for the centroid registry's STEP export.

## probe_xde_face_naming.py
- toy body: 10x10x10 box, naming face[0] as 'TEST_TAB_BOND_FACE' via AddSubShape
- `AddSubShape(top_label, face)` -> label created
- `STEPCAFControl_Writer().Perform(doc, path)` -> True
- re-imported STEP: names found (top-level + sub-shape, recursive)=['<OCP.OCP.TCollection.TCollection_ExtendedString object at 0x7f9239b746b0>']
- CONCLUSION: face-level sub-shape name DID NOT survive — AddSubShape + TDataStd_Name is not sufficient in this OCP build; needs a different technique before WP1/WP2b/WP2c centroid-registry naming code is written, do not assume it works

## probe_xde_face_naming.py
- toy body: 10x10x10 box, naming face[0] as 'TEST_TAB_BOND_FACE' via AddSubShape
- `AddSubShape(top_label, face)` -> label created
- `STEPCAFControl_Writer().Perform(doc, path)` -> True
- re-imported STEP: names found (top-level + sub-shape, recursive)=['TEST_BODY']
- CONCLUSION: face-level sub-shape name DID NOT survive — AddSubShape + TDataStd_Name is not sufficient in this OCP build; needs a different technique before WP1/WP2b/WP2c centroid-registry naming code is written, do not assume it works

### Correction — the two "DID NOT survive" entries above are SUPERSEDED

The first negative entry was invalid: its verification code converted the
recovered `TCollection_ExtendedString` with plain `str()`, which yields the
pybind object repr, not the text — so it proved nothing either way. The
second run (with the conversion fixed via
`TCollection_AsciiString(x).ToCString()`) showed the top-level name survives
but the face name doesn't **under default writer settings** — grepping the
written STEP file showed the face name never left the writer. Root cause:
sub-shape names are gated behind `write.stepcaf.subshapes.name` /
`read.stepcaf.subshapes.name` (both default 0). Extra trap: those
Interface_Static params only REGISTER after the first STEPCAF
writer/reader is constructed — `SetIVal_s` on them before that returns
False and silently does nothing. The run below is the authoritative one.

## probe_xde_face_naming.py
- toy body: 10x10x10 box, naming face[0] as 'TEST_TAB_BOND_FACE' via AddSubShape
- `AddSubShape(top_label, face)` -> label created
- `write.stepcaf.subshapes.name=1` (set AFTER writer init — lazy param registration) -> True
- `STEPCAFControl_Writer().Perform(doc, path)` -> True
- `read.stepcaf.subshapes.name=1` -> True
- re-imported STEP: names found (top-level + sub-shape, recursive)=['TEST_BODY', 'TEST_TAB_BOND_FACE']
- CONCLUSION: face-level sub-shape name SURVIVED the STEP XDE round-trip. Full working recipe: AddSubShape + TDataStd_Name, PLUS write.stepcaf.subshapes.name=1 (set after writer init) on write AND read.stepcaf.subshapes.name=1 on read — both flags default OFF, and without the write flag the name never even reaches the STEP file. Names read back via TCollection_AsciiString(name.Get()).ToCString(), never plain str(). This is the technique the WP1/WP2b/WP2c centroid-registry STEP export must use.

## probe_spar_shapes_verify.py (WP2/D23)
- stand-in cavity: half-span OML of minimal.yaml, vol=5230460mm^3
- web: solids=1 shards=0 watertight=True vol=11905mm^3, build=2.3s -> PASS
  - footprint wires closed at 3 stations: True
  - 5 ribs built (25.2s), max rib∩spar volume=0.0000mm^3 -> PASS (cutouts clear the spar)
- c_channel: solids=1 shards=0 watertight=True vol=40966mm^3, exceeds web volume (11905): True, build=13.9s -> PASS
  - footprint wires closed at 3 stations: True
  - 5 ribs built (26.1s), max rib∩spar volume=0.0000mm^3 -> PASS (cutouts clear the spar)
- i_beam: solids=1 shards=0 watertight=True vol=40915mm^3, exceeds web volume (11905): True, build=13.5s -> PASS
  - footprint wires closed at 3 stations: True
  - 5 ribs built (26.4s), max rib∩spar volume=0.0000mm^3 -> PASS (cutouts clear the spar)
- box: solids=1 shards=0 watertight=True vol=33536mm^3, exceeds web volume (11905): True, build=20.5s -> PASS
  - footprint wires closed at 3 stations: True
  - 5 ribs built (26.7s), max rib∩spar volume=0.0000mm^3 -> PASS (cutouts clear the spar)
- tube: solids=1 shards=0 watertight=True vol=38842mm^3, build=1.5s -> PASS
  - footprint wires closed at 3 stations: True
  - 5 ribs built (25.2s), max rib∩spar volume=0.0000mm^3 -> PASS (cutouts clear the spar)
- tube oversize validation: rejected with actionable message: True
- CONCLUSION: ALL SHAPE PATHS PASS against the real kernel (stand-in cavity) — ready for the real-cavity gate run.

## probe_interlock_verify.py (WP2c/D25)
- **PROBE FAILED**: ValueError: interlock: crossing rib_y=500.0mm × spar 'rear': 2 tab(s) of 6.0mm + 2×3.0mm edge margin = 18.0mm exceeds the usable web height 16.0mm. Reduce tabs_per_crossing/tab_width_mm/edge_margin_mm, or disable interlock for this rib via ribs.overrides.
```
Traceback (most recent call last):
  File "/home/coder/wingo/scripts/r0_probes/probe_interlock_verify.py", line 82, in main
    ribs_on = build_ribs(cfg_on, cavity, planes)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/coder/wingo/backend/geometry/ribs.py", line 246, in build_ribs
    rib_shape = _spar_cutouts(config, rib_shape, y, thickness_mm, normal, rib_index)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/coder/wingo/backend/geometry/ribs.py", line 198, in _spar_cutouts
    tool = rib_cut_tool(
           ^^^^^^^^^^^^^
  File "/home/coder/wingo/backend/geometry/interlock.py", line 120, in rib_cut_tool
    for band in tab_bands(config, fp):
                ^^^^^^^^^^^^^^^^^^^^^
  File "/home/coder/wingo/backend/geometry/interlock.py", line 82, in tab_bands
    raise ValueError(
ValueError: interlock: crossing rib_y=500.0mm × spar 'rear': 2 tab(s) of 6.0mm + 2×3.0mm edge margin = 18.0mm exceeds the usable web height 16.0mm. Reduce tabs_per_crossing/tab_width_mm/edge_margin_mm, or disable interlock for this rib via ribs.overrides.
```

## probe_interlock_verify.py (WP2c/D25)
- ribs off/on interlock built in 49.9s
- every interlocked rib keeps tab material (vol > plain-cutout rib): True; all watertight: True
- slots cut in 1.1s: spar volume 11905 -> 11897mm^3 (10 slots expected): True
- max interlocked-rib ∩ slotted-spar volume=0.0000mm^3 (must be 0)
- box spar untouched by interlock: ribs identical=True, spar identical=True
- override(index=2, off): that rib plain=True, others interlocked=True
- oversized tab battery rejected actionably: True
- CONCLUSION: D25 tab-and-slot interlock PASSES on the real kernel (stand-in cavity).


## test_p06_ext_interlock.py gate development — 3 real construction findings on te_half.yaml's real sandwich cavity

The WP2c/D25 smoke probe above (probe_interlock_verify.py) verified interlock
against a stand-in OML cavity on minimal.yaml. Writing the real P6-extension
gate against te_half.yaml's TRUE sandwich cavity (hollow_interior, with its
device-cut cove/nose complexity) surfaced three additional real findings the
stand-in cavity couldn't have shown:

1. **Lightening hole can fragment a tab's bond wall.** The lightening-hole
   cut runs BEFORE the spar/tab cutout and doesn't know about interlock tabs;
   its offset2D boundary can slice straight through the gap between two
   adjacent tabs, splitting the tab's HI/LO bond face into several small
   irregular pieces instead of one clean rectangle. Fixed:
   `interlock.crossing_protect_wire` + `ribs._lightening_hole_cut` now
   subtracts every interlocked crossing's tab-band region (+ small pad) from
   the lightening-hole CUTTING TOOL (not the slab) before cutting — zero
   effect on non-interlocked crossings.

2. **Root/tip-adjacent ribs can't have a CAPTURED slot.** D25 assumes spar
   material on both sides of the slot; every spar in this project spans the
   full root-to-tip Y range, so a rib within one slot half-extent of Y=0 or
   Y=half_span has no material past its near end cap. `interlock_active` now
   requires `y_half <= y_mm <= half_span_mm - y_half` (falls back to the
   plain D23 cutout, same posture as box/tube).

3. **A spar crossing near the device window's hinge/cove region can't form a
   clean tab wall either.** te_half.yaml's rear spar (xc=0.70) sits close to
   hinge_xc=0.75; a rib crossing there is shaped by the cove/nose cut's
   curved boundary rather than a simple flat airfoil skin, and the tab's
   expected flat wall fragments into many small curved facets (confirmed:
   identical fragmentation with the lightening hole DISABLED entirely, and
   reproducible using only `te.wing`'s true P4 boundary once the true
   sandwich cavity was used — NOT reproducible on the simpler te.wing-as-
   cavity stand-in, confirming it's specific to the sandwich cavity's cove
   geometry near the hinge). `interlock_active` now also excludes any
   crossing whose rib_y falls within `[span_start_frac, span_end_frac] *
   half_span_mm` (the te_surface device window) — conservative (excludes
   BOTH spars there, even though only the hinge-adjacent one was actually
   affected), same precedent as test_iml_min_wall_audit's own device-window
   vertex exclusion. Precisely handling cove-adjacent tab/slot geometry is
   follow-on work, not a P6-extension blocker.

Also found and fixed during gate-writing (test-code bugs, not construction
bugs): `structure.interlock.enabled` is a GLOBAL toggle with no per-spar
switch, so BOTH web-bearing spars on a config get interlocked together, not
just one — a gate comparison that assumed only one spar's tabs undercounted
expected face totals. `build_ribs` SKIPS rib planes with no section (found:
te_half.yaml's y=660 plane), so `RibSet.ribs`'s list POSITION is not the
same as the plane's INDEX once any plane is skipped — gate code must map by
`rib.y_mm`, not index directly into `.ribs[i]`.

CONCLUSION: with these three construction fixes (findings 1-3) and the
gate's own bug fixes, `tests/gates/test_p06_ext_interlock.py`'s full fast
tier (9/9) passes on te_half.yaml's real sandwich cavity.
