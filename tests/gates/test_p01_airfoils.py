"""P1 gate — plan.md §9 pass criteria:

  100% of vendored UIUC files normalize OR quarantine with a reason string
  (0 silent failures); NACA generators match published ordinate tables within
  tolerance for 3 reference sections; resample round-trip max deviation
  < 1e-3 chord; every normalized foil has TE thickness >= te_min_thickness_mm.

Ground truth for the NACA check is the vendored UIUC-published coordinate
files (data/uiuc_snapshot/), compared by geometric point-to-curve distance
(backend/airfoils/metrics.py) — not y-at-x, which is invalid near the LE.
"""
from pathlib import Path

import pytest

from backend import tolerances
from backend.airfoils.metrics import max_point_to_curve_deviation
from backend.airfoils.naca import generate_naca
from backend.airfoils.resample import cosine_resample
from backend.airfoils.uiuc_ingest import (
    detect_format_and_coords,
    ingest_snapshot,
    _normalize_unit_chord,
)
from backend.airfoils.types import Airfoil, QuarantinedAirfoil

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = REPO_ROOT / "data" / "uiuc_snapshot"

# TE thickness requirement (plan.md §9): te_min_thickness_mm at the smallest
# chord in play. 0.8 mm is the schema default (te_min_thickness_mm); 180 mm is
# the smallest chord in the full_example golden config — the tightest case, so
# the derived unit-chord fraction here is the strictest the tool must satisfy.
TE_MIN_THICKNESS_MM = 0.8
REFERENCE_MIN_CHORD_MM = 180.0
TE_THICKNESS_FRAC = TE_MIN_THICKNESS_MM / REFERENCE_MIN_CHORD_MM

RESAMPLE_POINTS = 199
REFERENCE_SECTIONS = ["naca2412", "naca4412", "naca23012"]


@pytest.fixture(scope="module")
def ingested():
    return ingest_snapshot(SNAPSHOT, RESAMPLE_POINTS, TE_THICKNESS_FRAC)


def test_zero_silent_failures(ingested, gate_metrics):
    normalized, quarantined = ingested
    all_dats = sorted(SNAPSHOT.glob("*.dat"))

    # Every file is accounted for as EITHER normalized OR quarantined.
    assert len(normalized) + len(quarantined) == len(all_dats)
    covered = {a.name for a in normalized} | {q.name for q in quarantined}
    assert covered == {p.stem for p in all_dats}

    # Every quarantine carries a non-empty reason string.
    for q in quarantined:
        assert isinstance(q, QuarantinedAirfoil) and q.reason.strip()

    # The deliberately-malformed fixture MUST be in quarantine (proves the
    # quarantine path is live, not that everything happened to normalize).
    quarantined_names = {q.name for q in quarantined}
    assert "_quarantine_me" in quarantined_names

    gate_metrics["total_dat_files"] = len(all_dats)
    gate_metrics["normalized"] = len(normalized)
    gate_metrics["quarantined"] = len(quarantined)
    gate_metrics["quarantine_reasons"] = {q.name: q.reason for q in quarantined}


def test_normalized_foils_meet_te_thickness(ingested, gate_metrics):
    normalized, _ = ingested
    assert normalized  # sanity: we actually normalized something
    worst = 1.0
    for foil in normalized:
        te_mm = foil.te_thickness() * REFERENCE_MIN_CHORD_MM
        assert te_mm >= TE_MIN_THICKNESS_MM - 1e-9, (
            f"{foil.name}: TE {te_mm:.4f} mm < required {TE_MIN_THICKNESS_MM} mm"
        )
        worst = min(worst, te_mm)
    gate_metrics["min_te_thickness_mm"] = worst


@pytest.mark.parametrize("code", REFERENCE_SECTIONS)
def test_naca_matches_published(code, gate_metrics):
    generated = generate_naca(code, n_points=999).points
    raw = (SNAPSHOT / f"{code}.dat").read_text().splitlines()
    _, coords = detect_format_and_coords(raw)
    published = _normalize_unit_chord(coords)

    dev = max_point_to_curve_deviation(published, generated)
    assert dev < tolerances.NACA_PUBLISHED_MATCH_MAX_DEV_FRAC, (
        f"{code}: generator deviates {dev:.2e} from published "
        f"(limit {tolerances.NACA_PUBLISHED_MATCH_MAX_DEV_FRAC:.2e})"
    )
    gate_metrics.setdefault("naca_published_dev", {})[code] = dev


@pytest.mark.parametrize("code", REFERENCE_SECTIONS)
def test_resample_round_trip(code, gate_metrics):
    dense = generate_naca(code, n_points=1999).points
    resampled = cosine_resample(dense, RESAMPLE_POINTS)
    dev = max_point_to_curve_deviation(resampled, dense)
    assert dev < tolerances.RESAMPLE_ROUNDTRIP_MAX_DEV_FRAC, (
        f"{code}: resample round-trip deviation {dev:.2e} "
        f"(limit {tolerances.RESAMPLE_ROUNDTRIP_MAX_DEV_FRAC:.2e})"
    )
    gate_metrics.setdefault("resample_roundtrip_dev", {})[code] = dev
