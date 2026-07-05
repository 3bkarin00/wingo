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
# hazard. The cove/nose clearance (gap_mm, ≥1 mm typical) must exceed it by a
# wide margin. 0.1 mm sits far above kernel noise and far below any real gap.
FACE_TANGENCY_TOLERANCE_MM = 0.1
