"""Every numeric tolerance in WingStructGen, in one place (plan.md §0.5).

A tolerance literal anywhere else in the codebase is a review-blocking
offense — import from here instead. Each constant carries its derivation so
a future phase can judge whether it's still appropriate rather than treating
it as received wisdom.
"""

# --- Kernel / tessellation --------------------------------------------------

# Working OCC boolean-fuzzy-value assumption for P0's schema-level gap_mm
# check. OCC's own default geometric tolerance (Precision::Confusion) is
# 1e-4 mm; we budget 100x that as a conservative working value because
# compounded fuzzy booleans (device cuts, joints) accumulate error faster
# than a single operation. PROVISIONAL: re-derive this from the real R0
# boolean probe in P4 and update this comment when it is.
KERNEL_TOLERANCE_MM = 0.01

# Typical linear-deflection tessellation tolerance used for glTF/STL export
# and interference sampling. Matches common CAD-kernel tessellation defaults;
# revisit in P9 (export gate) against real glTF/STL fidelity requirements.
TESSELLATION_TOLERANCE_MM = 0.05

# --- Mechanical / geometric ---------------------------------------------

# Hinge pin / joint-pin coaxiality requirement (P7, P11, P18 gates). Chosen
# as a tight-but-machinable fit tolerance for 3D-printed or COTS hinge pins
# at this scale (per plan.md §0.5).
COAXIALITY_TOLERANCE_MM = 0.05

# Sandwich stack (core + 2x face sheet) must not exceed this fraction of the
# minimum local airfoil thickness at any station (§6 P0 validation rules,
# F15). 80% leaves a 20% margin for local thickness variation between
# sampled stations and manufacturing tolerance.
SANDWICH_MARGIN_FRACTION = 0.8

# Default flat-lip flushness tolerance for joint-housing lips against local
# OML curvature (D10, F17) — schema default for `joint_retention.housing.lip.flush_tol_mm`.
DEFAULT_LIP_FLUSH_TOL_MM = 0.1

# Minimum chordwise (xc) clearance between a device hinge line and the spar
# it must clear (TE hinge vs rear spar, LE hinge vs main spar — §6 P0
# validation rules). PROVISIONAL heuristic for the P0 schema-level check
# only; the real geometric containment/clearance check runs on actual OML in
# P3 (F5) and supersedes this.
HINGE_SPAR_XC_CLEARANCE_FRAC = 0.02

# --- Validation multipliers (P0 gap_mm rule, §6) ----------------------------

# gap_mm must be at least this many multiples of TESSELLATION_TOLERANCE_MM,
# so tessellated device-cut gaps don't collapse to zero width visually/in
# STL.
GAP_MIN_TESSELLATION_MULTIPLE = 2

# gap_mm must be at least this many multiples of KERNEL_TOLERANCE_MM, so the
# boolean cut that forms the gap doesn't fall inside kernel fuzz and produce
# a degenerate (zero-volume) gap body.
GAP_MIN_KERNEL_MULTIPLE = 10

# Provisional per-ply thickness lookup (mm), standing in for the D17
# materials DB (Postgres `materials` table) until it's seeded in P1+. Values
# are typical for the named fabric weight; update from the real DB once
# `make seed` populates it. Shared by the P0 sandwich-stack validator
# (backend/schema/validators.py) and the P3 hinge-axis-margin gate.
PLY_THICKNESS_MM_PROVISIONAL = {
    "cfrp_200gsm_twill": 0.20,
    "cfrp_200gsm_uni": 0.18,
    "gfrp_200gsm_twill": 0.22,
}

# --- P1 airfoil subsystem (thresholds + gate tolerances) --------------------

# A UIUC .dat with fewer than this many coordinate points is implausible as a
# real airfoil (the coarsest in the vendored snapshot is ~33) — quarantine
# rather than try to normalize garbage.
AIRFOIL_MIN_RAW_POINTS = 20

# P1 gate: cosine-resample round-trip max deviation from the analytic source
# curve, as a fraction of chord (plan.md §9 P1 pass criteria: < 1e-3 chord).
RESAMPLE_ROUNDTRIP_MAX_DEV_FRAC = 1.0e-3

