"""False spar: closing wall for the TE device cut (plan.md §8.5 step 5 /
§8.7 step 7 — "false spars close device cut faces").

WHY IT EXISTS: within the device spanwise window, the wing's aft boundary is
the cove cut surface (a concave arc of radius r_cove = StationFeet.R +
COVE_CLEARANCE_MM around each station's hinge point C — cove_profile.py).
The sandwich cavity (`wing ∩ hollow_IML`) is otherwise EXPOSED at that
surface: the per-station IML offsets come from the original uncut airfoil,
so nothing closes the interior at the cut. The false spar is a flat wall
just forward of the cove that seals the main (forward) cavity bay. The small
open bay left BETWEEN the wall and the cove face is physically correct — the
cove region is open to the hinge gap anyway for the CS nose to sweep
through; its bare-core lip treatment belongs to ramped drop-offs at hinge
lands (D11), not to this wall.

CONSTRUCTION (probed machinery only — per-station polygon wires, ruled
loft, fuzzy boolean; no new third-party boundary, hence no new R0 probe —
judgment recorded in docs/r0_findings/p06.md):

  per station s along the hinge axis (same N_STATIONS convention as
  te_cut.py, extended past the window by gap_mm on each side so the wall
  ties into the clean-span cavity instead of ending coincident with the
  window's cut end-faces — an F4-style hazard AND a bond flange for the
  forced device-edge ribs that arrive later in P6):
    x_aft(s) = -(r_cove(s) + FALSE_SPAR_COVE_STANDOFF_MM)   [local a-coord]
    x_fwd(s) = x_aft(s) - wall thickness
  rectangle (x from x_fwd to x_aft, u from -H to +H with H generously
  larger than the local section) -> ruled loft -> wall prism
  false_spar = wall_prism ∩ hollow_IML loft

Intersecting with the HOLLOW-IML LOFT (not the wing body) is deliberate and
sufficient: forward of the cove's forwardmost sweep and forward of the
hinge plane, hollow_IML ⊆ wing (the cove/aft-box cuts only remove material
aft of / inside the cove region), so the cheap loft ∩ loft boolean gives
the same solid as a ∩ against the actual wing body without paying the
body-boolean cost. The wall follows the cove per station (tapered configs
keep a constant standoff) rather than sitting at a global max — for
aft-hinge configs the cove sweep already reaches to/past the rear spar's
plane, and hugging the cove keeps the wall as far aft as the cut allows.

KNOWN DESIGN TENSION (documented, deferred): for these aft-hinge configs
(hinge_xc 0.70-0.75, rear spar 0.68-0.70) the wall can land within a few mm
of — or straddle station-wise — the rear spar's PLANE. The rear spar is
still a zero-thickness P3 reference surface; when spars are thickened and
trimmed to the IML (later in P6), the P6 gate's pairwise-interference check
arbitrates, and the physical resolution if they collide is merging the two
webs (standard practice), not moving the false spar off the cut.

WALL THICKNESS: one skin panel stack (face + core + face = the P0 per-wall
`stack_mm`) — the wall is a sandwich cap of the same layup as the skin it
closes (its laminate decomposition arrives with the midsurface work).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cadquery as cq
import numpy as np

from backend import tolerances
from backend.geometry.booleans import fuzzy_common
from backend.geometry.cove_profile import analytic_section_points, find_station_feet
from backend.geometry.iml import face_sheet_thickness_mm
from backend.geometry.sections import PlacedSection
from backend.geometry.te_cut import N_STATIONS, hinge_frame
from backend.schema.models import Config

# Wall half-height factor (× local chord) — must merely guarantee the wall
# prism crosses BOTH inner face sheets transversally and pokes well outside
# the section (max airfoil half-thickness here is ~6% chord); the ∩ with the
# hollow-IML loft bounds it. Same "generously oversized cutting prism"
# convention as te_cut.py's aft boxes (3× chord).
_WALL_HALF_HEIGHT_CHORD_FRAC = 0.3


@dataclass
class FalseSpar:
    solid: cq.Shape
    # Per-station aft-face a-coordinate (relative to the station's hinge
    # point C), kept so a gate can re-verify the standoff against the cove
    # without re-deriving station feet.
    aft_x_local_mm: list = field(default_factory=list)
    thickness_mm: float = 0.0
    timings_s: dict = field(default_factory=dict)


def build_false_spar(
    config: Config, sections: list[PlacedSection], hollow_iml_solid: cq.Solid
) -> FalseSpar:
    """Build the wing-side closing wall for the enabled te_surface device.
    `sections` must be the same half-span PlacedSection list the OML/IML
    lofts were built from (mirror:false device configs, matching te_cut.py's
    scoping); `hollow_iml_solid` is the cavity loft from
    iml.build_sandwich_lofts."""
    te = config.te_surface
    if te is None or not te.enabled:
        raise ValueError("config has no enabled te_surface")

    timings: dict = {}
    t0 = time.perf_counter()

    p0, _, h, a, u, axis_len = hinge_frame(config)
    gap = te.gap_mm
    wall_mm = 2 * face_sheet_thickness_mm(config) + config.skin.core.thickness_mm

    ys = np.array([s.y_mm for s in sections])
    chords = np.array([s.chord_mm for s in sections])

    s_vals = np.linspace(-gap, axis_len + gap, N_STATIONS)
    wires, aft_x = [], []
    for s in s_vals:
        C = p0 + h * s
        pts = analytic_section_points(sections, C, h)
        feet = find_station_feet(pts, C, a, u)
        r_cove = feet.R + tolerances.COVE_CLEARANCE_MM
        x_aft = -(r_cove + tolerances.FALSE_SPAR_COVE_STANDOFF_MM)
        x_fwd = x_aft - wall_mm
        H = _WALL_HALF_HEIGHT_CHORD_FRAC * float(np.interp(C[1], ys, chords))
        corners = [
            C + x_fwd * a - H * u,
            C + x_aft * a - H * u,
            C + x_aft * a + H * u,
            C + x_fwd * a + H * u,
        ]
        wires.append(cq.Wire.makePolygon([cq.Vector(*p) for p in corners], close=True))
        aft_x.append(float(x_aft))
    wall_prism = cq.Solid.makeLoft(wires, ruled=True)
    timings["wall_prism_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    solid = fuzzy_common(wall_prism, hollow_iml_solid)
    timings["cavity_common_s"] = time.perf_counter() - t0

    return FalseSpar(
        solid=solid,
        aft_x_local_mm=aft_x,
        thickness_mm=wall_mm,
        timings_s=timings,
    )
