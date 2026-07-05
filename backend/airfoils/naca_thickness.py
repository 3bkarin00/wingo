"""Minimal analytic NACA4/5 thickness helper.

Standalone from the full P1 airfoil ingest/resample pipeline (NACA
generators, UIUC ingest, cosine resampling — plan.md §8.1). This exists only
so the P0 sandwich-stack-vs-thickness rule (F15) has *some* thickness source
before P1 builds the real subsystem. NACA 4- and 5-digit series share the
same closed-form thickness distribution (only the camber line differs
between the two series, and camber doesn't affect thickness), so one
function covers both.
"""
import math
import re

_NACA_RE = re.compile(r"^naca(\d{4}|\d{5})$", re.IGNORECASE)

# Chord fractions sampled for the "min local thickness" estimate. Endpoints
# near LE/TE are excluded because thickness naturally tapers to ~0 there and
# isn't representative of where the sandwich stack actually sits.
_SAMPLE_X_FRAC = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def thickness_frac(airfoil_name: str, x_frac: float) -> float | None:
    """Full thickness at x_frac, as a fraction of chord. None if unparseable."""
    match = _NACA_RE.match(airfoil_name.strip())
    if not match:
        return None
    digits = match.group(1)
    t = int(digits[-2:]) / 100.0  # max thickness %chord = last two digits
    x = x_frac
    yt = 5 * t * (
        0.2969 * math.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1015 * x**4
    )
    return 2 * yt


def min_thickness_mm(airfoil_name: str, chord_mm: float) -> float | None:
    """Minimum thickness (mm) over the sampled mid-chord region. None if the
    airfoil name isn't a NACA4/5 code this helper can parse (e.g. a UIUC or
    uploaded airfoil — those need the real P1 pipeline)."""
    fracs = [thickness_frac(airfoil_name, x) for x in _SAMPLE_X_FRAC]
    if any(f is None for f in fracs):
        return None
    return min(fracs) * chord_mm