# P1 gate: max point-to-curve deviation (fraction of chord) allowed between
# our NACA generator and the UIUC-published coordinates for the same airfoil.
# Measured geometric max across the 3 reference sections (naca2412/4412/23012)
# is 1.8e-4 (see tests/golden/expected/naca_reference.json); threshold set at
# 5e-4 → ~2.7x margin, tight enough to catch a real generator regression.
NACA_PUBLISHED_MATCH_MAX_DEV_FRAC = 5.0e-4

# --- Boolean / device-cut phases (P4+) --------------------------------------

# Any solid emerging from a boolean cut with volume below this many mm^3 is a
# micro-shard, not a real body — filter it out (F3). A real wing part (skin
# panel, control surface) is at least ~10^4 mm^3; a boolean shard is typically
# < 1 mm^3. 1.0 mm^3 sits far below any legitimate body and far above kernel
# noise. Re-evaluate if a future phase produces intentionally tiny features.
SHARD_MIN_VOLUME_MM3 = 1.0

# Fuzzy value handed to BRepAlgoAPI boolean ops at the cove, where nose/cove
# cylinders run nearly parallel (F4 risk zone). OCC's default confusion is
# 1e-4 mm; 1e-3 mm gives the kernel a slightly larger merge tolerance to
# resolve near-coincident edges robustly without visibly moving geometry.
BOOLEAN_FUZZY_VALUE_MM = 1.0e-3

# P4 gate: volume-conservation band for the TE cut — vol(wing)+vol(CS)+vol(gap)
# must equal vol(P2 OML) to within this fraction (plan.md §9 P4: 0.5%). Our
# construction conserves volume exactly in principle; the band absorbs kernel
# fuzz from the boolean split.
DEVICE_CUT_VOLUME_CONSERVATION_FRAC = 0.005

# P4 tangency check (F4): two coaxial cylindrical faces whose radii differ by
# less than this are effectively tangent/coincident — an unstable-boolean
# hazard. 0.1 mm sits far above kernel noise and far below any real gap.
FACE_TANGENCY_TOLERANCE_MM = 0.1

# --- TE/LE cove-nose per-station arc construction (§8.5, refined twice —
# ADR-002 introduced the per-station axis-centered arc; ADR-003 replaced the
# two-arc/Hermite-blend branch with a single arc + a DERIVED hinge-axis
# height, after the two-arc blend's curvature discontinuity showed up as a
# visibly lumpy nose on any twisted config) -------------------------------
#
# Per-station 2D construction in planes ⟂ the hinge axis: the CS nose is ONE
# arc centered on the hinge-axis point C, at radius R=(Ru+Rl)/2 where Ru/Rl
# are the "normal foot" distances to the upper/lower OML skin (tangent to
# the skin there by construction — see docs/r0_findings/p04.md). The wing
# cove is a concentric arc at the same C, offset outward by a FIXED radial
# clearance — an exact, deflection-invariant offset regardless of deflection
# angle. See docs/decisions/ADR-002, ADR-003.

# Radial clearance between the CS nose arc and the wing cove arc, both
# centered on the hinge axis at each station. Fixed (not derived from
# gap_mm/skin thickness) so it holds exactly at every deflection angle by
# construction. 5 mm matches typical hinge-line clearance for this wing scale
# (chords ~200-450 mm) — large enough to never pinch on kernel fuzz, small
# enough to stay a minor fraction of local thickness at realistic hinge
# stations.
COVE_CLEARANCE_MM = 5.0

# Max allowed "mean-radius tangency error" at a station: with the two-arc
# branch deleted (ADR-003), the single nose arc uses R=(Ru+Rl)/2, which
# deviates from the TRUE per-side radius Ru/Rl by up to |Ru-Rl|/2. Expressed
# as an angle via arctan(|R-Ru|/Ru) (well-behaved near zero, unlike an
# arccos-based formulation which has an infinite derivative there and
# over-reports even a ~0.001mm mismatch as several tenths of a degree —
# measured directly, see docs/r0_findings/p04.md). Config-time validation
# (backend/geometry/te_cut.py) REJECTS a config whose worst station exceeds
# this rather than silently degrading the shape (ADR-003).
#
# Calibrated from real measurement, not the literal design-brief suggestion
# of 0.5°: at a realistic aft hinge_xc (~0.70-0.75, the only region a rear
# spar leaves valid), tangency error scales roughly linearly with twist at
# ~1.7deg per degree of tip twist (docs/r0_findings/p04.md) — 0.5° would
# reject nearly every wing with ANY nonzero twist at a realistic TE hinge
# position, not just pathological ones. 2.0° accommodates a real, measured
# 1° tip-twist config (1.70° residual, ~15% margin) while still rejecting
# the project's own extreme-twist edge case (te_half_twisted.yaml, -8° tip,
# ~16.75° residual) — the same value this replaces (NOSE_TANGENCY_ANGLE_TOL_DEG,
# retired) landed on for an unrelated reason (5x R0-probe discretization
# noise), a coincidence worth noting, not a reused derivation.
NOSE_TANGENCY_MAX_DEG = 2.0

# Anti-unporting angular overlap (design-practice addition, ADR-003): the
# nose arc must not stop at the tangent points Pu/Pl — it's extended beyond
# each by (max_deflection_deg + this margin) so the curved nose still
# overlaps the fixed wing's cove lips at full deflection and never rotates
# out of the cove ("unporting", exposing its edge to airflow). 4.0° sits in
# the middle of the 3-5° standard-practice range; no config-specific
# derivation applies here (unlike the tolerances above) since it's a fixed
# design margin, not fit to observed geometry.
OVERLAP_MARGIN_DEG = 4.0

# False-spar (device-cut closing wall, plan.md §8.5/§8.7) standoff between
# the wall's AFT face and the wing cove's forwardmost sweep (r_cove =
# StationFeet.R + COVE_CLEARANCE_MM at each station). Keeps the wall
# strictly clear of the cove cut surface so the wall ∩ cavity boolean never
# sees a tangent/coincident face pair (F4) and the wall never encroaches on
# the cove clearance band the CS nose sweeps through. 0.5 mm = 50x
# KERNEL_TOLERANCE_MM (comfortably above kernel fuzz) while staying a small
# fraction of the ~10-15 mm cove radii of realistic aft-hinge configs
# (hinge_xc 0.70-0.75, chords 190-420 mm).
FALSE_SPAR_COVE_STANDOFF_MM = 0.5

# Ramped core drop-off (D11, plan.md §8.7) floor: the per-station core_mm
# tapers toward zero within ramp_ratio*core_mm of the wingtip
# (backend/geometry/iml.py's _ramped_core_mm) but is floored here rather
# than let the offset distance hit exactly zero. 0.1mm = 10x
# KERNEL_TOLERANCE_MM. NOT an arbitrary "small number": a first attempt
# used 0.01mm (== KERNEL_TOLERANCE_MM exactly) and it broke real-kernel
# booleans on tests/configs/edge/high_taper.yaml — a razor-thin core layer
# right at the kernel's own precision floor made BRepAlgoAPI_Cut fail
# outright at the default fuzzy value and produce dozens of degenerate
# micro-fragments at larger ones (docs/r0_findings/p06.md). 0.1mm keeps a
# comfortable margin above kernel fuzz while staying negligible next to any
# config's real core.thickness_mm (0.5mm-3.0mm across current test configs).
RAMP_MIN_CORE_MM = 0.1

# Sampling-grid tolerance for the "cove clearance is exactly COVE_CLEARANCE_MM
# everywhere" gate check — absorbs per-station loft interpolation between
# sampled cross-sections, not just kernel fuzz. Matches FACE_TANGENCY_TOLERANCE_MM
# order of magnitude for consistency across P4's geometric checks.
COVE_CLEARANCE_TOL_MM = 0.15

# Small blend radius where the wing cove arc meets the OML skin, avoiding a
# zero-radius reentrant corner (resin-pooling/stress-concentration risk in a
# real composite mold — common minimum composite tooling corner radius).
COVE_LEAD_IN_FILLET_MM = 1.0

# The nose region's per-station profile closes with a chord roughly AT the
# hinge axis (local x≈0), while aft_box_cs starts gap_mm aft of it (the hinge
# axis is ⟂ to `a` by construction, so this offset is exact at every
# station) — with no overlap, `nose_region.fuse(aft_box_cs)` sees two
# non-touching solids and produces 2 disjoint bodies instead of 1. The nose
# polygon's closing edge is pushed aft by gap_mm + this margin so the two
# regions genuinely overlap before the union.
NOSE_AFT_OVERLAP_MM = 2.0

# --- Hinges, generated mode: PIN-AND-TUBE (P7, D26/ADR-005) -----------------
#
# Supersedes the retired lug/tang knuckle constants (the lug/tang R0 trail
# and its keyway/Minkowski-box findings remain in docs/r0_findings/p07.md
# as historical record). The R0 fact that still matters here: CS nose
# material reaches all the way to the true hinge-axis line (wing has zero
# material near it), so every wing-side hardware body needs a matched
# clearance notch in a DERIVED copy of cs_solid — never the frozen P4
# cs_solid itself.

# Generated hinge pin (wire) diameter — plan.md's `cots_pin_dia_mm` only
# applies to `mode: cots`. 2.0mm matches common small RC/UAV hinge-wire
# stock at this wing scale (chords ~200-450mm).
HINGE_PIN_DIA_MM = 2.0

# Tube bore (id) running clearance over the pin — sliding fit for a piano-
# hinge wire; the standard 0.1mm printed/reamed running allowance at Ø2.
HINGE_TUBE_ID_CLEARANCE_MM = 0.1

# Tube wall — 1.0mm suits both a printed bushing and off-the-shelf 4mm-OD
# brass/CF tube stock over a 2mm wire (OD = id + 2×wall ≈ 4.1mm).
HINGE_TUBE_WALL_MM = 1.0

# Axial length of one tube segment — ~6x pin diameter bearing length, the
# same bearing-length guideline the retired knuckle length used, slightly
# longer since a bonded tube (not a printed boss) carries the load.
HINGE_TUBE_SEGMENT_LEN_MM = 12.0

# Axial gap between the wing-side and CS-side tube mouths at one station —
# assembly/running clearance along the axis (unrelated to the chordwise
# device gap_mm; same reasoning as the retired knuckle axial gap).
HINGE_AXIAL_GAP_MM = 2.0

# Carrier block wall around its tube bore — the recipe's own ">= 3 mm wall".
HINGE_CARRIER_WALL_MM = 3.0

# Carrier bore over tube OD — bond fit (adhesive-filled annulus), one
# standard structural film thickness like PI_BOND_GAP_MM, applied on
# diameter: bore Ø = tube OD + this.
HINGE_CARRIER_BORE_FIT_MM = 0.2

# Explicit bond-line gap between a carrier's mating face and the structure
# it bonds to (wing carrier ↔ false-spar aft face; CS carrier ↔ CS
# material via its Minkowski-grown notch) — bonded, NEVER touching (F4-
# adjacent). Same adhesive-film value as PI_BOND_GAP_MM.
HINGE_CARRIER_BOND_GAP_MM = 0.2

# How deep the CS carrier embeds aft of its tube envelope into CS nose
# material — bond area comparable to the carrier's own cross-section
# (~10mm ≈ the carrier height at these tube sizes).
HINGE_CS_CARRIER_EMBED_MM = 10.0

# Swept-pocket construction (D26: union of rotated copies, never a single
# revolve): angular step between copies. 2° (the recipe's own value) gives
# a chordal sag of r·(1−cos1°) ≈ 0.0015·r — < 0.05mm for any reach under
# 300mm, absorbed many times over by the swept clearance below.
HINGE_POCKET_SWEEP_STEP_DEG = 2.0

# Radial growth applied to the MOVING bodies before rotate-union — the
# swing clearance between moving and static hardware. 0.5mm: > 10x kernel
# fuzz, > the 2° chordal sag above, small enough to stay inside the cove
# clearance budget (COVE_CLEARANCE_MM = 5.0).
HINGE_POCKET_SWEPT_CLEARANCE_MM = 0.5

# Access bore for inserting the hinge wire: Ø = pin + this (the recipe's
# "Ø(wire+1.0)") — free clearance for feeding a slightly bowed wire
# through multiple tube segments.
HINGE_ACCESS_BORE_EXTRA_MM = 1.0

# Set-screw pilot in the outboard carrier — M3 tapping-size pilot (Ø2.5),
# cut only, no thread geometry (same posture as boss_thread placeholders).
HINGE_SET_SCREW_DIA_MM = 2.5

# --- Spar shapes (D23, plan.md §8.7 step 7a — WP2) --------------------------

# Uniform clearance between a rib's spar cutout and the spar's own local
# cross-section footprint (all shapes). 0.2mm is the common laser/CNC kit
# slip-fit allowance for bonded CFRP assemblies (adhesive fills the gap) —
# deliberately 2x the interlock's fit_clearance_mm default (0.1, schema),
# since a plain cutout is non-locating (nothing registers against it) while
# a tab/slot pair is a locating feature and wants the tighter fit.
SPAR_RIB_CUTOUT_CLEARANCE_MM = 0.2

# Sampled-frame count for cap-path lofts (c_channel/i_beam caps, box caps;
# reused by WP2b's π-section sweeps). R0-verified: probe_sweep_spine.py
# (docs/r0_findings/p06_ext.md) reproduced the analytic swept volume within
# 0.06% at 30 frames on a deliberately curved+twisted synthetic spine.
SPAR_CAP_SWEEP_FRAMES = 30

# Fraction of the loop-endpoints' spanwise extent trimmed off each end when
# splitting the spar-surface ∩ cavity section loop into upper/lower cap-path
# chains — discards the near-vertical root/tip closure segments of the loop
# (which belong to neither chain). 2% of span extent comfortably exceeds the
# closure segments' own y-footprint (they are nominally constant-y) while
# costing a negligible sliver of cap length at each end.
CAP_PATH_END_TRIM_FRAC = 0.02

# Bond-line gap for skin-side bonded interfaces built to stand off the inner
# face sheet (c_channel/i_beam `inside_iml` caps now; WP2b π-joint base/legs
# reuse it as THE π bond gap). 0.2mm is a standard structural adhesive film
# thickness (e.g. 3M AF163-2 class) — same order as one provisional ply.
PI_BOND_GAP_MM = 0.2

# --- π-joint ribs (D24, plan.md §8.7 step 7b — WP2b) ------------------------
#
# D24 applies to every rib; the §6 schema deliberately adds no π block, so
# the π-section dimensions are tool constants here (promotable to schema
# later without construction changes — pi_joints.py reads only these).

# π preform base thickness — 3 plies of the provisional 0.2mm CFRP twill
# (PLY_THICKNESS_MM_PROVISIONAL), the light-preform layup a bonded rib/skin
# joint at this wing scale typically uses.
PI_BASE_THICKNESS_MM = 0.6

# π preform leg thickness — same 3-ply preform laminate as the base.
PI_LEG_THICKNESS_MM = 0.6

# π leg height (how far each leg reaches down the rib face from the base) —
# ~10-15x the bond-line thickness gives a bond area per leg comparable to
# the classic aerospace guideline of >= 10x adherend thickness for a lap
# joint; 8mm also stays well clear of typical lightening-hole margins
# (schema default margin_mm: 8).
PI_LEG_HEIGHT_MM = 8.0

# Chordwise margin (fraction of the rib's local chordwise extent) at each
# end of the skin-contact chains that is left UN-offset when building the
# π rib outline — the LE/TE closure segments of the cavity boundary belong
# to neither skin, and 3% comfortably covers their footprint on every
# vendored airfoil (LE closure ~1-2% x/c; blunt-TE closure <1%) without
# giving away meaningful bond length.
PI_SKIN_END_MARGIN_FRAC = 0.03

# Shoulder the π base extends chordwise-across (spanwise, along the rib
# normal) beyond each leg's outer face — keeps the base->leg junction away
# from the base's own edge (a molded preform needs a flat land outboard of
# the leg radius; 2mm is a common minimum preform flange land).
PI_BASE_SHOULDER_MM = 2.0

# Chordwise margin added around each spar footprint's x-interval when
# trimming π paths clear of spar crossings — the preform must not touch the
# spar body; one SPAR_RIB_CUTOUT_CLEARANCE_MM each side plus 2mm handling/
# layup positioning slack.
PI_SPAR_CLEARANCE_MM = 2.2

# Tube spars: max outer diameter as a fraction of the LOCAL internal cavity
# depth at the tube's chordwise station (recipe/D23: "validate od <= 60%
# local internal depth"). Leaves >= 40% of the depth as bond/positioning
# headroom above+below the tube.
TUBE_OD_DEPTH_FRAC_MAX = 0.6

# Station count for the tube-OD-vs-depth validation sweep (D23 recipe: "at
# 20 stations") — dense enough to catch a taper crossing the 60% line
# mid-span between config stations.
TUBE_DEPTH_VALIDATION_STATIONS = 20

# --- Face-naming centroid registry (plan.md §8.8 "Face naming for FEA" —
# shared by WP1 carriers, WP2b π bonds, WP2c tab/slot bonds) -----------------

# Max distance between a bond face's RECORDED centroid (at creation time)
# and a candidate final face's centroid. Booleans that merely re-tessellate
# or split an untouched face move its centroid by kernel-tolerance amounts
# (~BOOLEAN_FUZZY_VALUE_MM); a face that lost a corner to a nearby cut can
# shift by a few tenths. 0.5mm accepts the former and the benign end of the
# latter while still rejecting a mismatch to any OTHER face of these parts
# (bond faces on the same body are never closer than a leg thickness,
# 0.6mm, let alone a rib bay).
FACE_REGISTRY_CENTROID_TOL_MM = 0.5

# Min |dot| between recorded and candidate unit normals ("normal aligned").
# 0.98 = ~11.5° cone — generous for planar bond faces (which stay exactly
# parallel through booleans) while rejecting a neighboring perpendicular
# face outright.
FACE_REGISTRY_NORMAL_DOT_MIN = 0.98

# Candidate face area must be within this fraction of the recorded area —
# the recipe's own "area within 10%".
FACE_REGISTRY_AREA_TOL_FRAC = 0.10

# --- Kinematic sweep (P8, plan.md §9 "the decisive R1 gate") ---------------

# Coarse angular step across the full ±max_deflection sweep — plan.md's own
# "coarse 1° steps" wording.
KINEMATIC_COARSE_STEP_DEG = 1.0

# Fine angular step within the outer travel band near each extreme —
# plan.md's own "fine 0.1° steps" wording; F9's whole point is that a
# collision near the tightest-clearance extreme can be missed between
# coarse samples, so the fine band gets 10x the resolution there.
KINEMATIC_FINE_STEP_DEG = 0.1

# Fraction of max_deflection_deg, measured from each extreme inward, that
# gets the fine step instead of (in addition to) the coarse one — plan.md's
# own "fine ... steps in the outer 20% of travel" wording.
KINEMATIC_FINE_ZONE_FRAC = 0.20

# Angular step for the swept-volume envelope (union of rotated copies,
# same technique as WP1's pocket construction, R0-verified accurate to
# 1.5e-14mm — docs/r0_findings/p07.md). Independent of the coarse/fine
# COLLISION-SAMPLING steps above: this is a single continuous envelope
# from 0 to the extreme, not point samples, so it can afford to be coarser
# without risking a missed collision (F9 is specifically about POINT
# sampling; the envelope itself is exact between its own steps up to
# ordinary chordal-sag error, HINGE_POCKET_SWEEP_STEP_DEG's own
# derivation).
KINEMATIC_SWEPT_ENVELOPE_STEP_DEG = 2.0

# Clearance floor tolerance: pass criterion is "minimum clearance >=
# gap_mm - tolerance" (plan.md). Kernel-fuzz-scale slack on top of the
# configured gap_mm, same role as HINGE_LUG_CLEARANCE_MARGIN_MM's original
# reasoning (never a fixed absolute floor independent of gap_mm, since
# that wouldn't generalize across configs).
KINEMATIC_CLEARANCE_TOLERANCE_MM = 0.05

# Proximity-cull margin for the skin-clearance distance sweep
# (kinematics.proximity_face_subsets): static-body faces farther than this
# from the moving body's rotation-swept bounding box are dropped before any
# BRepExtrema call. Found the hard way (docs/known_issues.md):
# BRepExtrema_DistShapeShape on the two FULL lofted skin solids (hundreds
# of narrow ruled faces each) blew a 10-hour pytest budget mid-sweep — the
# cull is what makes the per-angle distance computation tractable at all.
# SOUNDNESS: the check asserts min clearance >= gap_mm - tolerance; a
# culled face sits > margin away from every position of the moving body,
# so with margin (25.0) > any configured gap_mm (5.0 across current
# configs, 5x headroom) a culled face can never be the face that decides a
# pass/fail at the floor — the assertion's outcome is identical to the
# uncalled computation's, only the reported min can saturate at > margin,
# which is still unambiguously a pass.
KINEMATIC_PROXIMITY_CULL_MARGIN_MM = 25.0

# --- Web UI E2E (P10, plan.md §9 P10 pass criteria) -------------------------

# "compare a tracked vertex against server-computed position": the E2E gate
# rotates a tracked glTF vertex client-side (three.js Quaternion about the
# hinge axis) and compares it against the SAME vertex rotated server-side
# (kinematics.rotate_point, pure Rodrigues' formula on the identical axis —
# R0-verified accurate to 1.5e-14mm against cq.Shape.rotate, docs/r0_findings/
# p07.md) — two independent rotation implementations of the same rigid
# transform. This tolerance absorbs glTF's float32 position encoding (spec-
# mandated component type) at this wing's coordinate scale (chords/spans up
# to ~O(1e3)mm: float32 epsilon ≈ 1e3 * 1.19e-7 ≈ 1.2e-4mm) plus three.js's
# own float32 matrix math, with a wide margin — NOT a geometric-construction
# tolerance (no OCC boolean is involved in this check at all).
KINEMATIC_VERTEX_CHECK_TOLERANCE_MM = 0.01

# P10 E2E gate (tests/gates/test_p10_web_e2e.py): wall-clock budget for one
# full job (submit -> build_wing -> export -> done) driven through the real
# API/worker stack. Deliberately NOT GEOMETRY_TEST_TIMEOUT_S: backend.
# pipeline.build_wing is production code and per CLAUDE.md's hard rule
# NEVER goes through tests/gates/geometry_cache.py, so a te_half.yaml job
# here pays the full uncached cost every time — P6's own gate docstring
# measures ~60-90min for the sandwich/rib/spar body alone on a cache miss,
# plus P7's own ~300-450s for hinges. 7200s (2hr) gives real headroom on
# top of that measured combined cost, same "generous but not infinite, so a
# genuine hang still fails loud" posture as GEOMETRY_TEST_TIMEOUT_S's own
# derivation.
P10_E2E_JOB_TIMEOUT_S = 7200

# --- Test infrastructure (not a geometric tolerance, but per-project rule:
# every numeric constant lives here, none inline) ----------------------------

# Per-test wall-clock budget (pytest-timeout) for any gate test that builds
# real OCC geometry (device-cut booleans, lofts). A single measured baseline
# (te_half, full detailed nose/cove checks incl. 5 real OCC re-sections) ran
# ~260s; 600s gives ~2.3x headroom for a slower device config (e.g. a tilted
# hinge frame with more complex boolean topology) while still failing loud
# and fast if a construction change introduces a genuine hang rather than
# just being slow — "hang vs slow" must be answered by this timeout firing
# (or not) plus the per-stage timings.py-adjacent JSON, never by a human
# watching a terminal.
GEOMETRY_TEST_TIMEOUT_S = 600
